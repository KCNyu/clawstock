// Package analyzer parses Go source files and extracts function metadata + coverage.
package analyzer

import (
	"bytes"
	"encoding/json"
	"fmt"
	"go/ast"
	"go/format"
	"go/parser"
	"go/token"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// FunctionInfo holds everything the generator needs to write a test.
type FunctionInfo struct {
	FilePath    string   // absolute path to source file
	PackageName string   // go package name
	PackagePath string   // import path (for go test ./...)
	FuncName    string   // function/method name
	IsExported  bool
	Receiver    string   // non-empty for methods, e.g. "*UserService"
	Signature   string   // full func signature line
	Body        string   // formatted source of the function
	StartLine   int
	EndLine     int
	Imports     []string // imports in the source file
	SiblingCtx  string   // other types/constants in the package (for context)
	Coverage    float64  // 0.0–1.0, -1 = not measured
	HasExistingTest bool
	// priority score: higher = generate first
	Priority float64
}

// Analyzer walks a Go repository and produces FunctionInfo records.
type Analyzer struct {
	RepoPath string
	fset     *token.FileSet
}

func New(repoPath string) *Analyzer {
	return &Analyzer{
		RepoPath: repoPath,
		fset:     token.NewFileSet(),
	}
}

// Analyze walks all packages under RepoPath and returns function list.
func (a *Analyzer) Analyze() ([]*FunctionInfo, error) {
	a.fset = token.NewFileSet()
	var result []*FunctionInfo

	err := filepath.WalkDir(a.RepoPath, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		// skip vendor, hidden dirs, and test files themselves
		if d.IsDir() {
			base := d.Name()
			if base == "vendor" || base == "testdata" || strings.HasPrefix(base, ".") {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(path, ".go") || strings.HasSuffix(path, "_test.go") {
			return nil
		}

		fns, err := a.parseFile(path)
		if err != nil {
			return nil // soft skip bad files
		}
		result = append(result, fns...)
		return nil
	})
	if err != nil {
		return nil, err
	}

	// enrich with existing test presence
	a.markExistingTests(result)

	return result, nil
}

func (a *Analyzer) parseFile(filePath string) ([]*FunctionInfo, error) {
	src, err := os.ReadFile(filePath)
	if err != nil {
		return nil, err
	}

	file, err := parser.ParseFile(a.fset, filePath, src, parser.ParseComments)
	if err != nil {
		return nil, err
	}

	pkgName := file.Name.Name
	pkgPath := a.importPathFor(filePath)
	imports := collectImports(file)
	siblingCtx := a.buildSiblingContext(file, src)

	var fns []*FunctionInfo
	for _, decl := range file.Decls {
		fn, ok := decl.(*ast.FuncDecl)
		if !ok || fn.Body == nil {
			continue
		}

		info := &FunctionInfo{
			FilePath:    filePath,
			PackageName: pkgName,
			PackagePath: pkgPath,
			FuncName:    fn.Name.Name,
			IsExported:  fn.Name.IsExported(),
			Imports:     imports,
			SiblingCtx:  siblingCtx,
			Coverage:    -1,
		}

		// receiver (method)
		if fn.Recv != nil && len(fn.Recv.List) > 0 {
			var buf bytes.Buffer
			format.Node(&buf, a.fset, fn.Recv.List[0].Type)
			info.Receiver = buf.String()
		}

		// signature
		info.Signature = a.formatSignature(fn)

		// body
		start := a.fset.Position(fn.Pos()).Line
		end := a.fset.Position(fn.End()).Line
		info.StartLine = start
		info.EndLine = end
		lines := strings.Split(string(src), "\n")
		if start > 0 && end <= len(lines) {
			info.Body = strings.Join(lines[start-1:end], "\n")
		}

		fns = append(fns, info)
	}
	return fns, nil
}

// GetCoverage runs go test -coverprofile for each unique package path and
// returns a map of "pkgPath::FuncName" → coverage fraction.
func (a *Analyzer) GetCoverage(pkgPaths []string) (map[string]float64, error) {
	result := make(map[string]float64)

	for _, pkg := range pkgPaths {
		tmpFile := filepath.Join(os.TempDir(), "cov_"+sanitizePkg(pkg)+".out")
		cmd := exec.Command("go", "test", "-coverprofile="+tmpFile, "-covermode=set", "./"+pkg+"/...")
		cmd.Dir = a.RepoPath
		_ = cmd.Run() // ignore test failures; we just want coverage data

		data, err := os.ReadFile(tmpFile)
		if err != nil {
			continue
		}
		os.Remove(tmpFile)

		// parse coverage.out  (format: mode:set\nfile:startline.col,endline.col stmts count)
		for _, line := range strings.Split(string(data), "\n") {
			if strings.HasPrefix(line, "mode:") || line == "" {
				continue
			}
			// we only track at file level here; per-func requires go tool cover -func
		}
		// use go tool cover -func for per-function data
		coverFunc := a.runCoverFunc(tmpFile)
		for funcKey, pct := range coverFunc {
			result[pkg+"::"+funcKey] = pct
		}
	}
	return result, nil
}

// runCoverFunc parses `go tool cover -func` output.
func (a *Analyzer) runCoverFunc(profilePath string) map[string]float64 {
	out, err := exec.Command("go", "tool", "cover", "-func="+profilePath).Output()
	if err != nil {
		return nil
	}
	result := make(map[string]float64)
	for _, line := range strings.Split(string(out), "\n") {
		if strings.Contains(line, "total:") {
			continue
		}
		// format:  file.go:line:  FuncName  60.0%
		parts := strings.Fields(line)
		if len(parts) < 3 {
			continue
		}
		funcName := parts[1]
		pctStr := strings.TrimSuffix(parts[2], "%")
		var pct float64
		fmt.Sscanf(pctStr, "%f", &pct)
		result[funcName] = pct / 100.0
	}
	return result
}

// ComputePriority assigns a score to a function (higher = more urgent).
// Formula: (1 - coverage) * complexityScore * exportedBonus
func ComputePriority(f *FunctionInfo) float64 {
	cov := f.Coverage
	if cov < 0 {
		cov = 0 // unmeasured → assume 0
	}
	lines := float64(f.EndLine - f.StartLine)
	complexity := 1.0
	if lines > 100 {
		complexity = 3.0
	} else if lines > 30 {
		complexity = 2.0
	}
	exportedBonus := 1.0
	if f.IsExported {
		exportedBonus = 1.5
	}
	return (1.0 - cov) * complexity * exportedBonus
}

// helpers

func (a *Analyzer) importPathFor(filePath string) string {
	rel, _ := filepath.Rel(a.RepoPath, filepath.Dir(filePath))
	return rel
}

func (a *Analyzer) formatSignature(fn *ast.FuncDecl) string {
	var buf bytes.Buffer
	// reconstruct just the func line
	buf.WriteString("func ")
	if fn.Recv != nil {
		buf.WriteString("(")
		format.Node(&buf, a.fset, fn.Recv)
		buf.WriteString(") ")
	}
	buf.WriteString(fn.Name.Name)
	format.Node(&buf, a.fset, fn.Type)
	return buf.String()
}

func (a *Analyzer) buildSiblingContext(file *ast.File, src []byte) string {
	// collect type declarations and const/var blocks (but NOT func bodies)
	// so the LLM knows what types exist in the package
	var parts []string
	for _, decl := range file.Decls {
		switch d := decl.(type) {
		case *ast.GenDecl:
			var buf bytes.Buffer
			format.Node(&buf, a.fset, d)
			s := buf.String()
			// trim very long things
			if len(s) < 2000 {
				parts = append(parts, s)
			}
		}
	}
	ctx := strings.Join(parts, "\n")
	if len(ctx) > 4000 {
		ctx = ctx[:4000] + "\n// ... (truncated)"
	}
	return ctx
}

func (a *Analyzer) markExistingTests(fns []*FunctionInfo) {
	seen := make(map[string]bool)
	for _, f := range fns {
		dir := filepath.Dir(f.FilePath)
		if seen[dir] {
			continue
		}
		seen[dir] = true

		testFile := strings.TrimSuffix(f.FilePath, ".go") + "_test.go"
		if _, err := os.Stat(testFile); err == nil {
			// mark all functions in this file
			for _, fn := range fns {
				if filepath.Dir(fn.FilePath) == dir {
					fn.HasExistingTest = true
				}
			}
		}
	}
}

func collectImports(file *ast.File) []string {
	var imports []string
	for _, imp := range file.Imports {
		path := strings.Trim(imp.Path.Value, `"`)
		imports = append(imports, path)
	}
	return imports
}

func sanitizePkg(pkg string) string {
	return strings.NewReplacer("/", "_", ".", "_").Replace(pkg)
}

// CoverageReport is the result of one full coverage measurement.
type CoverageReport struct {
	TotalFunctions int
	Covered        int
	TotalLines     int
	CoveredLines   int
	ByPackage      map[string]PackageCoverage
}

type PackageCoverage struct {
	Total   int
	Covered int
	Pct     float64
}

// MeasureTotalCoverage runs go test -cover for the whole repo and parses the summary.
func (a *Analyzer) MeasureTotalCoverage() (float64, error) {
	out, err := exec.Command("go", "test", "-cover", "./...").CombinedOutput()
	if err != nil && !strings.Contains(string(out), "coverage:") {
		return 0, fmt.Errorf("go test failed: %w\n%s", err, out)
	}
	// parse lines like: ok   github.com/foo/bar   0.123s  coverage: 67.5% of statements
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

// ExistingTestsInDir returns the content of all _test.go in the same dir.
func ExistingTestsInDir(dir string) string {
	entries, _ := os.ReadDir(dir)
	var sb strings.Builder
	for _, e := range entries {
		if strings.HasSuffix(e.Name(), "_test.go") {
			data, _ := os.ReadFile(filepath.Join(dir, e.Name()))
			sb.Write(data)
			sb.WriteString("\n")
		}
	}
	return sb.String()
}

// CoverageJSON is used to unmarshal `go test -json` output (unused for now, kept for extensibility).
type CoverageJSON struct {
	Action  string  `json:"Action"`
	Package string  `json:"Package"`
	Output  string  `json:"Output"`
	Elapsed float64 `json:"Elapsed"`
}

var _ = json.Marshal // suppress import warning
