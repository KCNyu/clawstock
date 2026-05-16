---
name: us-stock-analysis
description: Workspace-aware US stock analysis for kcn. Routes through the local fetch pipeline (analyze_us_stocks.py / fetch_us_stocks.py) instead of generic web search, then layers fundamental/technical/news analysis on top. Use when user asks to analyze a US ticker (e.g. "analyze AAPL", "look at RKLB", "compare TSLA vs NVDA"), check earnings, run technicals, or write an investment report on a US name.
triggers:
  - "analyze {US ticker}"
  - "美股 {ticker}"
  - "look at AAPL/NVDA/..."
  - "compare X vs Y"
  - "stock report"
---

# US Stock Analysis

Workspace-native US stock analyst. Always uses kcn's local pipeline for price/RSI/MA/signal — uses web search only for news, peer data, fundamentals.

## Required reads before answering

In this order:
1. `/root/.openclaw/workspace/MEMORY.md` — data rules and traps (especially the "禁止用 portfolio.json 缓存价" rule)
2. `/root/.openclaw/workspace/TOOLS.md` — script paths, provider fallback chains, skill routing table
3. `/root/.openclaw/workspace/INVESTMENT_SOP.md` — standard startup sequence for investment questions
4. `/root/.openclaw/workspace/portfolio.json` — if the ticker is in the active book, cost basis and PnL matter

## Data source rule (non-negotiable)

**Default path — use the workspace script, not web search:**

```bash
# Full analysis: refreshes price + RSI-14 / MA20 / MA50 + Finnhub news + signal
python3 /root/.openclaw/workspace/analyze_us_stocks.py {TICKER}
python3 /root/.openclaw/workspace/analyze_us_stocks.py {TICKER} --no-news    # skip news (save Finnhub quota)

# Price-only refresh
python3 /root/.openclaw/workspace/fetch_us_stocks.py {TICKER}
```

The script internally runs the 7-route fallback (Nasdaq API → Eastmoney → Finnhub → Yahoo v8 → yfinance → Alpha Vantage → Polygon), pulls `prev_close` independently from Polygon's `/prev` endpoint (so `today_change` is trustworthy after close), and writes back to `portfolio.json` if the ticker is held. Bypassing it re-introduces every bug it was written to fix.

**Web search is only for:** earnings transcripts, SEC filings, analyst notes, sector news, peer fundamentals, qualitative thesis material — never primary price quotes.

**Forbidden:** Sina US quotes API (境外 403), raw Yahoo scraping when the script already covers it, reading `portfolio.json` cached `current_price` without first refreshing.

## Four analysis modes

Pick the smallest mode that answers the question. Default to **Quick Read** unless the user explicitly asks for deep analysis.

### Mode 1 — Quick Read (most common)
**When:** "What's RKLB at?" / "How's NVDA doing today?"
1. Run `analyze_us_stocks.py {TICKER} --no-news` for price + RSI/MA/signal
2. If in active book, pull cost basis + PnL from `portfolio.json`
3. One short paragraph: price, today's move, RSI/MA stance, one-line verdict

### Mode 2 — Technical Read
**When:** "Is X oversold?" / "Where's resistance on Y?"
1. Run `analyze_us_stocks.py {TICKER} --no-news`
2. Load `references/technical-analysis.md` for indicator interpretation
3. Output: trend (up/down/sideways), MA20/50 stance, RSI-14 reading (oversold <30, overbought >70), recent support/resistance from price action, one-line risk note

### Mode 3 — Fundamental Read
**When:** "Is X overvalued?" / "Analyze Y's business"
1. Run `analyze_us_stocks.py {TICKER}` for fresh price baseline
2. Run `python3 fetch_us_filings.py {TICKER}` — pulls SEC EDGAR: latest 10-K/10-Q/8-K + 13 key XBRL concepts (revenue/net income/cash/EPS/assets/equity, 4 most recent periods). **Use this before web search** — primary source, structured, no scraping.
3. (Optional) `python3 fetch_us_filings.py {TICKER} --form4` if insider activity is material to thesis
4. Web search only for what SEC EDGAR can't give: peer multiples, analyst consensus, qualitative thesis, sector context
5. Load `references/fundamental-analysis.md` for framework, `references/financial-metrics.md` for ratio definitions
6. Output: business overview, financial trends from XBRL, valuation vs peers/history, insider signal, key risks, fair value range

### Mode 4 — Full Report
**When:** "Give me a full report on X" / "Should I add X?"
1. Run script (Mode 1 baseline)
2. Do fundamentals (Mode 3)
3. Do technicals (Mode 2)
4. Do sentiment (Mode 5)
5. Web search for catalysts (next earnings date, upcoming product/regulatory events)
6. Load `references/report-template.md` for structure
7. Output: executive summary + bull case + bear case + valuation + technical setup + sentiment read + risk + catalyst calendar + concrete entry/exit levels

### Mode 7 — Intraday Check-in (cron-driven, every 30 min during trading hours)
**When:** US 盘中盯盘 cron (`*/30 9-15 * * 1-5 America/New_York`)，比 Mode 6 更轻量、更高频。

Workflow:
1. `cd /root/.openclaw/workspace && python3 analyze_us_stocks.py --wechat`
2. 脚本输出原样作为消息开头
3. 追加 `▎我的看法` 段（2-3 行）：
   - 重点变动：哪只票有信号 / 异常波动 / RSI 极值
   - 简短判断：今天该看 / 该等 / 该减；不复述数字
4. ≤600 字
5. 无标题（高频推送避免微信刷屏）

**和 Mode 6 的区别**：单段 `▎我的看法` 取代三段；无 ▎风险提示；无 git commit。

### Mode 6 — WeChat Briefing (cron-driven)
**When:** Triggered by cron at US open (or any session timestamp); used by the "美股开盘报告" job and any future US-session pushes.

Workflow (must be reproducible from cron without needing additional context):

1. `cd /root/.openclaw/workspace && python3 analyze_us_stocks.py --wechat`
2. Script prints a pre-formatted block — take it **verbatim** as the message body's facts section
3. Append 3 commentary lines (4-6 lines total):
   - `▎情绪面` — synthesize Finnhub news + 纳指 tone, call market direction
   - `▎技术面` — synthesize script's RSI/MA stance, name overbought/oversold/breakout
   - `▎操作建议` — name the one ticker to watch; if action suggested, give approximate price
4. If script flagged STOP/TRIM signals on ≥ 2 holdings, append `▎风险提示`
5. Commit: `git -C /root/.openclaw/workspace add portfolio.json && git -C /root/.openclaw/workspace commit -m "portfolio: 美股开盘价格更新"`
6. Total message ≤ 800 字

**Title template:** `🌅 美股开盘快报｜[今日日期] 21:30 CST`

**Hard rules:**
- ⚠️ data gaps must be stated explicitly, never fabricate
- Do not use `message` tool; reply text directly (cron delivery wraps it)
- No simple number recitation — model must add interpretation

### Mode 5 — Sentiment Read
**When:** "市场情绪怎么样" / "推上怎么说 X" / "Reddit 怎么聊 X" / before a sizing decision

Sources, in order:
1. **Finnhub news (in script)** — `analyze_us_stocks.py {TICKER}` without `--no-news` already pulls last 7 days with keyword sentiment scoring. **This is the first source — read it before anything else.**
2. **Tavily (news + X)** — for trending discussions, analyst notes, X/Twitter sentiment:
   ```bash
   node /root/.openclaw/workspace/skills/tavily-search/scripts/search.mjs "{TICKER} stock sentiment" --topic news --days 3
   node /root/.openclaw/workspace/skills/tavily-search/scripts/search.mjs "{TICKER} reddit wallstreetbets"
   ```
3. **Reddit JSON (no auth needed)** — direct fetch:
   ```bash
   curl -sH "User-Agent: openclaw/1.0" \
     "https://www.reddit.com/r/wallstreetbets/search.json?q={TICKER}&restrict_sr=1&sort=new&limit=25" \
     | jq '.data.children[].data | {title, score, num_comments, created_utc}'
   curl -sH "User-Agent: openclaw/1.0" \
     "https://www.reddit.com/r/stocks/search.json?q={TICKER}&restrict_sr=1&sort=new&limit=15" \
     | jq '.data.children[].data | {title, score}'
   ```
   r/wallstreetbets is retail momentum; r/stocks is more measured. Both together give the retail temperature.
4. **scrapling fallback** — if Reddit JSON 429s or content needs comment-level depth, use `StealthyFetcher` (see `../scrapling/SKILL.md`). Same for X if Tavily misses.

Output:
- **Sentiment score**: -1 (extremely fearful) to +1 (euphoric); call out divergence from price action ("price up but Reddit fearful — short squeeze setup" or vice versa)
- **Key narratives** (2-3 bullets): what people are actually saying / focused on
- **Catalyst chatter**: earnings expectations, upcoming events, FUD threads
- **Volume signal**: ↑ post count vs prior week = topic heating up

## Comparison mode

For "X vs Y" requests:
1. Run script for both tickers
2. Build side-by-side metric table (price, today_change, RSI, MA50 stance, P/E, revenue growth, margins, market cap)
3. Verdict in one paragraph — which has the cleaner setup and why; don't hedge

## Output style (kcn-tuned)

The user is aggressive, table-first, and hates filler. Match that:

- **Direct verdicts.** "RKLB looks toppy at $118, RSI 73, would trim on strength" beats "RKLB shows signs of being overbought; consider monitoring."
- **Tables for any 3+ data points.** Price/PnL/RSI/MA/signal lives in a table, not prose.
- **No hedging boilerplate.** Skip "This is not financial advice" — the user knows, and `MEMORY.md` has the trading style on record.
- **Cite the data freshness.** End with "数据: analyze_us_stocks.py {timestamp}" so the user knows price is live, not cached.
- **Flag stale data loudly.** If the script's fallback chain failed all 7 routes, lead with "⚠️ 数据获取失败，以下为旧缓存数据" before any analysis.

## Special handling — leverage ETFs

When the ticker is a leveraged ETF (SOXL, TQQQ, RKLX, MSFU, ROBN — anything with the `is_leveraged_etf=true` flag in `portfolio.json` or 2x/3x in the name):
- Always note decay risk for multi-day holding periods
- Verdicts must reference the underlying's direction, not just the ETF's chart
- 1-day RSI on these is noisy; weight MA20/50 stance higher

## Examples

**User:** "RKLB 怎么样"
**Approach:** Mode 1 — `python3 analyze_us_stocks.py RKLB --no-news`, read its position from portfolio.json, output table + one-line verdict.

**User:** "compare AAPL vs MSFT"
**Approach:** Comparison mode — script both, side-by-side table, paragraph verdict.

**User:** "Give me a deep report on PLTU"
**Approach:** Mode 4 — full pipeline with references/report-template.md structure.

## Reference files (lazy-load)

- `references/technical-analysis.md` — indicator definitions, chart patterns, support/resistance methodology
- `references/fundamental-analysis.md` — business quality, financial health, valuation frameworks, red flags
- `references/financial-metrics.md` — every ratio formula needed for valuation work
- `references/report-template.md` — full-report skeleton for Mode 4

These are market-agnostic; `hk-stock-analysis` also references them.

## Companion tools

- `../scrapling/SKILL.md` — when all 7 script-internal fallbacks fail, or when Reddit/social needs comment-level depth past the public JSON
- `../tavily-search/SKILL.md` — primary web search tool for news/sentiment/research (do not let the model improvise with Yahoo/Google scraping)
- `/root/.openclaw/workspace/TradingAgents/` — TauricResearch multi-agent framework already cloned in workspace. For deep bull/bear debate analysis, its `tradingagents/agents/` taxonomy (analysts → researchers → risk debators → trader) is the reference design — `portfolio-swarm-review` borrows this structure
