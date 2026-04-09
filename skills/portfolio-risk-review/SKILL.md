---
name: portfolio-risk-review
description: Analyze kcn's current portfolio with our own workspace data sources and holdings files. Use for current holdings analysis, portfolio review, position risk ranking, HK-US-KR linkage assessment, leverage ETF risk review, and final actionable investment reports based on portfolio.json plus fresh market quotes from our fallback chain.
---

# Portfolio Risk Review

Use this skill to produce a practical holdings report for kcn.

## Required inputs

Read in this order:
1. `/root/.openclaw/workspace/MEMORY.md`
2. `/root/.openclaw/workspace/portfolio.json`
3. `/root/.openclaw/workspace/memory/current-portfolio-summary.md`
4. Recent `memory/YYYY-MM-DD.md` entries when trade context matters

## Market data rule

Always use fresh quotes before judging the portfolio.

### Use our own data chain, not generic defaults
- HK stocks / ETFs: Tencent or Eastmoney first, then other fallback already documented in workspace
- US stocks: Eastmoney first where available, then Finnhub fallback
- KR linkage names: Naver polling API first
- If fresh data cannot be obtained, say so explicitly and mark any stale conclusions

## Analysis workflow

### 1. Build the portfolio map
For each holding, identify:
- market
- shares
- cost basis
- latest price
- unrealized PnL
- whether it is core, tactical, or high-risk leverage exposure

### 2. Group the book into risk buckets
Use buckets that fit this portfolio:
- US growth / beta: NVDA, RKLB, TQQQ, HOOD, QQQ, TCOM
- theme / special situation: CRCL, OKLO
- HK core / lower beta: 02208, 03032, 03033
- HK leverage / high-risk: 07226, 07709
- exited but relevant watch items: 07747 when linkage matters

### 3. Run four lenses

#### Lens A, PnL and position quality
Judge each position by:
- gain/loss magnitude
- proximity to breakeven
- whether thesis is intact, weakening, or broken
- whether the position is suitable for holding, trimming, or only doing T

#### Lens B, cross-market linkage
Explicitly review:
- NASDAQ / US growth tone for TQQQ, NVDA, HOOD
- storage / semi linkage into SK hynix and Samsung for 07709 and 07747 context
- Hang Seng Tech direction for 07226, 03032, 03033

#### Lens C, concentration and drawdown risk
Highlight:
- largest loss contributors
- leverage decay risk
- correlation clusters
- which positions can cause outsized portfolio drawdown in one bad day

#### Lens D, action priority
Sort positions into:
- keep and watch
- can reduce on rebound
- suitable for tactical T only
- only add if a defined trigger appears

## Output format

Use this exact structure.

### Portfolio snapshot
- total US PnL
- total HK PnL
- biggest winner
- biggest loser
- main risk source

### Position-by-position view
For each active holding, give:
- ticker
- latest price
- PnL
- short verdict in one line

### Cross-market read
Cover:
- US side
- HK side
- KR linkage side

### Risk ranking
Rank the top 3 portfolio risks from highest to lowest.

### Action plan
Give practical actions in plain language:
- what to hold
- what to trim on strength
- what to avoid adding blindly
- what to use for T only

## Style rules
- Be direct and practical
- Prefer concrete judgments over generic finance prose
- Tie every conclusion back to the actual holdings
- Respect the user's aggressive style, but still call out real risk plainly
- Do not replace our data-source workflow with external framework defaults
