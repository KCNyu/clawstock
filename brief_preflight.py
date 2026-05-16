#!/usr/bin/env python3
"""
brief_preflight.py — deterministic data collection for daily-deep-brief harness.

Runs everything that must happen BEFORE LLM analysis. LLM reads the resulting
brief-context.json to get all deterministic facts (FX rate, concentration,
retrospective) so it can't forget steps.

Steps:
  1. Refresh US + HK prices (mutates portfolio.json)
  2. Fetch FX rate (3-route fallback)
  3. Snapshot portfolio.json → memory/snapshots/{date}.json
  4. Compute HHI concentration + Top2 for HK and US legs
  5. Compute USD-base / HKD-base book totals
  6. Pull SEC EDGAR fundamentals for US singles (is_leveraged_etf=false)
  7. Locate prior plan.json + compute retrospective (trigger fired + simulated PnL)
  8. Write memory/.tmp/brief-context-{date}.json

Output (stdout): step-by-step progress; final summary with issue count.
Exit: 0 if no issues, 1 if any data leg failed.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

WS = Path('/root/.openclaw/workspace')
TMP_DIR = WS / 'memory' / '.tmp'
SNAPSHOT_DIR = WS / 'memory' / 'snapshots'


def _run(script, args=None, timeout=120):
    """Run a workspace script; return (stdout, ok)."""
    cmd = ['python3', str(WS / script)] + (args or [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout, r.returncode == 0
    except Exception as e:
        return f'{type(e).__name__}: {e}', False


def fetch_fx_rate():
    out, ok = _run('fetch_fx.py', ['--json'])
    if not ok:
        return {'rate': 7.80, 'source': 'HARDCODED_FALLBACK', 'error': out[-300:]}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {'rate': 7.80, 'source': 'PARSE_FAILED', 'error': out[-300:]}


_LEVERAGED_KEYWORDS = ('倍', 'Direxion', 'T-Rex', 'Defiance', 'ProShares',
                       '2X Long', '3X Long', '2x Long', '3x Long', 'Daily Target')


def _is_leveraged_etf(holding):
    """Heuristic: portfolio.json doesn't reliably set is_leveraged_etf.
    Detect via name keywords (Chinese 倍 + known sponsor names)."""
    if holding.get('is_leveraged_etf') is True:
        return True
    name = holding.get('name', '')
    return any(kw in name for kw in _LEVERAGED_KEYWORDS)


def collect_us_fundamentals(portfolio):
    """Pull SEC EDGAR --financials for each non-leveraged US single."""
    fundamentals = {}
    for h in portfolio['portfolios']['us_stocks']['holdings']:
        if h.get('shares', 0) <= 0 or _is_leveraged_etf(h):
            continue
        ticker = h['ticker']
        out, ok = _run('fetch_us_filings.py', [ticker, '--financials', '--json'], timeout=30)
        if not ok:
            fundamentals[ticker] = {'error': out[-300:]}
            continue
        try:
            fundamentals[ticker] = json.loads(out)
        except json.JSONDecodeError:
            fundamentals[ticker] = {'error': 'parse failed', 'raw': out[:300]}
    return fundamentals


def compute_concentration(holdings):
    """HHI + Top2 + per-holding weights for one leg."""
    active = [h for h in holdings if h.get('shares', 0) > 0]
    if not active:
        return {}
    total = sum(h.get('current_value', h['cost_basis'] * h['shares']) for h in active)
    if not total:
        return {'error': 'leg has zero total value'}

    weights = []
    for h in active:
        v = h.get('current_value', h['cost_basis'] * h['shares'])
        weights.append({
            'ticker':     h['ticker'],
            'value':      round(v, 2),
            'weight_pct': round(v / total * 100, 2),
            'leveraged':  bool(h.get('is_leveraged_etf')),
        })
    weights.sort(key=lambda x: -x['weight_pct'])

    hhi  = sum((w['weight_pct'] / 100) ** 2 for w in weights)
    top2 = sum(w['weight_pct'] for w in weights[:2])

    if hhi > 0.40:
        verdict = '🔴 危险集中'
    elif hhi > 0.25:
        verdict = '⚠️ 集中风险'
    elif hhi > 0.15:
        verdict = '偏集中'
    else:
        verdict = '✅ 健康'

    return {
        'hhi':        round(hhi, 3),
        'top2_pct':   round(top2, 1),
        'verdict':    verdict,
        'leg_total':  round(total, 2),
        'weights':    weights,
    }


def find_prior_plan(today_iso):
    """Most recent memory/*-plan.json with filename date < today."""
    candidates = sorted((WS / 'memory').glob('*-plan.json'))
    today_filename = f'{today_iso}-plan.json'
    prior = [p for p in candidates if p.name < today_filename]
    return prior[-1] if prior else None


def _is_hk_ticker(t):
    return t.isdigit() and len(t) <= 5


def compute_retrospective(prior_plan_path, portfolio):
    """For each action in prior plan, check trigger + simulate PnL."""
    if not prior_plan_path:
        return {'prior_plan_date': None, 'actions': [], 'note': 'first run (no prior plan)'}

    try:
        prior = json.loads(prior_plan_path.read_text())
    except Exception as e:
        return {'error': f'parse prior plan failed: {e}', 'path': str(prior_plan_path)}

    all_holdings = (portfolio['portfolios']['hk_stocks']['holdings'] +
                    portfolio['portfolios']['us_stocks']['holdings'])
    htmap = {h['ticker']: h for h in all_holdings}

    results = []
    for action in prior.get('actions', []):
        ticker = action.get('ticker')
        h = htmap.get(ticker)
        if not h:
            results.append({
                'ticker': ticker, 'error': 'ticker no longer in portfolio', 'plan': action,
            })
            continue

        trigger_type  = action.get('trigger_type', 'manual')
        trigger_price = action.get('trigger_price')
        size_shares   = action.get('size_shares')
        bucket        = action.get('bucket', '')

        current   = h.get('current_price', 0)
        prev_close = h.get('prev_close', current)
        open_px   = h.get('day_open', current)
        day_high  = h.get('day_high', current)
        day_low   = h.get('day_low', current)

        fired = None
        if trigger_type == 'open':
            fired = True
        elif trigger_type == 'price_above' and trigger_price is not None:
            fired = day_high >= trigger_price
        elif trigger_type == 'price_below' and trigger_price is not None:
            fired = day_low <= trigger_price
        # index_breakdown / event / manual → leave as None (LLM judges)

        sim_pnl = None
        execution_price = None
        if fired and size_shares:
            if trigger_type == 'open':
                execution_price = open_px
            elif trigger_price is not None:
                execution_price = trigger_price

            if execution_price is not None:
                # Sell-side actions: PnL = (execution - current) × shares (positive = good)
                if bucket in ('cut', 'trim_on_rebound', 't_only'):
                    sim_pnl = round((execution_price - current) * size_shares, 2)
                # Buy-side actions: PnL = (current - execution) × shares (positive = good)
                elif bucket == 'add_only_on_trigger':
                    sim_pnl = round((current - execution_price) * size_shares, 2)

        results.append({
            'ticker':                   ticker,
            'bucket':                   bucket,
            'plan_trigger_type':        trigger_type,
            'plan_trigger_price':       trigger_price,
            'plan_size_shares':         size_shares,
            'plan_confidence':          action.get('confidence'),
            'plan_rationale':           action.get('rationale'),
            'actual_open':              open_px,
            'actual_close':             current,
            'actual_day_high':          day_high,
            'actual_day_low':           day_low,
            'actual_prev_close':        prev_close,
            'trigger_fired':            fired,
            'simulated_execution_price': execution_price,
            'simulated_pnl':            sim_pnl,
            'pnl_currency':             'HKD' if _is_hk_ticker(ticker) else 'USD',
        })

    # Confidence calibration buckets
    def _calib(lo, hi):
        scored = [r for r in results
                  if r.get('plan_confidence') is not None
                  and lo <= r['plan_confidence'] < hi
                  and r['trigger_fired'] is not None]
        fired = sum(1 for r in scored if r['trigger_fired'])
        return f'{fired}/{len(scored)}' if scored else 'n/a'

    return {
        'prior_plan_date': prior.get('date'),
        'prior_plan_path': str(prior_plan_path),
        'actions':         results,
        'confidence_calibration': {
            'conf_80_100':  _calib(0.80, 1.01),
            'conf_60_79':   _calib(0.60, 0.80),
            'conf_below_60': _calib(0.0,  0.60),
        },
    }


def main():
    today = datetime.now().strftime('%Y-%m-%d')
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    issues = []

    print(f'═════ brief_preflight.py | {today} ═════')

    # [1] Refresh prices
    print('\n[1/7] Refresh US prices')
    us_out, us_ok = _run('analyze_us_stocks.py', ['--no-news'])
    if not us_ok:
        issues.append(f'US refresh failed: {us_out[-200:]}')
        print(f'   ⚠️  {issues[-1]}')
    else:
        print('   ✓ done')

    print('[2/7] Refresh HK prices')
    hk_out, hk_ok = _run('analyze_hk_stocks.py', ['--no-news'])
    if not hk_ok:
        issues.append(f'HK refresh failed: {hk_out[-200:]}')
        print(f'   ⚠️  {issues[-1]}')
    else:
        print('   ✓ done')

    # [3] FX
    print('[3/7] FX rate')
    fx = fetch_fx_rate()
    if 'error' in fx:
        issues.append(f'FX fallback used: {fx["error"][-200:]}')
    print(f'   USDHKD = {fx["rate"]}  ({fx["source"]})')

    # [4] Snapshot
    print('[4/7] Portfolio snapshot')
    portfolio_path = WS / 'portfolio.json'
    snapshot_path  = SNAPSHOT_DIR / f'{today}.json'
    snapshot_path.write_bytes(portfolio_path.read_bytes())
    print(f'   ✓ {snapshot_path.name}')

    # Load for downstream
    portfolio = json.loads(portfolio_path.read_text())

    # [5] Concentration
    print('[5/7] Concentration')
    hk_conc = compute_concentration(portfolio['portfolios']['hk_stocks']['holdings'])
    us_conc = compute_concentration(portfolio['portfolios']['us_stocks']['holdings'])
    print(f'   HK: HHI={hk_conc.get("hhi"):.3f} {hk_conc.get("verdict")} '
          f'(Top2 {hk_conc.get("top2_pct")}%)')
    print(f'   US: HHI={us_conc.get("hhi"):.3f} {us_conc.get("verdict")} '
          f'(Top2 {us_conc.get("top2_pct")}%)')

    # Book totals (FX-aware)
    rate = fx['rate']
    hk_pnl_hkd = portfolio['portfolios']['hk_stocks'].get('total_pnl', 0)
    us_pnl_usd = portfolio['portfolios']['us_stocks'].get('total_pnl', 0)
    book = {
        'hk_pnl_hkd':      round(hk_pnl_hkd, 2),
        'us_pnl_usd':      round(us_pnl_usd, 2),
        'usd_base_total':  round(hk_pnl_hkd / rate + us_pnl_usd, 2),
        'hkd_base_total':  round(hk_pnl_hkd + us_pnl_usd * rate, 2),
        'fx_used':         rate,
    }

    # [6] SEC EDGAR
    print('[6/7] SEC EDGAR US singles')
    us_fund = collect_us_fundamentals(portfolio)
    for t, data in us_fund.items():
        if 'error' in data:
            print(f'   ⚠️  {t}: {data["error"][:80]}')
            issues.append(f'SEC EDGAR {t} failed')
        else:
            kf = data.get('key_financials', {})
            print(f'   ✓ {t}: {len(kf)} concepts')

    # [7] Retrospective
    print('[7/7] Retrospective')
    prior_plan = find_prior_plan(today)
    retro = compute_retrospective(prior_plan, portfolio)
    if retro.get('prior_plan_date'):
        actions = retro['actions']
        fired = sum(1 for a in actions if a.get('trigger_fired') is True)
        not_fired = sum(1 for a in actions if a.get('trigger_fired') is False)
        ambiguous = sum(1 for a in actions if a.get('trigger_fired') is None and 'error' not in a)
        print(f'   prior plan: {retro["prior_plan_date"]}')
        print(f'   fired: {fired}   not fired: {not_fired}   ambiguous (manual/event): {ambiguous}')
        print(f'   conf cal: 80%+ {retro["confidence_calibration"]["conf_80_100"]}, '
              f'60-79% {retro["confidence_calibration"]["conf_60_79"]}')
    else:
        print(f'   first run (no prior plan)')

    # Write context.json
    context = {
        'generated_at':  datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'date':          today,
        'fx':            fx,
        'portfolio_path': str(portfolio_path),
        'snapshot_path': str(snapshot_path),
        'portfolio':     portfolio,
        'book_totals':   book,
        'concentration': {'hk': hk_conc, 'us': us_conc},
        'us_fundamentals': us_fund,
        'retrospective': retro,
        'issues':        issues,
    }
    ctx_path = TMP_DIR / f'brief-context-{today}.json'
    ctx_path.write_text(json.dumps(context, ensure_ascii=False, indent=2))

    print(f'\n═════ preflight done | {len(issues)} issues ═════')
    print(f'context: {ctx_path}')
    if issues:
        for i in issues:
            print(f'  ⚠️  {i}')
    return 0 if not issues else 1


if __name__ == '__main__':
    sys.exit(main())
