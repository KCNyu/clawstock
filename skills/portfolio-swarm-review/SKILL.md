---
name: portfolio-swarm-review
description: Run a swarm-style multi-role review of kcn's current holdings using workspace files and our own market-data chain. Use for portfolio-wide action plans, post-close reviews, holiday or next-session operation planning, cross-market linkage analysis, leverage ETF risk assessment, and judge-style final recommendations built from multiple analyst roles.
---

# Portfolio Swarm Review

Use this skill when a single-pass holdings review is not enough and a multi-role decision process is more useful.

## Required reads

Always read in this order:
1. `/root/.openclaw/workspace/MEMORY.md`
2. `/root/.openclaw/workspace/portfolio.json`
3. `/root/.openclaw/workspace/memory/current-portfolio-summary.md`
4. Recent daily memory files when recent trades affect interpretation

## Fresh data rule

Before producing conclusions, refresh or verify fresh market data using our own workflow.

### Use our own data chain
- HK holdings: Eastmoney or Tencent first
- US holdings: Eastmoney first when available, then Finnhub fallback
- KR linkage: Naver polling first
- If any leg is stale, say exactly which leg is stale and limit confidence accordingly

## Four-role swarm framework

Run the analysis as if four specialized analysts worked in sequence.
You may do this in one response, but keep the roles distinct internally and in the final synthesis.

### Role 1. Position Analyst
Focus:
- current price vs cost
- unrealized PnL and distance to breakeven
- classify each position as core, tactical, weak, or leverage-risk

Output:
- one-line verdict for each active holding
- identify strongest and weakest positions

### Role 2. Cross-Market Linkage Analyst
Focus:
- US growth / Nasdaq tone for NVDA, TQQQ, HOOD, QQQ
- storage / semi chain for 07709 via SK hynix and Samsung
- HSTECH tone for 07226, 03032, 03033
- theme linkage for CRCL and OKLO when relevant

Output:
- whether each linkage chain is supportive, neutral, or weak
- the one or two most important inter-market signals

### Role 3. Risk Analyst
Focus:
- concentration risk
- leverage decay risk
- top drawdown contributors by money and by volatility
- correlation clusters inside the portfolio

Output:
- rank the top 3 risk sources
- identify where one bad session can hurt the whole book

### Role 4. Decision Judge
Focus:
- convert the first three roles into action priorities
- preserve aggressive style but reduce unnecessary damage
- distinguish between hold, reduce, T-only, and conditional add

Output:
- practical action list
- next-session or post-holiday plan
- triggers that would change the recommendation

## Portfolio grouping template

Use these buckets unless the portfolio changes materially.

### US growth / beta
- NVDA
- RKLB
- QQQ
- TQQQ
- HOOD
- TCOM

### Special situation / theme
- CRCL
- OKLO

### HK lower-beta core / proxy exposure
- 02208
- 03032
- 03033

### HK high-risk leverage
- 07226
- 07709

### Watch-only linkage name
- 07747 when Samsung linkage matters

## Required final output structure

### Swarm summary
- one paragraph summarizing the combined judgment

### Role 1, Position Analyst
- bullet list for each active holding with price, PnL, verdict

### Role 2, Cross-Market Linkage Analyst
- US side
- HK side
- KR side
- key cross-market implication

### Role 3, Risk Analyst
- top 3 risks ranked
- what is causing most drawdown now
- what can create the next sharp drawdown

### Role 4, Decision Judge
Split into four buckets:
- hold and watch
- trim on rebound
- T-only
- add only on trigger

### Next-step plan
Give a direct operating plan for the next session or post-holiday period:
- what to watch first
- which holdings matter most at the open
- which price / market triggers would upgrade or downgrade the stance

## Style rules
- Keep it practical, not academic
- Tie each conclusion to real holdings
- Say plainly when a position is weak
- Do not let a high-conviction theme hide a bad structure
- Keep the final plan concise enough to trade from
