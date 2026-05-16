# clawstock

[![Pages](https://github.com/KCNyu/clawstock/actions/workflows/pages/pages-build-deployment/badge.svg)](https://kcnyu.github.io/clawstock/)
[![Harness Regression](https://github.com/KCNyu/clawstock/actions/workflows/harness-regression.yml/badge.svg)](https://github.com/KCNyu/clawstock/actions/workflows/harness-regression.yml)
[![License: Personal](https://img.shields.io/badge/license-personal--use-orange.svg)](#license)

> Harness-driven HK + US portfolio analysis workspace.
> Preflight scripts → LLM swarm → postflight validation, wired into 10 cron jobs that
> publish daily WeChat briefings and refresh a public dashboard.

**🎯 [Live Portfolio Dashboard](https://kcnyu.github.io/clawstock/dashboard.html)** &nbsp;|&nbsp;
**[Daily Briefs Index](https://kcnyu.github.io/clawstock/)**

---

## Table of Contents

- [What this is](#what-this-is)
- [Architecture](#architecture)
- [Cron job map](#cron-job-map)
- [Repository layout](#repository-layout)
- [Quickstart](#quickstart)
- [Iron rules](#iron-rules)
- [Self-learning loop](#self-learning-loop)
- [Stack](#stack)
- [Disclaimer](#disclaimer)
- [License](#license)

---

## What this is

A personal investment workspace where Claude Code (acting as `Rick`, an opinionated
portfolio analyst persona) runs on a fixed cron schedule via [openclaw](https://openclaw.com),
analyses the HK + US legs of a real portfolio, and ships briefings to WeChat plus
a live web dashboard.

The interesting part is the **harness pattern**: every cron job is split into three
stages so the LLM cannot quietly skip a step.

```
┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│   preflight (确定性)│ ──► │   LLM (Rick swarm) │ ──► │  postflight (校验)  │
└────────────────────┘     └────────────────────┘     └────────────────────┘
  refresh prices / FX /     read context.json:        section markers /
  HHI / snapshot / EDGAR /  write report + plan.json  verbatim block /
  retrospective              (LLM does only synthesis) banned-phrase / length
                                                       pass/warn auto-commit
```

Deterministic work (refresh prices, FX conversion, HHI computation, signal counting)
runs 100% in Python. The LLM is allowed only the parts that cannot be scripted:
combining signals into a written take. Missing a snapshot, forgetting FX, omitting
a >3% mover — all caught by postflight.

## Architecture

Four harness pairs cover the nine stock cron jobs:

| Pair | Triggers | Job |
|---|---|---|
| `brief_preflight.py` + `brief_postflight.py` | 08:00 HKT weekday daily-deep-brief | FX + snapshot + HHI + EDGAR + retrospective |
| `report_preflight.py --market {hk\|us} --phase {open\|mid\|pm\|close}` | 6 Mode 6 briefings | Refresh prices + extract signals + anomalies + headline |
| `intraday_preflight.py --market {hk\|us}` | 2 Mode 7 monitors (every 30 min) | Prices + anomaly detect + should_alert decision |
| `build_dashboard.py` | runs after every postflight commit | Aggregates portfolio + snapshots + plans → `assets/data/dashboard.json` |

Each postflight self-validates its companion LLM output against a hard contract:
required section markers, verbatim data block from preflight, banned phrases
("数据待获取" / "TODO"), length caps, mandatory anomaly mention.

`pass` / `warn` ⇒ auto-commit `portfolio.json` + `assets/data/dashboard.json`.
`fail` ⇒ no commit; banner prefix on the WeChat message.

## Cron job map

10 scheduled jobs (HKT for HK leg, ET for US leg):

| Time | Job | Mode | Harness |
|---|---|---|---|
| 03:00 | Memory Dreaming Promotion | system | — |
| 08:00 HKT weekday | 📊 Daily deep brief | daily-deep-brief | brief preflight/postflight |
| 09:30 HKT weekday | HK open report | Mode 6 | `report --market hk --phase open` |
| 09:00–15:30 every 30 min HKT | HK intraday monitor | Mode 7 | `intraday --market hk` |
| 12:00 HKT weekday | HK mid-day report | Mode 6 | `report --market hk --phase mid` |
| 13:30 HKT weekday | HK afternoon update | Mode 6 | `report --market hk --phase pm` |
| 16:00 HKT weekday | HK close report | Mode 6 | `report --market hk --phase close` |
| 09:30 ET weekday | US open report | Mode 6 | `report --market us --phase open` |
| 09:00–15:30 every 30 min ET | US intraday monitor | Mode 7 | `intraday --market us` |
| 16:00 ET weekday | US close report | Mode 6 | `report --market us --phase close` |

## Repository layout

```
clawstock/
├── README.md                   # this file
├── dashboard.html              # interactive dashboard (ECharts)
├── index.md                    # Jekyll Pages landing
├── _config.yml                 # Jekyll config
│
├── SOUL.md / IDENTITY.md       # Rick's persona / disposition
├── USER.md                     # kcn profile + preferences
├── MEMORY.md                   # iron rules + known traps
├── TOOLS.md                    # scripts / fallback chains / skill routing
├── INVESTMENT_SOP.md           # investment-question startup sequence
├── AGENTS.md / CLAUDE.md       # entry-point pointers
│
├── portfolio.json              # real positions (HK + US)
├── price_alerts.md             # active manual alerts
│
├── scripts/
│   ├── data/                   # data fetchers (called by harness)
│   │   ├── analyze_hk_stocks.py
│   │   ├── analyze_us_stocks.py
│   │   ├── fetch_us_stocks.py
│   │   ├── fetch_us_filings.py
│   │   ├── fetch_fx.py
│   │   ├── update_portfolio.py
│   │   └── build_dashboard.py
│   ├── harness/                # preflight + postflight pairs
│   │   ├── brief_preflight.py     brief_postflight.py
│   │   ├── report_preflight.py    report_postflight.py
│   │   └── intraday_preflight.py  intraday_postflight.py
│   └── legacy/                 # superseded scripts kept as reference
│
├── skills/                     # SKILL.md packages (Claude Code skills)
│   ├── daily-deep-brief/
│   ├── hk-stock-analysis/
│   ├── us-stock-analysis/
│   ├── portfolio-swarm-review/
│   ├── portfolio-risk-review/
│   └── ...
│
├── memory/                     # daily logs + plans + snapshots
│   ├── {YYYY-MM-DD}.md             # handwritten notes
│   ├── {YYYY-MM-DD}-pre-open.md    # daily deep brief markdown
│   ├── {YYYY-MM-DD}-plan.json      # structured plan (retrospective input)
│   └── snapshots/{YYYY-MM-DD}.json # daily portfolio snapshot
│
├── assets/                     # static for Pages
│   ├── dashboard.css
│   ├── dashboard.js
│   └── data/dashboard.json     # aggregated by build_dashboard.py
│
└── .github/workflows/          # CI: harness regression + Pages auto-build
```

## Quickstart

```bash
# 1. Refresh portfolio prices (US leg, 7-route fallback)
python3 scripts/data/analyze_us_stocks.py

# 2. Refresh HK leg (Tencent → stooq → yfinance)
python3 scripts/data/analyze_hk_stocks.py

# 3. Manually trigger a daily deep brief preflight
python3 scripts/harness/brief_preflight.py

# 4. Rebuild dashboard data
python3 scripts/data/build_dashboard.py

# 5. Open the dashboard locally (any static server)
python3 -m http.server 8080  # then visit http://localhost:8080/dashboard.html
```

API keys (Finnhub, Alpha Vantage, Polygon) are read from `.api_keys`
(gitignored). All scripts work without keys, just with reduced data quality.

## Iron rules

These are the constraints the harness enforces — listed here because they would
otherwise be invisible to anyone reading the code.

### FX rule (HKD + USD cannot be summed directly)

HK leg is denominated in HKD, US leg in USD. **Never add them directly.** Book-level
numbers must be presented in both views:

```
Total P&L: USD${X}  ≈  HKD${Y}     (USDHKD = {rate}, source {src}, fetched {ts})
  ├─ HK: HKD${a}  ≈  USD${a/rate}
  └─ US: USD${b}  ≈  HKD${b*rate}
```

Historical incident (2026-05-16): a brief reported "合计 -4,423" by directly
adding -4936 HKD + +513 USD — meaningless. All harness paths now go through
`fetch_fx.py` and the postflight scans for known bug-pattern strings.

### Concentration HHI

Per leg (HK and US separately):
- `weight_i = current_value_i / leg_total_value`
- `HHI = Σ weight²`
- `Top2 = sum of largest two weights`

| HHI | Top 2 | Status |
|---|---|---|
| &lt; 0.15 | &lt; 40% | ✅ healthy |
| 0.15 – 0.25 | 40 – 60% | ⚠️ moderately concentrated |
| 0.25 – 0.40 | 60 – 75% | 🟠 concentrated risk |
| &gt; 0.40 | &gt; 75% | 🔴 dangerously concentrated |

The dashboard renders both legs as dual gauges; the brief postflight requires
that the LLM's `▎集中度` section quotes the verdict verbatim.

### Leveraged ETF heuristic

Preflight skips SEC EDGAR lookups for tickers whose name contains:
`倍`, `Direxion`, `T-Rex`, `Defiance`, `ProShares`, `2X Long`, `3X Long`, `Daily Target`.
For leveraged ETFs, fundamentals are noise — look at underlying instead.

## Self-learning loop

Every daily-deep-brief writes `memory/{date}-plan.json` with structured actions:

```jsonc
{
  "date": "2026-05-16",
  "buckets": {
    "cut":              [...],
    "trim_on_rebound":  [...],
    "hold_and_watch":   [...],
    "t_only":           [...],
    "add_only_on_trigger": [...]
  },
  "actions": [
    {
      "ticker":      "07226",
      "bucket":      "trim_on_rebound",
      "trigger_type": "price_above",
      "trigger":      "trim 1000 shares if price > 4.85",
      "confidence":   0.62,
      "simulated_entry_price": 4.49
    }
  ],
  "context": { "hhi_us": 0.21, "hhi_hk": 0.34, "fx": 7.83 }
}
```

The next morning's brief reads the prior plan and, for each action, computes:
1. **Did the trigger fire?** (cross checked against actual price action)
2. **Simulated P&L** if the action had been executed at the trigger price
3. **Confidence calibration** — log into rolling stats over time

Design heavily inspired by [TradingAgents v0.2.4](https://github.com/TauricResearch/TradingAgents)'s
persistent decision memory, but adapted for HK + US dual-leg portfolios.

## Stack

- **[Claude Code](https://claude.com/claude-code)** — Anthropic official CLI, the agent harness
- **[openclaw](https://openclaw.com)** — cron scheduler + multi-channel delivery (WeChat, Telegram, etc.)
- **Python 3** — data scripts + harness
- **[ECharts 5.5](https://echarts.apache.org/)** — interactive dashboard charts
- **Jekyll + GitHub Pages** — static hosting
- Public data sources: Tencent / stooq / yfinance / Frankfurter / SEC EDGAR / Finnhub
- Private: `portfolio.json` (real positions, committed knowingly to a public repo)

## Disclaimer

This repository contains real trading positions and analysis. It is shared publicly
for personal record-keeping and as a portable workspace, **not as investment advice
or a recommendation**. Every number is point-in-time and may be stale. Past
performance does not guarantee future results. The persona (`Rick`) is opinionated
by design — that doesn't mean it is right.

## License

Personal-use repository. No license granted for derivative trading systems, automated
copy-trading, or commercial use. Code patterns (harness layout, fallback chain design,
HHI formulation) may be adapted under any compatible open-source license of your
choosing if reused independently.

---

*Built and maintained by [Shengyu Li (kcn)](https://github.com/KCNyu) and Rick.*
