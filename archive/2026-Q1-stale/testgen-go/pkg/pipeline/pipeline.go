// Package pipeline is the async orchestrator.
// Design reference:
//   - ByteDance: 异步多阶段 Pipeline (被测代码分析 → Prompt组装 → 生成 → 智能修复)
//   - Meituan: 安全网策略 (存量代码先补测试再改代码)
//   - JD: 存量/增量分级 + 工具辅助
package pipeline

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"

	"github.com/testgen-go/pkg/analyzer"
	"github.com/testgen-go/pkg/generator"
	"github.com/testgen-go/pkg/validator"
)

// Config is the top-level pipeline configuration.
type Config struct {
	RepoPath    string         `yaml:"repo_path"`
	Workers     int            `yaml:"workers"`
	MaxRetries  int            `yaml:"max_retries"`
	MinPriority float64        `yaml:"min_priority"` // skip functions with priority < this
	TargetCov   float64        `yaml:"target_coverage"` // stop when whole-repo coverage exceeds this (%)
	StatePath   string         `yaml:"state_path"`  // path to persist state JSON
	LLM         generator.Config `yaml:"llm"`
	// optional: only process these package paths (relative)
	Packages []string `yaml:"packages"`
}

// State is persisted to disk so the pipeline can resume.
type State struct {
	Processed map[string]ProcessedResult `json:"processed"` // key = filePath::FuncName
	StartedAt time.Time                  `json:"started_at"`
	UpdatedAt time.Time                  `json:"updated_at"`
}

type ProcessedResult struct {
	Status        string    `json:"status"`   // "passed" | "failed" | "skipped"
	TestFile      string    `json:"test_file"`
	CoverageDelta float64   `json:"coverage_delta"`
	Attempts      int       `json:"attempts"`
	Error         string    `json:"error,omitempty"`
	At            time.Time `json:"at"`
}

// Pipeline is the main async engine.
type Pipeline struct {
	cfg       Config
	analyzer  *analyzer.Analyzer
	generator *generator.Generator
	validator *validator.Validator
	state     *State
	stateMu   sync.Mutex
	logger    *slog.Logger
	metrics   Metrics
	metricsMu sync.Mutex
}

// Metrics tracks progress.
type Metrics struct {
	Total     int
	Done      int
	Passed    int
	Failed    int
	Skipped   int
	StartCov  float64
	CurrentCov float64
}

func New(cfg Config) *Pipeline {
	if cfg.Workers == 0 {
		cfg.Workers = 4
	}
	if cfg.MaxRetries == 0 {
		cfg.MaxRetries = 3
	}
	if cfg.StatePath == "" {
		cfg.StatePath = filepath.Join(cfg.RepoPath, ".testgen-state.json")
	}

	apiKey := cfg.LLM.APIKey
	if apiKey == "" {
		apiKey = generator.APIKeyFromEnv(cfg.LLM.Provider)
	}
	cfg.LLM.APIKey = apiKey

	p := &Pipeline{
		cfg:       cfg,
		analyzer:  analyzer.New(cfg.RepoPath),
		generator: generator.New(cfg.LLM),
		validator: validator.New(cfg.RepoPath, cfg.MaxRetries),
		logger:    slog.Default(),
	}
	p.state = p.loadState()
	return p
}

// Run is the main entry point. It runs until ctx is cancelled or target coverage reached.
func (p *Pipeline) Run(ctx context.Context) error {
	p.logger.Info("testgen pipeline starting", "repo", p.cfg.RepoPath, "workers", p.cfg.Workers)

	// 1. Measure baseline coverage
	baseCov, err := p.analyzer.MeasureTotalCoverage()
	if err != nil {
		p.logger.Warn("could not measure baseline coverage", "err", err)
	}
	p.metricsMu.Lock()
	p.metrics.StartCov = baseCov
	p.metrics.CurrentCov = baseCov
	p.metricsMu.Unlock()
	p.logger.Info("baseline coverage", "pct", fmt.Sprintf("%.1f%%", baseCov))

	if p.cfg.TargetCov > 0 && baseCov >= p.cfg.TargetCov {
		p.logger.Info("already at target coverage, nothing to do")
		return nil
	}

	// 2. Analyze the repo
	p.logger.Info("analyzing repository...")
	fns, err := p.analyzer.Analyze()
	if err != nil {
		return fmt.Errorf("analyze: %w", err)
	}

	// 3. Filter + prioritize
	queue := p.buildQueue(fns)
	p.metricsMu.Lock()
	p.metrics.Total = len(queue)
	p.metricsMu.Unlock()
	p.logger.Info("functions queued", "count", len(queue))

	// 4. Dispatch to worker pool
	taskCh := make(chan *analyzer.FunctionInfo, len(queue))
	for _, fn := range queue {
		taskCh <- fn
	}
	close(taskCh)

	var wg sync.WaitGroup
	for i := 0; i < p.cfg.Workers; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			p.worker(ctx, workerID, taskCh)
		}(i)
	}

	// 5. Progress ticker
	done := make(chan struct{})
	go p.progressTicker(ctx, done)

	wg.Wait()
	close(done)

	// 6. Final coverage
	finalCov, _ := p.analyzer.MeasureTotalCoverage()
	p.logger.Info("pipeline complete",
		"start_cov", fmt.Sprintf("%.1f%%", baseCov),
		"final_cov", fmt.Sprintf("%.1f%%", finalCov),
		"delta", fmt.Sprintf("+%.1f%%", finalCov-baseCov),
		"passed", p.metrics.Passed,
		"failed", p.metrics.Failed,
	)
	return nil
}

// worker processes functions from taskCh until done.
func (p *Pipeline) worker(ctx context.Context, id int, taskCh <-chan *analyzer.FunctionInfo) {
	for fn := range taskCh {
		select {
		case <-ctx.Done():
			return
		default:
		}

		key := stateKey(fn)
		if _, done := p.getProcessed(key); done {
			p.incMetric("skipped")
			continue
		}

		p.logger.Info("processing", "worker", id, "func", fn.FuncName, "pkg", fn.PackagePath)
		res := p.process(ctx, fn)
		p.saveProcessed(key, res)

		if res.Status == "passed" {
			p.incMetric("passed")
		} else if res.Status == "skipped" {
			p.incMetric("skipped")
		} else {
			p.incMetric("failed")
		}
		p.incMetric("done")
	}
}

// process runs the full generate → validate → fix loop for one function.
func (p *Pipeline) process(ctx context.Context, fn *analyzer.FunctionInfo) ProcessedResult {
	res := ProcessedResult{At: time.Now()}

	existingTests := analyzer.ExistingTestsInDir(filepath.Dir(fn.FilePath))

	var fixHint string
	var testFile string

	for attempt := 1; attempt <= p.cfg.MaxRetries+1; attempt++ {
		res.Attempts = attempt

		// generate
		code, err := p.generator.GenerateTests(ctx, fn, existingTests, fixHint)
		if err != nil {
			p.logger.Warn("generation error", "func", fn.FuncName, "err", err)
			if ctx.Err() != nil {
				res.Status = "skipped"
				res.Error = "context cancelled"
				return res
			}
			time.Sleep(time.Duration(attempt) * 2 * time.Second) // backoff
			continue
		}

		// validate
		validResult, tf, err := p.validator.WriteAndTest(ctx, fn, code)
		if tf != "" {
			testFile = tf
		}
		if err != nil {
			p.logger.Warn("validator error", "func", fn.FuncName, "err", err)
			continue
		}

		if validResult.Passed {
			p.logger.Info("✓ tests passed", "func", fn.FuncName, "delta", fmt.Sprintf("+%.1f%%", validResult.CoverageDelta))
			res.Status = "passed"
			res.TestFile = testFile
			res.CoverageDelta = validResult.CoverageDelta
			return res
		}

		// extract hint for next attempt
		fixHint = validator.ExtractFixHint(validResult)
		p.logger.Info("✗ attempt failed, will retry",
			"func", fn.FuncName,
			"attempt", attempt,
			"hint", shortHint(fixHint),
		)
	}

	// all retries exhausted → revert
	if testFile != "" {
		p.validator.RevertTestFile(testFile)
	}
	res.Status = "failed"
	res.Error = fixHint
	return res
}

// buildQueue filters and sorts functions by priority.
func (p *Pipeline) buildQueue(fns []*analyzer.FunctionInfo) []*analyzer.FunctionInfo {
	var queue []*analyzer.FunctionInfo
	for _, fn := range fns {
		// skip if already processed successfully
		if r, ok := p.getProcessed(stateKey(fn)); ok && r == "passed" {
			continue
		}
		// skip trivial (getters, init, etc.) unless they're totally uncovered
		if len(fn.Body) < 40 {
			continue
		}
		fn.Priority = analyzer.ComputePriority(fn)
		if fn.Priority < p.cfg.MinPriority {
			continue
		}
		// package filter
		if len(p.cfg.Packages) > 0 && !inList(fn.PackagePath, p.cfg.Packages) {
			continue
		}
		queue = append(queue, fn)
	}
	// sort descending by priority
	sort.Slice(queue, func(i, j int) bool {
		return queue[i].Priority > queue[j].Priority
	})
	return queue
}

// ──────────────────────────────────────────────
// State persistence
// ──────────────────────────────────────────────

func (p *Pipeline) loadState() *State {
	s := &State{
		Processed: make(map[string]ProcessedResult),
		StartedAt: time.Now(),
	}
	data, err := os.ReadFile(p.cfg.StatePath)
	if err != nil {
		return s
	}
	if err := json.Unmarshal(data, s); err != nil {
		return s
	}
	p.logger.Info("resumed from state", "processed", len(s.Processed))
	return s
}

func (p *Pipeline) saveState() {
	p.state.UpdatedAt = time.Now()
	data, _ := json.MarshalIndent(p.state, "", "  ")
	os.WriteFile(p.cfg.StatePath, data, 0644)
}

func (p *Pipeline) saveProcessed(key string, res ProcessedResult) {
	p.stateMu.Lock()
	p.state.Processed[key] = res
	p.stateMu.Unlock()
	p.saveState()
}

func (p *Pipeline) getProcessed(key string) (string, bool) {
	p.stateMu.Lock()
	defer p.stateMu.Unlock()
	r, ok := p.state.Processed[key]
	if !ok {
		return "", false
	}
	return r.Status, true
}

func stateKey(fn *analyzer.FunctionInfo) string {
	return fn.FilePath + "::" + fn.FuncName
}

// ──────────────────────────────────────────────
// Metrics helpers
// ──────────────────────────────────────────────

func (p *Pipeline) incMetric(field string) {
	p.metricsMu.Lock()
	defer p.metricsMu.Unlock()
	switch field {
	case "done":
		p.metrics.Done++
	case "passed":
		p.metrics.Passed++
	case "failed":
		p.metrics.Failed++
	case "skipped":
		p.metrics.Skipped++
	}
}

func (p *Pipeline) progressTicker(ctx context.Context, done chan struct{}) {
	t := time.NewTicker(30 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-done:
			return
		case <-ctx.Done():
			return
		case <-t.C:
			p.metricsMu.Lock()
			m := p.metrics
			p.metricsMu.Unlock()
			p.logger.Info("progress",
				"done", fmt.Sprintf("%d/%d", m.Done, m.Total),
				"passed", m.Passed,
				"failed", m.Failed,
			)
		}
	}
}

// GetMetrics returns a snapshot of current metrics.
func (p *Pipeline) GetMetrics() Metrics {
	p.metricsMu.Lock()
	defer p.metricsMu.Unlock()
	return p.metrics
}

// helpers

func shortHint(s string) string {
	if len(s) > 120 {
		return s[:120] + "..."
	}
	return s
}

func inList(s string, list []string) bool {
	for _, v := range list {
		if v == s {
			return true
		}
	}
	return false
}
