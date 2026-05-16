// Package generator calls an LLM to produce Go unit test code.
// Inspired by ByteDance QCon 2024: multi-stage pipeline with context assembly.
package generator

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"text/template"
	"time"

	"github.com/testgen-go/pkg/analyzer"
)

// Config controls LLM backend.
type Config struct {
	Provider string // "openai" | "anthropic" | "ollama"
	Model    string
	APIKey   string
	BaseURL  string // custom endpoint, e.g. for proxies or local ollama
	Timeout  int    // seconds
}

// Generator produces test source code using an LLM.
type Generator struct {
	cfg    Config
	client *http.Client
}

func New(cfg Config) *Generator {
	timeout := cfg.Timeout
	if timeout == 0 {
		timeout = 120
	}
	return &Generator{
		cfg:    cfg,
		client: &http.Client{Timeout: time.Duration(timeout) * time.Second},
	}
}

// GenerateTests returns the content of a _test.go file for the given function.
// fixHint is non-empty on retry passes and contains the previous compile/run error.
func (g *Generator) GenerateTests(ctx context.Context, fn *analyzer.FunctionInfo, existingTests string, fixHint string) (string, error) {
	prompt := g.buildPrompt(fn, existingTests, fixHint)
	switch g.cfg.Provider {
	case "anthropic":
		return g.callAnthropic(ctx, prompt)
	case "ollama":
		return g.callOllama(ctx, prompt)
	default:
		return g.callOpenAI(ctx, prompt)
	}
}

// ──────────────────────────────────────────────
// Prompt construction  (the most important part)
// ──────────────────────────────────────────────

const systemPrompt = `You are an expert Go developer specializing in writing unit tests for legacy codebases.

STRICT RULES — violating any of these will break the build:
1. NEVER modify source files. Only produce _test.go content.
2. Use the EXACT package name shown (package {{.PackageName}} or package {{.PackageName}}_test for black-box).
3. All imports must be real. Do NOT invent package paths.
4. Use table-driven tests with t.Run (Go idiomatic).
5. Use github.com/stretchr/testify/assert or require for assertions.
6. Mock external I/O (DB, HTTP, cache) with interfaces or httptest/sqlmock — do NOT dial real services.
7. Each test function name must start with Test.
8. The output must be ONLY valid Go source code — no markdown fences, no explanations.
9. If the function is unexported, use the same package (no _test suffix).
10. Do NOT refactor or restructure the function under test.`

var promptTmpl = template.Must(template.New("prompt").Parse(`
{{- if .FixHint}}
## PREVIOUS ATTEMPT FAILED — FIX THE FOLLOWING ERROR:
` + "```" + `
{{.FixHint}}
` + "```" + `
Analyze the error and produce corrected test code.
{{end}}

## FUNCTION TO TEST

File: {{.FilePath}}
Package: {{.PackageName}}
Import path: {{.PackagePath}}

### Imports in source file:
{{range .Imports}}- {{.}}
{{end}}

### Type / constant context (same package):
` + "```go" + `
{{.SiblingCtx}}
` + "```" + `

### Function under test:
` + "```go" + `
{{.Body}}
` + "```" + `

## EXISTING TESTS IN THIS PACKAGE (do not duplicate, only append new functions):
` + "```go" + `
{{.ExistingTests}}
` + "```" + `

## YOUR TASK
Write Go test function(s) that:
1. Cover the main happy path
2. Cover edge cases (nil inputs, empty slices, error returns, boundary values)
3. Cover each significant branch (if/switch arms)
4. Are completely self-contained and will pass with "go test ./..."

Output ONLY the new test functions (no package declaration, no imports block — those will be merged).
Actually, output a COMPLETE valid _test.go file including package line and all needed imports.
`))

type promptData struct {
	analyzer.FunctionInfo
	ExistingTests string
	FixHint       string
}

func (g *Generator) buildPrompt(fn *analyzer.FunctionInfo, existingTests string, fixHint string) string {
	data := promptData{
		FunctionInfo:  *fn,
		ExistingTests: existingTests,
		FixHint:       fixHint,
	}
	var buf bytes.Buffer
	if err := promptTmpl.Execute(&buf, data); err != nil {
		return fmt.Sprintf("generate test for %s in %s", fn.FuncName, fn.FilePath)
	}
	return buf.String()
}

func (g *Generator) sysPrompt(pkgName string) string {
	return strings.ReplaceAll(systemPrompt, "{{.PackageName}}", pkgName)
}

// ──────────────────────────────────────────────
// LLM backend calls
// ──────────────────────────────────────────────

// OpenAI-compatible (works for OpenAI, Azure, any OpenAI-compat proxy)
func (g *Generator) callOpenAI(ctx context.Context, userMsg string) (string, error) {
	baseURL := g.cfg.BaseURL
	if baseURL == "" {
		baseURL = "https://api.openai.com/v1"
	}
	model := g.cfg.Model
	if model == "" {
		model = "gpt-4o"
	}

	reqBody := map[string]interface{}{
		"model": model,
		"messages": []map[string]string{
			{"role": "system", "content": g.sysPrompt("")},
			{"role": "user", "content": userMsg},
		},
		"temperature": 0.2, // low for deterministic code
		"max_tokens":  4096,
	}
	return g.postJSON(ctx, baseURL+"/chat/completions", reqBody, func(body []byte) (string, error) {
		var resp struct {
			Choices []struct {
				Message struct {
					Content string `json:"content"`
				} `json:"message"`
			} `json:"choices"`
		}
		if err := json.Unmarshal(body, &resp); err != nil {
			return "", err
		}
		if len(resp.Choices) == 0 {
			return "", fmt.Errorf("empty response from OpenAI")
		}
		return cleanCode(resp.Choices[0].Message.Content), nil
	})
}

// Anthropic Messages API
func (g *Generator) callAnthropic(ctx context.Context, userMsg string) (string, error) {
	baseURL := g.cfg.BaseURL
	if baseURL == "" {
		baseURL = "https://api.anthropic.com/v1"
	}
	model := g.cfg.Model
	if model == "" {
		model = "claude-3-5-sonnet-20241022"
	}

	reqBody := map[string]interface{}{
		"model":      model,
		"max_tokens": 4096,
		"system":     g.sysPrompt(""),
		"messages": []map[string]string{
			{"role": "user", "content": userMsg},
		},
	}

	return g.postJSONWithHeader(ctx, baseURL+"/messages", reqBody,
		map[string]string{
			"x-api-key":         g.cfg.APIKey,
			"anthropic-version": "2023-06-01",
		},
		func(body []byte) (string, error) {
			var resp struct {
				Content []struct {
					Type string `json:"type"`
					Text string `json:"text"`
				} `json:"content"`
			}
			if err := json.Unmarshal(body, &resp); err != nil {
				return "", err
			}
			for _, c := range resp.Content {
				if c.Type == "text" {
					return cleanCode(c.Text), nil
				}
			}
			return "", fmt.Errorf("no text in anthropic response")
		})
}

// Ollama (local)
func (g *Generator) callOllama(ctx context.Context, userMsg string) (string, error) {
	baseURL := g.cfg.BaseURL
	if baseURL == "" {
		baseURL = "http://localhost:11434"
	}
	model := g.cfg.Model
	if model == "" {
		model = "codellama"
	}

	fullMsg := g.sysPrompt("") + "\n\n" + userMsg
	reqBody := map[string]interface{}{
		"model":  model,
		"prompt": fullMsg,
		"stream": false,
	}
	return g.postJSON(ctx, baseURL+"/api/generate", reqBody, func(body []byte) (string, error) {
		var resp struct {
			Response string `json:"response"`
		}
		if err := json.Unmarshal(body, &resp); err != nil {
			return "", err
		}
		return cleanCode(resp.Response), nil
	})
}

// postJSON helper
func (g *Generator) postJSON(ctx context.Context, url string, body interface{}, parse func([]byte) (string, error)) (string, error) {
	return g.postJSONWithHeader(ctx, url, body, nil, parse)
}

func (g *Generator) postJSONWithHeader(ctx context.Context, url string, body interface{}, extraHeaders map[string]string, parse func([]byte) (string, error)) (string, error) {
	b, err := json.Marshal(body)
	if err != nil {
		return "", err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(b))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	if g.cfg.APIKey != "" && g.cfg.Provider != "anthropic" {
		req.Header.Set("Authorization", "Bearer "+g.cfg.APIKey)
	}
	for k, v := range extraHeaders {
		req.Header.Set(k, v)
	}

	resp, err := g.client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("LLM API error %d: %s", resp.StatusCode, string(respBody))
	}
	return parse(respBody)
}

// cleanCode strips markdown fences if the LLM wrapped output in them.
func cleanCode(s string) string {
	s = strings.TrimSpace(s)
	// strip ```go ... ``` or ``` ... ```
	for _, fence := range []string{"```go\n", "```\n"} {
		if strings.HasPrefix(s, fence) {
			s = strings.TrimPrefix(s, fence)
			if idx := strings.LastIndex(s, "```"); idx >= 0 {
				s = s[:idx]
			}
			s = strings.TrimSpace(s)
		}
	}
	return s
}

// APIKeyFromEnv is a helper to read the API key from env if not set in config.
func APIKeyFromEnv(provider string) string {
	switch strings.ToLower(provider) {
	case "anthropic":
		return os.Getenv("ANTHROPIC_API_KEY")
	default:
		return os.Getenv("OPENAI_API_KEY")
	}
}
