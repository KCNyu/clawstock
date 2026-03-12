# testgen — 多语言代码仓库单测自动补全服务

## 背景与目标

构建一个可独立部署的全栈服务：给定一个代码仓库地址，自动分析代码、生成单元测试、验证通过后提 PR，并通过 Web Dashboard 实时观测任务进度。

核心约束：
- 只新增测试文件，绝不修改任何源码
- 架构与语言解耦，通过 Language Adapter 支持任意语言
- 当前优先实现 Go adapter，但所有接口按多语言设计

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
- `go test -coverprofile` 获取当前覆盖率
- 输出每个文件的 `{修改次数, 当前覆盖率}`

**② testability — 可测性诊断**
- 用语言对应的 AST 工具扫描每个函数
- 打 pure_func / interface_dep / concrete_dep / untestable 标签

**③ profiler — 项目画像提取**
- 分析依赖文件（go.mod / package.json / requirements.txt）
- 找 3-5 个现有测试文件作为风格样本
- 输出 ProjectProfile，注入每次 LLM 调用

**输出：** `{artifact_dir}/stage1_analysis.json` + `analysis_report.md`

### Stage 2：测试计划

- 按 priority 降序排列函数
- 按 package/module 分组（同组串行，不同组并行）
- 根据 testability 决定 generation_level
- 根据 `review_mode` 决定是否暂停等待 approve

**输出：** `{artifact_dir}/stage2_plan.json`

### Stage 3：单测生成（Worker Pool 并行）

**Prompt 结构：**

```
System:
[通用基础]
你是单元测试专家。只生成测试文件，不修改源码。
输出完整可运行的测试文件，不要用 markdown 代码块包裹。

[语言专用模板，从 prompt/templates/{language}.tmpl 读取]
语言：{language} {version}
测试框架：{test_framework}
Mock 框架：{mock_framework}
{语言特定约束...}

[项目约定]
参考以下现有测试的风格：
{project_profile.example_test_snippets}

User:
## 待测函数
文件：{file_path}
{sibling_types}
函数代码：
{body}

## 同包已有测试（风格参考，不要重复）
{existing_tests}

## 要求
覆盖：happy path + 边界值 + 错误返回 + 主要分支

[fix loop 时追加]
## 上次尝试的错误，请修复：
{error_output}
```

**Fix Loop（最多 3 次）：**
1. 写入测试文件
2. 编译检查（adapter.Build）
3. 失败 → 提取错误 → 带错误重新生成
4. 编译通过 → 运行测试（adapter.RunTests）
5. 失败 → 提取失败信息 → 带错误修复
6. 全部失败 → 删除文件，status=failed，记录 DB

**输出：** 各包下的测试文件 + `{artifact_dir}/stage3_results.json`

### Stage 4：AI Review + Mutation Test（并行，可配置开关）

**AI Review：**
- 对每个生成的测试文件调用 LLM 检查断言有效性、mock 正确性、错误路径覆盖
- 输出每个测试函数评分（1-5）+ 改进建议
- 不自动修改，只输出报告

**Mutation Test（默认关）：**
- Go：使用 gremlins
- 只针对本次新生成测试的函数跑
- 输出 killed vs survived 比例

**输出：** `{artifact_dir}/stage4_report.json` + `review_report.md` + `mutation_report.md`

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

**第一步（跑通最小闭环）：**
1. config 加载 + MySQL 连接 + 建表
2. HTTP server + 基础路由
3. Language Adapter 接口定义 + Go Adapter（AST 解析 + 可测性标签）
4. Stage 3：LLM 调用 + 编译运行验证 + fix loop
5. 写测试文件 + 记录 DB

**第二步（完整后端流程）：**
6. Worker Pool + Job 队列
7. Stage 1：git 热点 + 项目画像提取
8. Stage 2：测试计划生成
9. SSE 实时日志推送
10. 断点续跑（服务重启从 DB 恢复）
11. GitHub PR 自动创建

**第三步（前端 + 质量）：**
12. React Dashboard + Repos + JobList 页面
13. JobDetail 页面（重点：实时日志 + 函数结果表格）
14. Stage 4：AI Review
15. Rate limit + 指数退避
16. Python Adapter（验证多语言架构）
17. Stage 4：Mutation test（可选）

---

## 关键约束（必须遵守）

1. **所有语言相关逻辑只能在 `adapter/` 目录**，`pipeline/` 和 `worker/` 不允许出现任何语言特定代码
2. **测试文件命名由 adapter 决定**，core 层不 hardcode 任何文件名模式
3. **生成文件命名**：`{原文件名}_testgen_test.go`（Go），不覆盖原有 `_test.go`
4. **幂等**：同函数已有测试 → 跳过
5. **失败 Revert**：fix loop 耗尽 → 删文件，不留编译错误在仓库里
6. **不改源码**：除非显式配置 `generation_level: limited_refactor`
7. **按 package 串行**：同一 package 内函数串行处理，不同 package 可并行

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
