// testgen: async Go unit test generation pipeline
// Usage: testgen --repo /path/to/repo [--workers 4] [--target-cov 80]
package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/testgen-go/pkg/generator"
	"github.com/testgen-go/pkg/pipeline"
)

func main() {
	var (
		repoPath   = flag.String("repo", ".", "path to Go repository root")
		workers    = flag.Int("workers", 4, "number of parallel workers")
		retries    = flag.Int("retries", 3, "max LLM fix retries per function")
		targetCov  = flag.Float64("target-cov", 80.0, "stop when overall coverage exceeds this %%")
		minPrio    = flag.Float64("min-priority", 0.3, "skip functions with priority below this")
		statePath  = flag.String("state", "", "state file path (defaults to <repo>/.testgen-state.json)")
		pkg        = flag.String("pkg", "", "only process this package path (relative), comma-separated")

		// LLM flags
		provider = flag.String("llm-provider", "openai", "LLM provider: openai | anthropic | ollama")
		model    = flag.String("llm-model", "", "model name (default per provider)")
		apiKey   = flag.String("llm-key", "", "API key (falls back to OPENAI_API_KEY / ANTHROPIC_API_KEY env)")
		baseURL  = flag.String("llm-url", "", "custom LLM base URL")
	)
	flag.Parse()

	// structured logger
	logger := slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	key := *apiKey
	if key == "" {
		key = generator.APIKeyFromEnv(*provider)
	}
	if key == "" && *provider != "ollama" {
		fmt.Fprintf(os.Stderr, "error: LLM API key required. Set OPENAI_API_KEY / ANTHROPIC_API_KEY or use --llm-key\n")
		os.Exit(1)
	}

	cfg := pipeline.Config{
		RepoPath:    *repoPath,
		Workers:     *workers,
		MaxRetries:  *retries,
		TargetCov:   *targetCov,
		MinPriority: *minPrio,
		StatePath:   *statePath,
		LLM: generator.Config{
			Provider: *provider,
			Model:    *model,
			APIKey:   key,
			BaseURL:  *baseURL,
		},
	}

	if *pkg != "" {
		cfg.Packages = splitComma(*pkg)
	}

	// graceful shutdown on SIGINT/SIGTERM
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	p := pipeline.New(cfg)
	if err := p.Run(ctx); err != nil {
		slog.Error("pipeline error", "err", err)
		os.Exit(1)
	}

	m := p.GetMetrics()
	fmt.Printf("\n=== Summary ===\n")
	fmt.Printf("Total:   %d functions analyzed\n", m.Total)
	fmt.Printf("Passed:  %d tests generated & verified\n", m.Passed)
	fmt.Printf("Failed:  %d could not be fixed (skipped)\n", m.Failed)
	fmt.Printf("Coverage before: %.1f%%\n", m.StartCov)
	fmt.Printf("Coverage after:  %.1f%%\n", m.CurrentCov)
}

func splitComma(s string) []string {
	var result []string
	for _, p := range splitStr(s, ",") {
		if p != "" {
			result = append(result, p)
		}
	}
	return result
}

func splitStr(s, sep string) []string {
	var out []string
	start := 0
	for i := 0; i < len(s); i++ {
		if string(s[i]) == sep {
			out = append(out, s[start:i])
			start = i + 1
		}
	}
	out = append(out, s[start:])
	return out
}
