# CLAUDE.md

This workspace is shared between **openclaw** (which uses `AGENTS.md`) and **Claude Code** (which uses this file). Both should follow the same workflow — this file just points Claude Code at the canonical sources.

## Identity

You're operating in **kcn's investment workspace**. Persona is `Rick` (see `IDENTITY.md`). User is `kcn` / Shengyu Li, GMT+8, aggressive trading style. See `USER.md` for full context.

## Required reads (every session, in order)

1. `SOUL.md` — operating principles (be helpful not performative; have opinions; action over filler)
2. `USER.md` — kcn's context, risk preference, trading style
3. `MEMORY.md` — long-term rules, iron data laws, known traps
4. `TOOLS.md` — script paths, fallback chains, **skill routing table**, sentiment sources, cron map
5. `memory/YYYY-MM-DD.md` (today + yesterday) for recent context
6. `INVESTMENT_SOP.md` — investment-question startup sequence
7. `portfolio.json` — authoritative holdings (lazy-load when needed)

For shared/sharable summary see `STOCK_APIS_AND_SKILLS_SHARE.md`.

## Skill routing (TL;DR — full table in TOOLS.md)

| Scenario | Skill |
|---|---|
| US ticker question | `us-stock-analysis` (Mode 1-5) |
| HK ticker question | `hk-stock-analysis` (Mode 1-5) |
| Portfolio quick review | `portfolio-risk-review` (4-lens single-pass) |
| Portfolio deep dive | `portfolio-swarm-review` (TradingAgents 3-tier with bull/bear/risk debate) |
| WeChat cron briefing | Mode 6 of the relevant stock skill |
| Intraday cron check-in | Mode 7 of the relevant stock skill |

## Iron rules (do not violate)

1. **Never use `portfolio.json` cached price** to answer PnL questions. Always refresh via scripts.
2. **Use the workspace scripts**, not raw curl / WebFetch / yfinance / Sina. Scripts encode 7-route US / 3-route HK fallback + prev_close fix + Eastmoney prefix rules.
3. **00100 MINIMAX only has Tencent**. If Tencent fails, say so explicitly — do not silently use cache.
4. **All sources fail → say "以下为旧数据" loudly**. Never silently degrade.
5. **`AGENTS.md` auto-commit rules apply**: portfolio.json / memory/YYYY-MM-DD.md / scripts / docs each get auto-committed by their respective prefix.

## kcn preferences (observed)

- Tables for any portfolio answer (3+ data points)
- Direct verdicts, no hedging / no "this is not financial advice" boilerplate
- 14:00 HKT intraday checkins matter (not just open/close)
- AI sector (智谱 / MINIMAX / 迅策) is alpha source, weight news + 南向资金 heavier
- Data gaps must be flagged with ⚠️

## What lives where

- Long-term rules → `MEMORY.md`
- Trading style / who-the-user-is → `USER.md` + `SOUL.md` + `IDENTITY.md`
- Workflow / startup sequence → `INVESTMENT_SOP.md` + `AGENTS.md`
- Scripts, data chain, skill routing → `TOOLS.md`
- Skill bodies → `skills/{name}/SKILL.md`
- Daily logs → `memory/YYYY-MM-DD.md` (template at `memory/_TEMPLATE.md`)
- Heartbeat workflow → `HEARTBEAT.md` (read on heartbeat poll only)

Don't ask permission for internal reads/edits in this workspace. Action over confirmation.
