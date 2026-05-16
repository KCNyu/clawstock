# openstock

kcn 的 openclaw 投资分析 workspace —— 通过 [Claude Code](https://claude.com/claude-code) +
[openclaw](https://openclaw.com) cron 驱动的港股 + 美股 portfolio 分析系统。

## 架构：Harness 三段式

所有 stock cron 都走"preflight → LLM → postflight"三段式：

```
┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│   preflight (确定性)│ ──► │   LLM (Rick swarm) │ ──► │  postflight (校验)  │
└────────────────────┘     └────────────────────┘     └────────────────────┘
  脚本必跑：刷价/FX/         读 context.json:           段标记/verbatim/
  HHI/snapshot/EDGAR/         写报告 + plan.json         敷衍词/异动票/长度
  retrospective              （LLM 只做创造性合成）       pass/warn 自动 commit
```

为什么这样分：确定性活（refresh prices、FX 换算、HHI 算法、信号计数）100% 脚本执行，
LLM 只做"分析综合"这个不能脚本化的部分。漏快照/HHI/FX/异动票/段标记都被 postflight 抓住。

## Cron Job Map（10 个 cron）

| 时点 | Job | Mode | Harness 脚本 |
|---|---|---|---|
| 03:00 | Memory Dreaming Promotion | (system) | — |
| 08:00 HKT 工作日 | 📊 盘前深度简报 | daily-deep-brief | `brief_preflight.py` / `brief_postflight.py` |
| 09:30 HKT 工作日 | 港股开盘报告 | Mode 6 | `report_preflight.py --market hk --phase open` |
| 09-15:30 每 30 分 HKT | 港股盘中盯盘 | Mode 7 | `intraday_preflight.py --market hk` |
| 12:00 HKT 工作日 | 港股午盘报告 | Mode 6 | `report_preflight.py --market hk --phase mid` |
| 13:30 HKT 工作日 | 港股午后快报 | Mode 6 | `report_preflight.py --market hk --phase pm` |
| 16:00 HKT 工作日 | 港股收盘报告 | Mode 6 | `report_preflight.py --market hk --phase close` |
| 09:30 ET 工作日 | 美股开盘报告 | Mode 6 | `report_preflight.py --market us --phase open` |
| 09-15:30 每 30 分 ET | 美股盘中盯盘 | Mode 7 | `intraday_preflight.py --market us` |
| 16:00 ET 工作日 | 美股收盘报告 | Mode 6 | `report_preflight.py --market us --phase close` |

每个 cron 自动发到 WeChat（@tencent-weixin/openclaw-weixin plugin），日报落盘到
`memory/{YYYY-MM-DD}-pre-open.md`。

## 文件地图

### Root markdown（每个 session baseline reads）

| 文件 | 内容 |
|---|---|
| `SOUL.md` | Rick 的人格/思考方式 |
| `IDENTITY.md` | Rick 是谁 |
| `USER.md` | kcn 是谁 + 偏好 |
| `MEMORY.md` | 铁律（FX、集中度、老千股）+ 已知坑 |
| `TOOLS.md` | 全部脚本 / fallback 链 / skill 路由 / cron map |
| `INVESTMENT_SOP.md` | 投资问题启动顺序 |
| `AGENTS.md` | openclaw agent 入口 |
| `CLAUDE.md` | Claude Code 入口（同 AGENTS.md 一份指针） |
| `HEARTBEAT.md` | Heartbeat poll 工作流 |
| `DREAMS.md` | 记忆系统的梦境层（write-only） |

### Skill bodies (`skills/{name}/SKILL.md`)

| Skill | 用途 |
|---|---|
| `daily-deep-brief` | 08:00 HKT 工作日 cron — 全 swarm 盘前深度分析（Tier 1/2/3/Judge）|
| `hk-stock-analysis` | 港股 Mode 1-7（手动分析 + 4 个 briefing cron + 1 盯盘 cron） |
| `us-stock-analysis` | 美股 Mode 1-7（手动分析 + 2 个 briefing cron + 1 盯盘 cron） |
| `portfolio-swarm-review` | ad-hoc 手动深度组合分析 |
| `portfolio-risk-review` | 风险视角组合 review |
| `trading` | 决策类指南 |
| `openclaw-tune` | openclaw 系统级维护 |
| `tavily-search` / `scrapling` | 搜索 / 爬虫 |
| `github` / `flyai` | 工程类 |

### 数据脚本（被 harness 调用）

| 脚本 | 用途 |
|---|---|
| `analyze_hk_stocks.py` | HK 价格 + 信号（Tencent → stooq → yfinance fallback + 恒指/恒科 + Finnhub 新闻）|
| `analyze_us_stocks.py` | US 价格 + 信号（7-route fallback + RSI/MA + Finnhub 新闻）|
| `fetch_fx.py` | USDHKD 实时汇率（Frankfurter → exchangerate.host → Yahoo） |
| `fetch_us_filings.py` | SEC EDGAR fundamentals（10-K/10-Q/8-K/Form 4/13F/XBRL） |
| `update_portfolio.py` | 手动调仓后写 portfolio.json |

### Harness 脚本（4 套）

| Pair | 触发自 | 主要工作 |
|---|---|---|
| `brief_preflight.py` + `brief_postflight.py` | daily-deep-brief 08:00 cron | FX + snapshot + HHI + EDGAR + retrospective |
| `report_preflight.py` + `report_postflight.py` | 6 个 Mode 6 briefing cron | 刷价 + 信号 + 异动 + 标题 |
| `intraday_preflight.py` + `intraday_postflight.py` | 2 个 Mode 7 盯盘 cron | 刷价 + 异动检测 + should_alert 决策 |

### Memory（按日组织）

```
memory/
├── {YYYY-MM-DD}.md                    # 用户手写日常笔记
├── {YYYY-MM-DD}-pre-open.md          # daily-deep-brief 完整 markdown 报告
├── {YYYY-MM-DD}-plan.json            # daily-deep-brief 结构化 plan（给次日 retrospective 用）
├── snapshots/{YYYY-MM-DD}.json       # portfolio.json 每日快照（longitudinal）
└── .tmp/                              # preflight 临时 context（gitignored）
```

## 关键设计点

### FX 铁律（HKD + USD 不能直接相加）

港股 book 用 HKD，美股 book 用 USD —— **不能直接相加**。所有 book-level 数字必须两个 view 都给：
```
真实总浮盈亏: USD${X}  ≈  HKD${Y}   (USDHKD = {rate}, source {src}, fetched {ts})
  ├─ HK 段：HKD${a}  ≈  USD${a/rate}
  └─ US 段：USD${b}  ≈  HKD${b*rate}
```

历史教训：2026-05-16 那次 brief "合计 -4,423" 直接把 -4936 HKD 和 +513 USD 相加 → 数字毫无意义。
现在所有 harness 强制走 `fetch_fx.py`。

### 集中度 HHI 算法

每个 leg（HK / US 分开）：
- `weight_i = current_value_i / leg_total_value`
- `HHI = Σ weight²`
- `Top2 = 最大两仓 weight 之和`

| HHI | Top 2 | 状态 |
|---|---|---|
| < 0.15 | < 40% | 健康 ✅ |
| 0.15-0.25 | 40-60% | 偏集中，可接受 |
| 0.25-0.40 | 60-75% | 集中风险 ⚠️ |
| > 0.40 | > 75% | 危险集中 🔴 |

### Self-learning loop（plan.json + retrospective）

每个 daily-deep-brief 跑完写 `memory/{date}-plan.json` 结构化 plan。次日 brief 自动读
上次 plan.json，对每个 action 算 trigger 是否触发 + 模拟 P&L + confidence calibration。

设计参考 TradingAgents v0.2.4 的 persistent decision memory。

## Stack

- [Claude Code](https://claude.com/claude-code) — Anthropic 官方 CLI / agent harness
- [openclaw](https://openclaw.com) — cron 调度 + 多 channel delivery（WeChat / Telegram / etc）
- Python 3 — 数据脚本 + harness
- Public data sources: Tencent / stooq / yfinance / Frankfurter / SEC EDGAR / Finnhub
- Private: portfolio.json（真实仓位）

## Disclaimer

This repo contains real trading positions and analysis. It is for **personal use only** —
not investment advice, not a recommendation. All numbers are point-in-time and may be
stale. Past performance does not guarantee future results.
