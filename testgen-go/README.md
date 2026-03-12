# testgen-go

> 异步 Go 历史服务单测补全 Pipeline  
> **核心约束：只生成 `_test.go`，绝不改动任何源码**

---

## 设计思路（参考大厂实践）

```
                    ┌─────────────────────────────────────────┐
                    │         testgen Pipeline                 │
                    │                                         │
  Go Repo ──────▶  │  Analyzer                               │
                    │    ↓ AST解析 + 覆盖率测量               │
                    │  Priority Queue                         │
                    │    ↓ 按优先级排序 (存量覆盖缺口优先)      │
                    │  Worker Pool (N并发)                    │
                    │    ↓                                    │
                    │  ┌─────────────────────────────────┐   │
                    │  │  每个Function的处理循环           │   │
                    │  │                                 │   │
                    │  │  1. Context Builder             │   │
                    │  │     函数签名 + 类型上下文        │   │
                    │  │     + 同包现有测试               │   │
                    │  │       ↓                        │   │
                    │  │  2. LLM Generator              │   │
                    │  │     生成 _test.go 代码          │   │
                    │  │       ↓                        │   │
                    │  │  3. Validator                  │   │
                    │  │     go build 编译检查           │   │
                    │  │     go test 运行验证            │   │
                    │  │       ↓ 失败                   │   │
                    │  │  4. Fix Loop (max 3次)         │   │
                    │  │     错误信息 → LLM修复          │   │
                    │  │       ↓ 仍失败                 │   │
                    │  │  5. Revert & Skip              │   │
                    │  └─────────────────────────────────┘   │
                    │    ↓                                    │
                    │  State (可续跑)                         │
                    │  Coverage Report                        │
                    └─────────────────────────────────────────┘
```

### 参考了哪些大厂思路

| 来源 | 借鉴点 |
|------|--------|
| **字节跳动** (QCon 2024) | 多阶段 Pipeline；「生成→编译→失败→修复」自动循环；存量+增量均支持 |
| **美团** (2025.12) | 存量代码先建「安全网」；测试不通过 = Revert，绝不留脏文件 |
| **京东** (InfoQ 2024) | 存量从简、核心优先的优先级策略；工具生成+人工调参 |
| **腾讯** (merico 2025) | 异步任务、Worker Pool、Context 精简防超限 |

---

## 快速开始

```bash
# 1. 安装
cd testgen-go
go build -o testgen ./cmd/testgen

# 2. 运行（OpenAI）
export OPENAI_API_KEY=sk-xxx
./testgen \
  --repo /path/to/your/go/service \
  --workers 4 \
  --target-cov 80

# 3. 运行（Anthropic Claude）
export ANTHROPIC_API_KEY=sk-ant-xxx
./testgen \
  --repo /path/to/service \
  --llm-provider anthropic \
  --llm-model claude-3-5-sonnet-20241022

# 4. 只处理指定包
./testgen --repo ./myrepo --pkg internal/service,internal/handler

# 5. 中断后续跑（state自动保存）
./testgen --repo ./myrepo   # 自动跳过已处理的函数
```

---

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--repo` | `.` | Go 仓库根目录 |
| `--workers` | `4` | 并行 Worker 数量 |
| `--retries` | `3` | 每个函数的 LLM 修复最大次数 |
| `--target-cov` | `80.0` | 达到此覆盖率后自动停止 |
| `--min-priority` | `0.3` | 低于此优先级的函数跳过 |
| `--pkg` | 全部 | 限定处理的包路径（逗号分隔） |
| `--llm-provider` | `openai` | `openai` / `anthropic` / `ollama` |
| `--llm-model` | 按 provider | 模型名称 |
| `--llm-key` | env | API Key |
| `--llm-url` | 默认端点 | 自定义 API URL（代理/本地） |
| `--state` | `<repo>/.testgen-state.json` | 状态文件路径 |

---

## 优先级算法

```
priority = (1 - coverage) × complexity × exportedBonus

complexity: 函数行数 > 100 → 3.0, > 30 → 2.0, else 1.0
exportedBonus: 导出函数 → 1.5, else 1.0
```

高优先级 = 覆盖率低 + 逻辑复杂 + 对外暴露 → 先处理

---

## 生成策略（Prompt 核心原则）

1. **表格驱动测试**：Go 惯用的 table-driven test + `t.Run`
2. **Mock 外部依赖**：HTTP 用 `httptest`，DB 用 `sqlmock`，接口用 `testify/mock`
3. **不可测则跳过**：全局变量、init()、无接口的 DB 直连 → 标记 failed，不留脏文件
4. **同包 vs 黑盒**：
   - 未导出函数 → `package xxx`（同包访问）
   - 导出函数 → `package xxx_test`（黑盒测试）
5. **幂等**：同一函数已有测试 → 跳过，不重复写

---

## 生成的文件结构

```
your-service/
├── internal/
│   └── service/
│       ├── user.go                  ← 源码（不动！）
│       ├── user_testgen_test.go     ← 新生成的测试 ✨
│       └── user_test.go             ← 原有测试（不动！）
└── .testgen-state.json              ← 状态文件（可gitignore）
```

生成的文件统一命名为 `<original>_testgen_test.go`，便于区分人工写的和自动生成的。

---

## 典型 Prompt 结构

```
System: 你是 Go 测试专家。规则：不改源码；只生成 _test.go；使用 table-driven...

User:
## FUNCTION TO TEST
File: internal/service/user.go
Package: service
...
### Function under test:
```go
func (s *UserService) CreateUser(ctx context.Context, req *CreateUserReq) (*User, error) {
  ...
}
```
### Existing tests in this package: ...

## YOUR TASK
覆盖 happy path + 边界 + 错误分支...
```

---

## 关于 Go 历史代码的特殊处理

| 常见问题 | 处理方案 |
|---------|---------|
| 未导出函数 | 同包测试（`package xxx`），可直接访问 |
| 具体类型依赖（非接口） | 提示 LLM 用 monkey patch 或通过 exported 方法间接测试 |
| 全局 DB/Redis 连接 | 用 `go-sqlmock` / `miniredis` 替换全局变量 |
| `init()` 副作用 | 跳过，优先级标为 0 |
| 循环依赖 | 降低优先级，放到队列末尾 |
| `time.Now()` 依赖 | 提示注入 `clockwork.Clock` 接口（但不改源码，用 package-level var 替换） |

---

## 扩展：集成到 CI/CD

```yaml
# .github/workflows/testgen.yml
name: Auto Unit Test Generation
on:
  schedule:
    - cron: '0 2 * * *'   # 每天凌晨 2 点运行
  workflow_dispatch:

jobs:
  testgen:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with: { go-version: '1.21' }
      - run: go build -o testgen ./cmd/testgen
        working-directory: testgen-go
      - run: ./testgen-go/testgen --repo . --workers 4 --target-cov 70
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      - uses: actions/upload-artifact@v4
        with:
          name: testgen-state
          path: .testgen-state.json
      - name: Open PR with generated tests
        uses: peter-evans/create-pull-request@v6
        with:
          title: 'test: auto-generated unit tests'
          branch: 'auto/testgen'
```

---

## 后续可以加的能力

- [ ] **增量模式**：只处理 `git diff` 新增/修改的函数（增量提交触发）
- [ ] **覆盖率趋势图**：生成 HTML 报告，追踪每次运行的覆盖率变化
- [ ] **Mock 自动生成**：检测到未实现的接口时，自动 `mockgen`
- [ ] **并发限速**：LLM API 有 rate limit，加 token bucket 控制 QPS
- [ ] **人工审核队列**：Failed 的函数输出到文件，方便人工 review 后手动补
- [ ] **Ollama 本地模型**：离线场景用 `codellama:7b` 或 `deepseek-coder`
