# testgen — 多语言代码仓库单测自动补全服务

## 背景与目标

构建一个可独立部署的全栈服务：给定一个代码仓库地址，自动分析代码、生成单元测试、验证通过后提 PR，并通过 Web Dashboard 实时观测任务进度。

核心约束：
- 只新增测试文件，绝不修改任何源码
- 架构与语言解耦，通过 Language Adapter 支持任意语言
- 当前优先实现 Go adapter，但所有接口按多语言设计

## 参考实践（已验证可行）

本方案综合了以下业界实践：
- **Meta TestGen-LLM**：多阶段 Pipeline + fix loop，生产环境覆盖率 25% → 73%
- **字节跳动**：智能修复策略（错误分类 + 定向修复），而非盲目重试
- **Codium Cover-Agent**：开源多语言支持，Prompt 模板可直接参考
- **Google AlphaCode**：多候选生成 + mutation testing 质量评估

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端服务 | Go 1.21+ |
| 数据库 | MySQL 8.0 |
| 前端 | React 18 + TypeScript + Vite |
| UI 组件库 | Ant Design 5 |
| 图表 | Recharts |
| 容器化 | Docker + docker-compose |

---

## 整体架构

```
┌─────────────────────────────────────────────────┐
│              React Dashboard                     │
│  仓库管理 / 任务列表 / 实时进度 / 覆盖率趋势图      │
└────────────────────┬────────────────────────────┘
                     │ HTTP / SSE
┌────────────────────▼────────────────────────────┐
│              Go HTTP API Server                  │
│   /api/repos  /api/jobs  /api/events (SSE)       │
├─────────────────────────────────────────────────┤
│              Pipeline Engine（语言无关）           │
│   Stage1:Analyze → Stage2:Plan →                 │
│   Stage3:Generate → Stage4:Review                │
├─────────────────────────────────────────────────┤
│           Language Adapter（语言相关）             │
│  ┌────────┐ ┌────────┐ ┌────────┐               │
│  │  Go    │ │ Python │ │  TS    │  ...           │
│  └────────┘ └────────┘ └────────┘               │
├─────────────────────────────────────────────────┤
│              MySQL 8.0                           │
└─────────────────────────────────────────────────┘
```

---

## 项目目录结构

```
testgen/
├── backend/
│   ├── cmd/server/main.go
│   ├── api/
│   │   ├── repos.go
│   │   ├── jobs.go
│   │   ├── events.go          # SSE 实时推送
│   │   └── webhooks.go
│   ├── worker/
│   │   ├── pool.go
│   │   └── runner.go
│   ├── pipeline/
│   │   ├── engine.go
│   │   ├── stage1_analyze.go
│   │   ├── stage2_plan.go
│   │   ├── stage3_generate.go
│   │   └── stage4_review.go
│   ├── adapter/
│   │   ├── adapter.go         # interface 定义
│   │   ├── registry.go        # 语言自动检测 + 注册表
│   │   ├── go/
│   │   │   ├── adapter.go
│   │   │   ├── parser.go      # go/ast 解析
│   │   │   ├── coverage.go    # go test -cover
│   │   │   └── profiler.go    # go.mod + 测试风格提取
│   │   ├── python/
│   │   │   └── adapter.go     # 预留
│   │   └── typescript/
│   │       └── adapter.go     # 预留
│   ├── llm/
│   │   ├── client.go          # 统一 LLM 接口
│   │   ├── openai.go
│   │   ├── anthropic.go
│   │   └── ollama.go
│   ├── prompt/
│   │   ├── builder.go
│   │   └── templates/
│   │       ├── system_base.tmpl
│   │       ├── go.tmpl
│   │       ├── python.tmpl
│   │       └── typescript.tmpl
│   ├── db/
│   │   ├── mysql.go           # 连接 + migrate
│   │   ├── schema.sql
│   │   └── store.go
│   ├── notifier/
│   │   ├── github_pr.go
│   │   └── webhook.go
│   ├── config/config.go
│   └── go.mod
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx      # 总览：覆盖率趋势、任务统计
│   │   │   ├── Repos.tsx          # 仓库列表 + 注册
│   │   │   ├── JobList.tsx        # 任务列表
│   │   │   └── JobDetail.tsx      # 任务详情 + 实时日志
│   │   ├── components/
│   │   │   ├── CoverageChart.tsx  # 覆盖率趋势折线图
│   │   │   ├── StageTimeline.tsx  # Stage 进度时间轴
│   │   │   ├── FunctionTable.tsx  # 函数生成结果表格
│   │   │   └── LogStream.tsx      # 实时日志流（SSE）
│   │   ├── api/
│   │   │   └── client.ts          # API 请求封装
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── config.example.yaml
```

---

## 数据库设计（MySQL 8.0）

```sql
CREATE TABLE repos (
    id          VARCHAR(36) PRIMARY KEY,
    url         VARCHAR(512) NOT NULL,
    branch      VARCHAR(128) DEFAULT 'main',
    language    VARCHAR(32),
    config_json JSON,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE jobs (
    id                VARCHAR(36) PRIMARY KEY,
    repo_id           VARCHAR(36) NOT NULL,
    trigger_type      VARCHAR(32),        -- manual/webhook/cron
    status            VARCHAR(32),        -- queued/running/waiting_review/done/failed
    current_stage     VARCHAR(32),
    baseline_coverage DECIMAL(5,2),
    final_coverage    DECIMAL(5,2),
    artifact_dir      VARCHAR(512),
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_repo_id (repo_id),
    INDEX idx_status (status)
);

CREATE TABLE job_stages (
    id            VARCHAR(36) PRIMARY KEY,
    job_id        VARCHAR(36) NOT NULL,
    stage_name    VARCHAR(32),            -- analyze/plan/generate/review
    status        VARCHAR(32),            -- pending/running/done/failed
    artifact_path VARCHAR(512),
    started_at    DATETIME,
    finished_at   DATETIME,
    error_msg     TEXT,
    INDEX idx_job_id (job_id)
);

CREATE TABLE generated_tests (
    id             VARCHAR(36) PRIMARY KEY,
    job_id         VARCHAR(36) NOT NULL,
    file_path      VARCHAR(512),
    func_name      VARCHAR(256),
    testability    VARCHAR(32),           -- pure_func/interface_dep/concrete_dep/untestable
    priority       DECIMAL(6,3),
    status         VARCHAR(32),           -- passed/failed/skipped
    attempts       INT DEFAULT 0,
    test_file_path VARCHAR(512),
    coverage_delta DECIMAL(5,2),
    error_msg      TEXT,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_job_id (job_id),
    INDEX idx_status (status)
);

-- 实时日志（SSE 推送用）
CREATE TABLE job_logs (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    job_id     VARCHAR(36) NOT NULL,
    level      VARCHAR(16),              -- info/warn/error
    stage      VARCHAR(32),
    message    TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_job_id_created (job_id, created_at)
);

-- 覆盖率历史（Dashboard 趋势图用）
CREATE TABLE coverage_history (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    repo_id    VARCHAR(36) NOT NULL,
    job_id     VARCHAR(36) NOT NULL,
    coverage   DECIMAL(5,2),
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_repo_id (repo_id)
);
```

---

## Language Adapter 接口

```go
type LanguageAdapter interface {
    // 元信息
    Name() string
    FileExtensions() []string
    TestFilePattern() string
    TestFilePath(srcFile string) string

    // 分析
    ParseFunctions(filePath string) ([]*FunctionInfo, error)
    DetectTestability(fn *FunctionInfo) Testability
    MeasureCoverage(repoPath string) (*CoverageReport, error)
    ExtractProjectProfile(repoPath string) (*ProjectProfile, error)

    // 验证
    Build(repoPath, pkgPath string) error
    RunTests(repoPath, pkgPath, filter string) (*TestResult, error)

    // 文件合并
    MergeTestFile(existingPath, newCode, funcName string) (string, error)
}
```

### 语言自动检测（adapter/registry.go）

```
检测顺序（找到即返回）：
1. go.mod              → Go
2. tsconfig.json       → TypeScript
3. package.json        → JavaScript
4. pyproject.toml /
   requirements.txt /
   setup.py            → Python
5. pom.xml /
   build.gradle        → Java
6. Cargo.toml          → Rust
7. 统计文件扩展名占比   → 取最多的那种
```

---

## 通用数据结构

### FunctionInfo

```go
type FunctionInfo struct {
    FilePath        string
    Language        string
    PackageName     string
    PackagePath     string
    FuncName        string
    IsExported      bool
    Receiver        string
    Signature       string
    Body            string
    Imports         []string
    SiblingTypes    string
    Testability     Testability
    Complexity      int
    HotspotScore    float64
    Priority        float64
    HasExistingTest bool
}
```

### ProjectProfile

```go
type ProjectProfile struct {
    Language             string
    LanguageVersion      string
    ModuleName           string
    TestFramework        string
    MockFramework        string
    HTTPFramework        string
    DBFramework          string
    BuildTool            string
    ExampleTestSnippets  []string  // 3-5 个现有测试文件内容
    Conventions          map[string]string
}
```

### Testability 枚举

```
pure_func      — 无副作用，无外部依赖
interface_dep  — 依赖是接口类型，可 mock
concrete_dep   — 依赖具体实现（DB/HTTP client 等）
untestable     — init/全局状态/无返回值副作用
```

### 优先级公式

```
priority = hotspot(0-1) × (1 - coverage) × complexity_factor × testability_factor

complexity_factor:  行数>100 → 3.0, >30 → 2.0, else 1.0
testability_factor: pure_func → 1.5, interface_dep → 1.0,
                    concrete_dep → 0.5, untestable → 0
```

---

## Pipeline 各阶段

### Stage 1：分析（三个子任务并行）

**① scanner — git 热点分析**
- `git log --since=90d --name-only --pretty=format:` 统计文件修改频率
- 语言对应的覆盖率工具获取当前覆盖率（go test -cover / pytest-cov / jest --coverage）
- 输出每个文件的 `{修改次数, 当前覆盖率}`

**② testability — 可测性诊断（参考 Diffblue Cover 的分析方法）**

各语言 AST 解析方案：

| 语言 | 解析工具 | 调用方式 |
|------|---------|---------|
| Go | `go/ast` 标准库 | 原生调用 |
| Python | `adapter/python/scripts/parse_funcs.py` | exec 调 python3 脚本 |
| TypeScript | `adapter/typescript/scripts/parse_funcs.js` | exec 调 node 脚本（用 @typescript-eslint/parser）|
| Java | `adapter/java/scripts/parse_funcs.jar` | exec 调 java -jar |
| 其他语言 | tree-sitter CLI | exec 调 `tree-sitter parse --json` 兜底 |

每个 Adapter 自带解析脚本，统一输出 `FunctionInfo[]` JSON，接口完全一致。

可测性标签打法：
- `pure_func`：无 IO、无全局变量读写、无外部调用
- `interface_dep`：依赖类型是接口/抽象类（Go interface / Python Protocol / Java interface）
- `concrete_dep`：依赖具体实现（*gorm.DB / redis.Client / HttpClient 等）
- `untestable`：init 函数、全局变量初始化、无返回值纯副作用

**③ profiler — 项目画像提取（参考 Meta TestGen 的上下文构建）**
- 分析依赖文件（go.mod / package.json / requirements.txt / pom.xml）
- 找 3-5 个现有测试文件作为风格样本（优先选覆盖率高的包）
- 提取测试命名规范、断言风格、mock 初始化模式
- 输出 ProjectProfile，注入每次 LLM 调用的 System Prompt

**输出：** `{artifact_dir}/stage1_analysis.json` + `analysis_report.md`

### Stage 2：测试计划

- 按 priority 降序排列函数
- 按 package/module 分组（同组串行，不同组并行）
- 根据 testability 决定 generation_level
- 根据 `review_mode` 决定是否暂停等待 approve

**输出：** `{artifact_dir}/stage2_plan.json`

### Stage 3：单测生成（Worker Pool 并行）

**生成策略（借鉴 Meta TestGen）：**
- 每个函数生成 **2 个候选测试**（提高首次成功率）
- 编译 + 运行验证，取第一个通过的
- 如果都失败，进入智能修复循环

**Prompt 结构（参考 Cover-Agent + Meta TestGen）：**

```
System:
你是单元测试专家，专注于生成高质量、可维护的单元测试。

核心原则：
1. 只生成测试文件，绝不修改源码
2. 测试必须能独立运行，不依赖外部服务
3. 使用项目已有的测试框架和 mock 库
4. 输出完整可编译的测试文件（包含 package 和 import）
5. 不要用 markdown 代码块包裹输出

语言：{language} {version}
测试框架：{test_framework}
Mock 框架：{mock_framework}

{语言特定约束，从 prompt/templates/{language}.tmpl 读取}

项目约定（参考这些现有测试的风格）：
{project_profile.example_test_snippets}

User:
## 待测函数上下文

文件路径：{file_path}
包名：{package_name}
导入路径：{package_path}

### 相关类型定义（同包）
```{language}
{sibling_types}
```

### 待测函数
```{language}
{signature}
{body}
```

### 函数依赖分析
- 外部依赖：{dependencies}  // 需要 mock 的接口/类
- 可测性：{testability}      // pure_func / interface_dep / concrete_dep

### 同包已有测试（风格参考，不要重复测试用例）
```{language}
{existing_tests}
```

## 生成要求

1. 覆盖场景：
   - Happy path（正常流程）
   - 边界值（空值、零值、极大值）
   - 错误返回（所有 error 分支）
   - 主要业务分支（if/switch 的各个 case）

2. 测试结构：
   - 使用 table-driven test 风格（如果适用）
   - 每个测试用例有清晰的名称描述场景
   - Setup → Execute → Assert 三段式

3. Mock 策略：
   - 对 {dependencies} 中的依赖使用 {mock_framework}
   - Mock 的行为要符合真实场景
   - 验证 mock 的调用次数和参数

请生成 **完整的测试文件**（包含 package、import、所有测试函数）。

[智能修复模式 - 仅在重试时追加]
## 上次尝试失败，错误分析：

错误类型：{error_type}  // import_error / type_error / logic_error / runtime_error
错误信息：
```
{error_output}
```

修复建议：
{fix_hint}  // 根据错误类型自动生成的修复提示
```

**智能修复策略（借鉴字节实践）：**

根据错误类型采用不同修复策略，而非盲目重试：

| 错误类型 | 识别特征 | 修复策略 | 最大重试 |
|---------|---------|---------|---------|
| **import_error** | `cannot find package` / `undefined: xxx` | 检查 go.mod，补全正确 import 路径 | 2 次 |
| **type_error** | `cannot use ... as type` / `type mismatch` | 检查函数签名，修正类型转换 | 2 次 |
| **mock_error** | `unexpected call` / `missing call` | 调整 mock 预期，补全缺失的 mock 设置 | 3 次 |
| **logic_error** | `assertion failed` / `got != want` | 重新分析函数逻辑，修正测试预期 | 2 次 |
| **runtime_error** | `panic` / `nil pointer` | 补全前置条件检查，初始化缺失依赖 | 1 次 |
| **timeout** | 测试超时 | 跳过，标记为 `needs_manual_review` | 0 次 |

**Fix Loop 流程：**

```
1. 生成 2 个候选测试（candidate_1, candidate_2）
   ↓
2. 并行编译验证
   ↓
   ├─ candidate_1 通过 → 采用，结束
   ├─ candidate_2 通过 → 采用，结束
   └─ 都失败 → 进入智能修复
       ↓
3. 错误分类（根据编译/运行输出自动识别错误类型）
   ↓
4. 生成 fix_hint（根据错误类型 + 错误信息）
   ↓
5. 带 fix_hint 重新生成（最多重试次数见上表）
   ↓
6. 仍失败 → 删除文件，status=failed，记录详细错误到 DB
```

**输出：** 各包下的测试文件 + `{artifact_dir}/stage3_results.json`

### Stage 4：质量评估（AI Review + Mutation Test 并行）

**AI Review（参考 Meta TestGen 的评估标准）：**

对每个生成的测试文件，调用 LLM 进行质量评估：

```
System:
你是测试代码审查专家，评估单元测试的质量。

评估维度（1-5 分）：
1. 断言有效性：断言是否真正验证了函数行为，而非永远为真
2. Mock 正确性：mock 的行为是否符合真实依赖的语义
3. 边界覆盖：是否覆盖了空值、零值、极端值等边界情况
4. 错误路径：是否测试了所有 error 返回分支
5. 可维护性：测试代码是否清晰、易读、易修改

User:
## 待测函数
{function_signature}
{function_body}

## 生成的测试代码
{generated_test_code}

## 请评估并输出 JSON：
{
  "overall_score": 4.2,
  "dimensions": {
    "assertion_validity": 5,
    "mock_correctness": 4,
    "boundary_coverage": 4,
    "error_path_coverage": 4,
    "maintainability": 4
  },
  "issues": [
    {
      "severity": "medium",
      "line": 42,
      "message": "mock 的返回值与真实场景不符，应该返回 error 而非 nil"
    }
  ],
  "suggestions": [
    "补充测试用例：当 userID 为空字符串时的行为",
    "mock 的 Times(1) 断言过于严格，建议改为 Times(AtLeast(1))"
  ]
}
```

**输出：** `{artifact_dir}/review_report.json` + `review_report.md`（人类可读）

---

**Mutation Testing（用现成工具，参考 AlphaCode）：**

| 语言 | 工具 | 安装 | 运行 |
|------|------|------|------|
| Go | **gremlins** | `go install github.com/go-gremlins/gremlins/cmd/gremlins@latest` | `gremlins unleash --tags=testgen` |
| Python | **mutmut** | `pip install mutmut` | `mutmut run --paths-to-mutate=src/` |
| TypeScript | **stryker** | `npm install -g @stryker-mutator/core` | `stryker run` |
| Java | **pitest** | Maven plugin | `mvn org.pitest:pitest-maven:mutationCoverage` |

**运行策略：**
- 只针对本次新生成测试的函数跑 mutation（不全量）
- 用 tag 或 filter 限定范围（如 Go 的 `//go:build testgen`）
- 超时设置：单个函数最多 5 分钟

**Mutation Score 计算：**
```
mutation_score = killed_mutants / total_mutants

killed   = 测试检测到的变异（好测试）
survived = 测试未检测到的变异（无效测试）
timeout  = 变异导致死循环（忽略）
```

**质量判断标准（参考 Meta TestGen）：**
- mutation_score >= 0.8：优秀，测试真正验证了逻辑
- 0.6 - 0.8：良好，可接受
- < 0.6：差，测试可能只是"跑通了"但没验证行为

**输出：** `{artifact_dir}/mutation_report.json`

```json
{
  "total_mutants": 47,
  "killed": 38,
  "survived": 7,
  "timeout": 2,
  "mutation_score": 0.81,
  "by_function": [
    {
      "func_name": "CreateUser",
      "mutants": 12,
      "killed": 10,
      "survived": 2,
      "score": 0.83,
      "survived_mutations": [
        {
          "type": "ConditionalsBoundary",
          "line": 45,
          "original": "if len(users) > 0",
          "mutated": "if len(users) >= 0",
          "reason": "测试未覆盖 len(users)==0 的边界"
        }
      ]
    }
  ]
}
```

**最终决策：**
- AI Review score < 3.0 或 mutation_score < 0.6 → 标记 `needs_improvement`，输出到报告供人工 review
- 否则 → 自动合并到 PR

---

## HTTP API

```
# 仓库管理
POST   /api/repos                    # 注册仓库 {url, branch?, language?}
GET    /api/repos                    # 列出所有仓库
GET    /api/repos/:id
DELETE /api/repos/:id

# 任务管理
POST   /api/jobs                     # 触发任务 {repo_id}
GET    /api/jobs                     # 任务列表（支持分页、状态过滤）
GET    /api/jobs/:id                 # 任务详情 + 各 stage 状态
POST   /api/jobs/:id/approve         # pause 模式下批准继续
POST   /api/jobs/:id/retry           # 重试失败任务
GET    /api/jobs/:id/report          # 完整报告 JSON

# 实时推送（SSE）
GET    /api/events/:job_id           # 订阅任务实时日志和进度

# Webhook
POST   /webhook/github               # GitHub push 事件自动触发

# Dashboard 数据
GET    /api/stats                    # 全局统计（总任务数、平均覆盖率提升等）
GET    /api/repos/:id/coverage-history  # 覆盖率历史趋势
```

---

## SSE 实时推送格式

前端通过 `GET /api/events/:job_id` 订阅，后端推送以下事件：

```
event: stage_update
data: {"stage": "generate", "status": "running", "progress": "12/47"}

event: function_done
data: {"func_name": "CreateUser", "status": "passed", "coverage_delta": 3.2, "attempts": 1}

event: log
data: {"level": "info", "stage": "generate", "message": "✓ CreateUser tests passed"}

event: job_done
data: {"status": "done", "baseline": 18.4, "final": 54.2, "delta": 35.8}
```

---

## React 前端页面设计

### Dashboard（总览页）
- 顶部卡片：总仓库数 / 本月任务数 / 平均覆盖率提升 / 成功率
- 覆盖率趋势折线图（Recharts）：各仓库近 30 天覆盖率变化
- 最近任务列表（状态 + 进度条）

### Repos（仓库管理页）
- 仓库列表表格：URL / 语言 / 最近任务状态 / 最新覆盖率
- 注册新仓库弹窗：填写 git URL、branch、language（可自动检测）
- 每行操作：触发任务 / 查看历史 / 删除

### JobList（任务列表页）
- 表格：任务 ID / 仓库 / 触发方式 / 状态 / 覆盖率变化 / 创建时间
- 状态筛选 + 分页
- 点击跳转详情

### JobDetail（任务详情页）—— 最重要的页面
- 顶部：仓库信息 + 覆盖率 before/after（大字显示）
- Stage 时间轴：4 个 Stage 的状态 + 耗时（Ant Design Steps 组件）
- 实时日志流（SSE）：滚动日志窗口，颜色区分 info/warn/error
- 函数生成结果表格：
  - 列：函数名 / 文件 / 可测性 / 优先级 / 状态 / 尝试次数 / 覆盖率提升
  - 状态用颜色标签：passed(绿) / failed(红) / skipped(灰)
  - 点击行展开：查看生成的测试代码 + 错误信息
- 底部操作：approve（pause 模式）/ retry / 查看 PR 链接

---

## 配置文件（config.yaml）

```yaml
server:
  port: 8080
  data_dir: ./data               # artifact 文件存储目录

database:
  host: localhost
  port: 3306
  name: testgen
  user: testgen
  password: ""                   # 从 DB_PASSWORD env 读
  max_open_conns: 20
  max_idle_conns: 5

worker:
  pool_size: 4
  max_retries: 3

pipeline:
  default_generation_level: standard   # no_side_effect | standard | limited
  default_target_coverage: 70
  default_review_mode: notify          # auto | pause | notify
  hotspot_window_days: 90

llm:
  provider: anthropic                  # openai | anthropic | ollama
  model: claude-3-5-sonnet-20241022
  api_key: ""                          # 从 ANTHROPIC_API_KEY env 读
  base_url: ""
  max_concurrent: 3                    # 并发 LLM 调用数
  timeout_seconds: 120

notifier:
  github_token: ""                     # 从 GITHUB_TOKEN env 读
  auto_create_pr: true
  pr_branch_prefix: "auto/testgen-"

adapters:
  go:
    go_binary: go
    gremlins_binary: gremlins          # mutation test，可选
  python:
    python_binary: python3
    pytest_binary: pytest
  typescript:
    node_binary: node
    jest_binary: npx jest
```

---

## docker-compose.yml

```yaml
version: '3.8'
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: testgen
      MYSQL_USER: testgen
      MYSQL_PASSWORD: testgen123
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./backend/db/schema.sql:/docker-entrypoint-initdb.d/schema.sql

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8080:8080"
    environment:
      DB_HOST: mysql
      DB_PASSWORD: testgen123
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      GITHUB_TOKEN: ${GITHUB_TOKEN}
    volumes:
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml
    depends_on:
      - mysql

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  mysql_data:
```

---

## 实现优先级（MVP 顺序）

**第一步（跑通最小闭环，参考 Cover-Agent）：**
1. config 加载 + MySQL 连接 + 建表
2. HTTP server + 基础路由
3. Language Adapter 接口定义 + Go Adapter（AST 解析 + 可测性标签）
4. Stage 3：LLM 调用（生成 2 个候选）+ 编译运行验证 + 智能修复
5. 写测试文件 + 记录 DB
6. 验证：用一个真实 Go 仓库跑通，生成至少 10 个测试

**第二步（完整后端流程，参考 Meta TestGen）：**
7. Worker Pool + Job 队列（BullMQ 或自实现）
8. Stage 1：git 热点 + 项目画像提取
9. Stage 2：测试计划生成（优先级排序 + 按 package 分组）
10. SSE 实时日志推送
11. 断点续跑（服务重启从 DB 恢复）
12. GitHub PR 自动创建（用 GitHub API）

**第三步（前端 + 质量，参考字节实践）：**
13. React Dashboard + Repos + JobList 页面
14. JobDetail 页面（重点：实时日志 + 函数结果表格 + 错误分类展示）
15. Stage 4：AI Review（评分 + 改进建议）
16. Stage 4：Mutation test（gremlins / mutmut，可配置开关）
17. Rate limit + 指数退避（防 LLM API 限流）
18. Python Adapter（验证多语言架构，参考 Cover-Agent 的 Python 实现）

**第四步（生产优化）：**
19. 错误分类统计（Dashboard 展示各类错误占比，指导 Prompt 优化）
20. A/B 测试框架（对比不同 Prompt 模板的效果）
21. 成本监控（LLM token 消耗 + 时间成本）
22. TypeScript Adapter（前端项目支持）

---

## 关键约束（必须遵守）

1. **所有语言相关逻辑只能在 `adapter/` 目录**，`pipeline/` 和 `worker/` 不允许出现任何语言特定代码
2. **测试文件命名由 adapter 决定**，core 层不 hardcode 任何文件名模式
3. **生成文件命名**：`{原文件名}_testgen_test.go`（Go），不覆盖原有 `_test.go`
4. **幂等**：同函数已有测试 → 跳过
5. **失败 Revert**：智能修复耗尽 → 删文件，不留编译错误在仓库里
6. **不改源码**：除非显式配置 `generation_level: limited_refactor`
7. **按 package 串行**：同一 package 内函数串行处理，不同 package 可并行
8. **错误必须分类**：所有失败都要记录错误类型（import/type/mock/logic/runtime），用于后续 Prompt 优化
9. **Mutation test 限定范围**：只跑本次新生成测试的函数，不全量跑（成本控制）
10. **质量门禁**：AI Review score < 3.0 或 mutation_score < 0.6 → 标记 `needs_improvement`，不自动合并

---

## 参考资源（实现时查阅）

| 资源 | 用途 |
|------|------|
| [Meta TestGen-LLM 论文](https://engineering.fb.com/2024/04/24/developer-tools/testgen-llm-automated-unit-test-generation/) | Prompt 工程 + 评估指标 |
| [Cover-Agent GitHub](https://github.com/Codium-ai/cover-agent) | 各语言 Prompt 模板 + fix loop 实现 |
| [字节 InfoQ 文章](https://xie.infoq.cn/article/ad6587864fafe6ba7d68a5c74) | 智能修复策略 + 错误分类 |
| [Diffblue Cover 白皮书](https://www.diffblue.com/resources/) | 可测性分析方法 |
| [gremlins 文档](https://github.com/go-gremlins/gremlins) | Go mutation testing |
| [mutmut 文档](https://mutmut.readthedocs.io/) | Python mutation testing |

---

## 本地启动

```bash
# 启动依赖
docker-compose up -d mysql

# 后端
cd backend
ANTHROPIC_API_KEY=sk-ant-xxx go run ./cmd/server

# 前端
cd frontend
npm install && npm run dev

# 或全部用 docker-compose
ANTHROPIC_API_KEY=sk-ant-xxx GITHUB_TOKEN=ghp-xxx docker-compose up
```

访问 http://localhost:3000 打开 Dashboard。

```bash
# 注册仓库
curl -X POST http://localhost:8080/api/repos \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/your-org/your-service", "branch": "main"}'

# 触发任务
curl -X POST http://localhost:8080/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "<上面返回的 id>"}'

# 查看进度（或直接看 Dashboard）
curl http://localhost:8080/api/jobs/<job_id>
```
