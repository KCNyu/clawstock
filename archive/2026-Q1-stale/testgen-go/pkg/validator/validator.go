// Package validator compiles and runs the generated test, parses failures,
// and drives the fix loop.
// Design: inspired by ByteDance's "智能修复" multi-pass pipeline.
package validator

import (
	"bytes"
	"context"
	"fmt"
	"go/format"
	"go/parser"
	"go/token"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/testgen-go/pkg/analyzer"
)

// Result is the outcome of one validation attempt.
type Result struct {
	Passed       bool
	CompileError string
	TestError    string
	CoverageDelta float64
	Output       string
}

// Validator writes test files and runs `go test`.
type Validator struct {
	RepoPath   string
	MaxRetries int
}

func New(repoPath string, maxRetries int) *Validator {
	if maxRetries == 0 {
		maxRetries = 3
	}
	return &Validator{RepoPath: repoPath, MaxRetries: maxRetries}
}

// WriteAndTest writes the generated code to disk and runs go test.
// Returns a Result; if !Passed the caller should retry with Result.CompileError or TestError.
func (v *Validator) WriteAndTest(ctx context.Context, fn *analyzer.FunctionInfo, generatedCode string) (*Result, string, error) {
	// 1. Validate syntax before touching disk
	if err := syntaxCheck(generatedCode); err != nil {
		return &Result{CompileError: fmt.Sprintf("syntax error in generated code: %v", err)}, "", nil
	}

	// 2. Determine target test file path
	testFile := testFilePath(fn.FilePath)

	// 3. Merge with existing test file (append if exists)
	finalCode, err := mergeTestFile(testFile, generatedCode, fn.FuncName)
	if err != nil {
		return nil, "", fmt.Errorf("merge failed: %w", err)
	}

	// 4. Write to disk (in a temp file first to stay atomic-ish)
	if err := os.WriteFile(testFile, []byte(finalCode), 0644); err != nil {
		return nil, testFile, fmt.Errorf("write failed: %w", err)
	}

	// 5. go build (compile check, fast)
	if compileErr := v.compileCheck(ctx, fn.PackagePath); compileErr != "" {
		return &Result{CompileError: compileErr}, testFile, nil
	}

	// 6. go test (run)
	res := v.runTest(ctx, fn)
	return res, testFile, nil
}

// RevertTestFile removes the test file (used when all retries fail).
func (v *Validator) RevertTestFile(testFile string) {
	os.Remove(testFile)
}

// compileCheck runs `go build ./pkgPath` and returns the error output, or "".
func (v *Validator) compileCheck(ctx context.Context, pkgPath string) string {
	ctx, cancel := context.WithTimeout(ctx, 60*time.Second)
	defer cancel()

	args := []string{"build", "./" + pkgPath + "/..."}
	cmd := exec.CommandContext(ctx, "go", args...)
	cmd.Dir = v.RepoPath
	out, err := cmd.CombinedOutput()
	if err != nil {
		return string(out)
	}
	return ""
}

// runTest runs `go test -v -run Test<FuncName> ./pkgPath/...` and returns a Result.
func (v *Validator) runTest(ctx context.Context, fn *analyzer.FunctionInfo) *Result {
	ctx, cancel := context.WithTimeout(ctx, 120*time.Second)
	defer cancel()

	// measure coverage before
	preCov, _ := v.packageCoverage(fn.PackagePath)

	args := []string{
		"test",
		"-v",
		"-run", "Test" + fn.FuncName,
		"-coverprofile=/tmp/cov_" + sanitize(fn.FuncName) + ".out",
		"-covermode=atomic",
		"./" + fn.PackagePath + "/...",
	}
	cmd := exec.CommandContext(ctx, "go", args...)
	cmd.Dir = v.RepoPath
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	combined := stdout.String() + stderr.String()

	postCov, _ := v.packageCoverage(fn.PackagePath)

	if err != nil {
		// parse which tests failed
		return &Result{
			TestError:    extractFailure(combined),
			Output:       combined,
			CoverageDelta: postCov - preCov,
		}
	}
	return &Result{
		Passed:       true,
		Output:       combined,
		CoverageDelta: postCov - preCov,
	}
}

func (v *Validator) packageCoverage(pkgPath string) (float64, error) {
	out, err := exec.Command("go", "test", "-cover", "./"+pkgPath+"/...").CombinedOutput()
	if err != nil {
		return 0, nil
	}
	var total, count float64
	for _, line := range strings.Split(string(out), "\n") {
		if idx := strings.Index(line, "coverage: "); idx >= 0 {
			sub := line[idx+10:]
			var pct float64
			fmt.Sscanf(sub, "%f%%", &pct)
			total += pct
			count++
		}
	}
	if count == 0 {
		return 0, nil
	}
	return total / count, nil
}

// ExtractFixHint builds a concise error message to feed back to the LLM.
func ExtractFixHint(res *Result) string {
	if res.CompileError != "" {
		// trim to first 60 lines to stay within token budget
		return trimLines(res.CompileError, 60)
	}
	if res.TestError != "" {
		return trimLines(res.TestError, 60)
	}
	return ""
}

// ──────────────────────────────────────────────
// File management helpers
// ──────────────────────────────────────────────

// testFilePath derives the _test.go path from a source file path.
func testFilePath(srcPath string) string {
	base := strings.TrimSuffix(srcPath, ".go")
	return base + "_testgen_test.go"
}

// mergeTestFile merges new test code with existing _testgen_test.go content.
// Strategy: if the test for this function already exists, skip (idempotent).
func mergeTestFile(testFile, newCode, funcName string) (string, error) {
	testFuncMarker := "func Test" + funcName + "("

	// if file already has a test for this function, skip
	if existing, err := os.ReadFile(testFile); err == nil {
		if strings.Contains(string(existing), testFuncMarker) {
			return string(existing), nil // idempotent: nothing to do
		}
		// file exists but no test for this func: append new test functions only
		return appendTests(string(existing), newCode)
	}

	// new file
	return newCode, nil
}

// appendTests merges two Go source files by taking the package+imports from the
// first and appending the test functions from the second.
func appendTests(existing, newCode string) (string, error) {
	fset := token.NewFileSet()
	newFile, err := parser.ParseFile(fset, "", newCode, 0)
	if err != nil {
		return "", fmt.Errorf("cannot parse new test code: %w", err)
	}

	// collect test functions from newCode
	var newFuncs []string
	lines := strings.Split(newCode, "\n")
	for _, decl := range newFile.Decls {
		// extract the raw source of each top-level function declaration
		_ = decl
	}

	// simpler approach: strip package line + imports from newCode and append
	inImports := false
	skip := true
	for _, line := range lines {
		stripped := strings.TrimSpace(line)
		if skip {
			if stripped == "import (" {
				inImports = true
				continue
			}
			if inImports {
				if stripped == ")" {
					inImports = false
					skip = false
				}
				continue
			}
			if strings.HasPrefix(stripped, "package ") {
				continue
			}
			if stripped == "" {
				continue
			}
			if strings.HasPrefix(stripped, "import ") {
				continue
			}
			// first non-import, non-package line
			skip = false
		}
		newFuncs = append(newFuncs, line)
	}

	return existing + "\n" + strings.Join(newFuncs, "\n"), nil
}

// syntaxCheck parses the generated code to catch obvious syntax errors early.
func syntaxCheck(code string) error {
	fset := token.NewFileSet()
	_, err := parser.ParseFile(fset, "", code, 0)
	return err
}

// Format uses gofmt to tidy the code.
func Format(code string) (string, error) {
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, "", code, parser.ParseComments)
	if err != nil {
		return code, err // return as-is if parse fails
	}
	var buf bytes.Buffer
	if err := format.Node(&buf, fset, f); err != nil {
		return code, err
	}
	return buf.String(), nil
}

// extractFailure grabs the most relevant lines from test output.
func extractFailure(output string) string {
	var relevant []string
	for _, line := range strings.Split(output, "\n") {
		if strings.Contains(line, "FAIL") ||
			strings.Contains(line, "Error") ||
			strings.Contains(line, "panic") ||
			strings.Contains(line, "undefined") ||
			strings.Contains(line, "cannot") ||
			strings.Contains(line, "does not") {
			relevant = append(relevant, line)
		}
	}
	if len(relevant) == 0 {
		return trimLines(output, 30)
	}
	return strings.Join(relevant, "\n")
}

func trimLines(s string, n int) string {
	lines := strings.Split(s, "\n")
	if len(lines) > n {
		lines = lines[:n]
	}
	return strings.Join(lines, "\n")
}

func sanitize(s string) string {
	return strings.NewReplacer("/", "_", ".", "_", " ", "_").Replace(s)
}
