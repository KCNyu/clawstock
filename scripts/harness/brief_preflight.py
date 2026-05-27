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
  8. Peer scan
  9. Self-calibration
 10. Risk metrics
 11. Catalyst calendar (next 14d earnings + FOMC + macro)
 12. Write memory/.tmp/brief-context-{date}.json

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


def collect_peer_scan(portfolio):
    """For each active holding with a peer entry in peer-map.json, fetch peer
    prices and flag divergence (peer up significantly while holding flat/down)."""
    peer_map_path = WS / 'memory' / 'peer-map.json'
    if not peer_map_path.exists():
        return {}
    try:
        pmap = json.loads(peer_map_path.read_text()).get('holdings', {})
    except Exception as e:
        print(f'   ⚠️  peer-map.json parse failed: {e}')
        return {}

    # Index holdings by ticker for self-pct lookup
    h_by_ticker = {}
    for region in ('hk_stocks', 'us_stocks'):
        for h in portfolio['portfolios'].get(region, {}).get('holdings', []):
            if h.get('shares', 0) > 0:
                h_by_ticker[h['ticker']] = {
                    'pct_1d': h.get('today_change_pct', 0),
                    'pnl_pct': h.get('pnl_percent', 0),
                    'region': region,
                }

    # Collect all peer tickers we need
    peer_request = []
    seen = set()
    for ticker, info in pmap.items():
        if ticker not in h_by_ticker:  # holding inactive, skip
            continue
        for p in info.get('listed_peers', []):
            key = (p['ticker'], p['region'])
            if key not in seen:
                seen.add(key)
                peer_request.append({'ticker': p['ticker'], 'region': p['region']})

    if not peer_request:
        return {}

    # Call fetch_peers.py via subprocess
    try:
        import subprocess as sp
        r = sp.run(
            ['python3', str(WS / 'scripts' / 'data' / 'fetch_peers.py')],
            input=json.dumps(peer_request), capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            print(f'   ⚠️  fetch_peers.py failed: {r.stderr[-100:]}')
            return {}
        fetched = json.loads(r.stdout)['peers']
    except Exception as e:
        print(f'   ⚠️  peer fetch error: {e}')
        return {}

    # Build per-holding peer scan
    scan = {}
    for ticker, info in pmap.items():
        if ticker not in h_by_ticker:
            continue
        self_pct = h_by_ticker[ticker]['pct_1d'] or 0
        peer_results = []
        for p in info.get('listed_peers', []):
            pdata = fetched.get(p['ticker'], {})
            if 'price' in pdata:
                peer_results.append({
                    'ticker': p['ticker'],
                    'name': p['name'],
                    'rel': p['rel'],
                    'pct_1d': pdata.get('pct_1d'),
                    'pct_5d': pdata.get('pct_5d'),
                })

        # Sort by 1d pct desc
        peer_results.sort(key=lambda x: x.get('pct_1d') or -999, reverse=True)

        # Divergence: best peer outperformed holding by ≥3% today
        best_peer = peer_results[0] if peer_results else None
        divergence = None
        if best_peer and best_peer.get('pct_1d') is not None:
            diff = best_peer['pct_1d'] - self_pct
            if diff >= 3.0:
                divergence = f'{best_peer["ticker"]} {best_peer["name"]} {best_peer["pct_1d"]:+.1f}% vs self {self_pct:+.1f}% (gap {diff:+.1f}pp)'

        scan[ticker] = {
            'theme':            info.get('theme'),
            'self_pct_1d':      round(self_pct, 2),
            'self_pnl_pct':     h_by_ticker[ticker]['pnl_pct'],
            'listed_peers':     peer_results,
            'private_peers':    info.get('private_peers', []),
            'divergence_signal': divergence,
            'key_news_keywords': info.get('key_news_keywords', []),
        }
    return scan


def _shares_at_date(ticker, date_iso):
    """Get shares of `ticker` from portfolio.json as committed on/before `date_iso`.
    Returns int shares, or None if can't determine."""
    try:
        r = subprocess.run(
            ['git', '-C', str(WS), 'log', '--pretty=%H',
             f'--before={date_iso} 23:59:59', '-1', '--', 'portfolio.json'],
            capture_output=True, text=True, timeout=10)
        sha = r.stdout.strip()
        if not sha:
            return None
        r = subprocess.run(['git', '-C', str(WS), 'show', f'{sha}:portfolio.json'],
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return None
        pf = json.loads(r.stdout)
        for region in ('hk_stocks', 'us_stocks'):
            for h in pf['portfolios'][region]['holdings']:
                if h['ticker'] == ticker:
                    return int(h.get('shares', 0))
    except Exception:
        pass
    return None


def _detect_followed(row, min_window_days=None):
    """Compare shares on plan_date vs T+N. Return 'true' / 'false' / 'unknown'.

    Bucket → expected delta:
      cut / trim_on_rebound → shares should DECREASE
      add_only_on_trigger / add_on_breakout → shares should INCREASE
      hold_and_watch / watch / t_only → shares should be UNCHANGED

    min_window_days defaults to bucket-specific:
      hold_and_watch / watch / t_only → T+1 (held by next day = followed)
      cut / trim / add → T+2 (give user a working day to actually trade)
    """
    plan_date = row.get('plan_date')
    ticker = row.get('ticker')
    bucket = row.get('bucket', '').lower()
    if not (plan_date and ticker):
        return 'unknown'

    if min_window_days is None:
        min_window_days = 1 if bucket in ('hold_and_watch', 'watch', 't_only') else 2

    # Day BEFORE plan_date (last commit before plan was created)
    try:
        plan_dt = datetime.strptime(plan_date, '%Y-%m-%d')
        before_dt = (plan_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        after_dt = (plan_dt + timedelta(days=min_window_days)).strftime('%Y-%m-%d')
    except Exception:
        return 'unknown'

    # don't look ahead if window end is in the future
    if datetime.now() < plan_dt + timedelta(days=min_window_days):
        return 'unknown'  # too early; will retry next preflight

    shares_before = _shares_at_date(ticker, before_dt)
    shares_after  = _shares_at_date(ticker, after_dt)
    if shares_before is None or shares_after is None:
        return 'unknown'

    delta = shares_after - shares_before

    # Apply bucket rule
    if bucket in ('cut', 'trim_on_rebound'):
        return 'true' if delta < 0 else 'false'
    if bucket in ('add_only_on_trigger', 'add_on_breakout'):
        return 'true' if delta > 0 else 'false'
    if bucket in ('hold_and_watch', 'watch', 't_only'):
        return 'true' if delta == 0 else 'false'  # you held → followed; you bought/sold → didn't follow plan
    return 'unknown'  # 未识别 bucket


def _resolve_pending_followed():
    """Scan calibration.csv for rows with followed='unknown' and try to auto-detect
    via shares diff in git history. Runs every preflight — does NOT wait for the
    5-day outcome window. Returns updated row count.

    Separated from _resolve_pending_outcomes because:
    - followed answer often known within T+1 (hold_and_watch) or T+2 (trade buckets)
    - outcome resolution requires T+5 for price-move statistical significance
    - Previously these were coupled, so followed stayed 'unknown' for 5 days even
      when the answer was already determinable from portfolio.json shares diff.
    """
    calib_path = WS / 'memory' / 'calibration.csv'
    if not calib_path.exists():
        return 0

    import csv
    try:
        with open(calib_path, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return 0

    updated = 0
    for r in rows:
        if (r.get('followed') or 'unknown').lower() != 'unknown':
            continue
        verdict = _detect_followed(r)
        if verdict in ('true', 'false'):
            r['followed']    = verdict
            r['followed_at'] = datetime.now().isoformat() + ' (auto)'
            r['updated_at']  = datetime.now().isoformat()
            updated += 1

    if updated and rows:
        with open(calib_path, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    return updated


def _resolve_pending_outcomes():
    """Walk calibration.csv; for rows ≥5 days old with outcome=pending, compute
    actual outcome from snapshot history. Returns updated row count."""
    calib_path = WS / 'memory' / 'calibration.csv'
    if not calib_path.exists():
        return 0

    import csv
    try:
        with open(calib_path, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return 0

    today_iso = datetime.now().strftime('%Y-%m-%d')
    updated = 0
    for r in rows:
        if r.get('outcome') != 'pending':
            continue
        try:
            plan_dt = datetime.strptime(r['plan_date'], '%Y-%m-%d')
        except Exception:
            continue
        days_since = (datetime.now() - plan_dt).days
        if days_since < 5:
            continue  # too soon to evaluate

        # Look at portfolio.json's holding for this ticker
        try:
            pf = json.loads((WS / 'portfolio.json').read_text())
        except Exception:
            continue
        all_holdings = (pf['portfolios']['hk_stocks']['holdings'] +
                        pf['portfolios']['us_stocks']['holdings'])
        h = next((x for x in all_holdings if x['ticker'] == r['ticker']), None)
        if not h:
            r['outcome'] = 'unknown'
            r['updated_at'] = datetime.now().isoformat()
            updated += 1
            continue

        # Simulate outcome: did the action "win" 5 days later?
        # cut / trim: win if current_price < sim_entry_price (sold high)
        # add_only_on_trigger: win if current_price > sim_entry_price
        # hold_and_watch / t_only: win if pnl_pct > 0 (price went up after we decided to hold)
        bucket = r.get('bucket', '')
        cur = h.get('current_price', 0)
        try:
            entry = float(r.get('sim_entry_price') or 0)
        except Exception:
            entry = 0

        outcome = 'unknown'
        pnl_5d = ''
        if bucket in ('cut', 'trim_on_rebound', 't_only') and entry:
            pnl_5d_val = (entry - cur) / entry * 100  # positive = sold high, good
            outcome = 'win' if pnl_5d_val > 0 else 'loss'
            pnl_5d = round(pnl_5d_val, 2)
        elif bucket == 'add_only_on_trigger' and entry:
            pnl_5d_val = (cur - entry) / entry * 100
            outcome = 'win' if pnl_5d_val > 0 else 'loss'
            pnl_5d = round(pnl_5d_val, 2)
        elif bucket == 'hold_and_watch':
            pnl_5d_val = h.get('today_change_pct', 0)  # rough proxy
            outcome = 'win' if pnl_5d_val >= 0 else 'loss'
            pnl_5d = round(pnl_5d_val, 2)

        r['outcome'] = outcome
        r['pnl_5d'] = pnl_5d
        # Auto-detect followed by comparing portfolio.json shares (git history)
        if (r.get('followed') or 'unknown').lower() == 'unknown':
            r['followed'] = _detect_followed(r)
            if r['followed'] in ('true', 'false'):
                r['followed_at'] = datetime.now().isoformat() + ' (auto)'
        r['updated_at'] = datetime.now().isoformat()
        updated += 1

    if updated:
        with open(calib_path, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    return updated


def compute_self_calibration():
    """Read memory/calibration.csv accumulated by past brief postflights;
    compute Brier score + per-bucket win rate over rolling 30 days."""
    _resolve_pending_followed()  # T+1/T+2 followed detection (cheap, every run)
    _resolve_pending_outcomes()  # T+5 outcome resolution (statistical window)

    calib_path = WS / 'memory' / 'calibration.csv'
    if not calib_path.exists():
        return {'samples': 0, 'note': 'no calibration log yet (first runs)'}

    import csv
    rows = []
    try:
        with open(calib_path, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                rows.append(row)
    except Exception as e:
        return {'samples': 0, 'note': f'calibration read failed: {e}'}

    # Filter to last 30 days with outcome known
    cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    scored = []
    for r in rows:
        if r.get('plan_date', '') < cutoff:
            continue
        try:
            conf = float(r.get('confidence', 0))
        except Exception:
            continue
        outcome = r.get('outcome', '')  # 'win', 'loss', 'pending'
        if outcome not in ('win', 'loss'):
            continue
        # Tier 1.1: only count plans you actually followed
        # 'unknown' / 'true' / 'false' — only 'true' counted for calibration
        followed = (r.get('followed') or 'unknown').lower()
        if followed != 'true':
            continue
        actual = 1.0 if outcome == 'win' else 0.0
        scored.append({
            'bucket': r.get('bucket', ''),
            'confidence': conf,
            'actual':     actual,
            'brier':      (conf - actual) ** 2,
        })

    if not scored:
        return {'samples': len(rows), 'note': f'{len(rows)} plans logged but no outcomes resolved yet'}

    # Brier score
    brier_30d = sum(r['brier'] for r in scored) / len(scored)

    # Per-bucket
    buckets = {}
    for r in scored:
        b = r['bucket']
        buckets.setdefault(b, {'n': 0, 'wins': 0, 'conf_sum': 0})
        buckets[b]['n'] += 1
        buckets[b]['wins'] += int(r['actual'])
        buckets[b]['conf_sum'] += r['confidence']
    per_bucket = {b: {
        'n': v['n'], 'win_rate': v['wins'] / v['n'],
        'avg_confidence': v['conf_sum'] / v['n'],
        'calibration_gap': (v['conf_sum'] / v['n']) - (v['wins'] / v['n']),
    } for b, v in buckets.items()}

    # Per-confidence-bucket actual win rate
    conf_buckets = {'50-60': [], '60-70': [], '70-80': [], '80-90': [], '90-100': []}
    for r in scored:
        c = r['confidence']
        for k, lo, hi in [('50-60',0.50,0.60),('60-70',0.60,0.70),('70-80',0.70,0.80),('80-90',0.80,0.90),('90-100',0.90,1.01)]:
            if lo <= c < hi:
                conf_buckets[k].append(r['actual'])
                break
    conf_table = {k: {'n': len(v), 'actual_win_rate': sum(v)/len(v) if v else None} for k, v in conf_buckets.items()}

    return {
        'samples': len(scored),
        'brier_30d': round(brier_30d, 4),
        'brier_quality': 'good' if brier_30d < 0.20 else ('marginal' if brier_30d < 0.30 else 'poor — confidence is unreliable'),
        'per_bucket': per_bucket,
        'per_confidence_band': conf_table,
        'note': 'lower Brier = better calibrated. < 0.20 good, > 0.30 means model is overconfident',
    }


def main():
    today = datetime.now().strftime('%Y-%m-%d')
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    issues = []

    print(f'═════ brief_preflight.py | {today} ═════')

    # [1] Refresh prices
    print('\n[1/11] Refresh US prices')
    us_out, us_ok = _run('analyze_us_stocks.py', ['--no-news'])
    if not us_ok:
        issues.append(f'US refresh failed: {us_out[-200:]}')
        print(f'   ⚠️  {issues[-1]}')
    else:
        print('   ✓ done')

    print('[2/11] Refresh HK prices')
    hk_out, hk_ok = _run('analyze_hk_stocks.py', ['--no-news'])
    if not hk_ok:
        issues.append(f'HK refresh failed: {hk_out[-200:]}')
        print(f'   ⚠️  {issues[-1]}')
    else:
        print('   ✓ done')

    # [3] FX
    print('[3/11] FX rate')
    fx = fetch_fx_rate()
    if 'error' in fx:
        issues.append(f'FX fallback used: {fx["error"][-200:]}')
    print(f'   USDHKD = {fx["rate"]}  ({fx["source"]})')

    # [4] Snapshot
    print('[4/11] Portfolio snapshot')
    portfolio_path = WS / 'portfolio.json'
    snapshot_path  = SNAPSHOT_DIR / f'{today}.json'
    snapshot_path.write_bytes(portfolio_path.read_bytes())
    print(f'   ✓ {snapshot_path.name}')

    # Load for downstream
    portfolio = json.loads(portfolio_path.read_text())

    # [5] Concentration
    print('[5/11] Concentration')
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
    print('[6/11] SEC EDGAR US singles')
    us_fund = collect_us_fundamentals(portfolio)
    for t, data in us_fund.items():
        if 'error' in data:
            print(f'   ⚠️  {t}: {data["error"][:80]}')
            issues.append(f'SEC EDGAR {t} failed')
        else:
            kf = data.get('key_financials', {})
            print(f'   ✓ {t}: {len(kf)} concepts')

    # [7] Retrospective
    print('[7/11] Retrospective')
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

    # [8] Peer scan — for each active holding, fetch peer prices + flag divergence
    print('[8/11] Peer scan')
    peer_scan = collect_peer_scan(portfolio)
    print(f'   {len(peer_scan)} holdings with peer data; {sum(1 for h in peer_scan.values() if h.get("divergence_signal"))} divergence signals')

    # [9] Self-calibration — read past plan outcomes and compute confidence accuracy
    print('[9/11] Self-calibration')
    self_calib = compute_self_calibration()
    if self_calib.get('samples', 0) >= 5 and 'brier_30d' in self_calib:
        print(f'   Brier (30d): {self_calib["brier_30d"]:.3f}  ({self_calib["samples"]} samples)')
        for bucket, stats in self_calib.get('per_bucket', {}).items():
            print(f'   {bucket:24s} n={stats["n"]} win_rate={stats["win_rate"]:.0%}')
    else:
        print(f'   not enough data yet (need ≥5 plans, have {self_calib.get("samples", 0)})')

    # [10] Risk metrics — Tier 2: β / vol / DD / Sharpe / margin sim
    print('[10/11] Risk metrics')
    risk = {}
    try:
        subprocess.run(['python3', str(WS / 'scripts' / 'data' / 'portfolio_risk_metrics.py')],
                       capture_output=True, text=True, timeout=120, check=False)
        risk_path = WS / 'assets' / 'data' / 'risk.json'
        if risk_path.exists():
            risk = json.loads(risk_path.read_text())
            alerts = risk.get('alerts', [])
            print(f'   US β={risk.get("us",{}).get("beta_spx","?")}, combined vol={risk.get("combined",{}).get("vol_30d_annualized","?")}, alerts={len(alerts)}')
            for a in alerts[:5]:
                print(f'   ⚠ {a["type"]:18s} ({a["severity"]:6s}) {a["detail"][:80]}')
    except Exception as e:
        print(f'   ⚠ risk metrics failed: {e}')

    # [11] Catalyst calendar — next 14d earnings + FOMC + macro
    print('[11/11] Fetch catalysts')
    catalysts = {}
    try:
        cat_out, cat_ok = _run('scripts/data/fetch_catalysts.py', ['--json'], timeout=60)
        if not cat_ok:
            print(f'   ⚠ catalysts fetch failed: {cat_out[-150:]}')
            issues.append('catalysts fetch failed')
        else:
            catalysts = json.loads(cat_out)
            summary = catalysts.get('summary', {})
            print(f'   earnings: {summary.get("earnings_count", 0)}, '
                  f'FOMC: {summary.get("fomc_in_window", 0)}, '
                  f'macro: {summary.get("macro_count", 0)}')
            hi = summary.get('highest_impact_within_7d')
            if hi:
                print(f'   highest impact 7d: {hi}')
            if 'error' in catalysts:
                print(f'   ⚠ partial errors: {list(catalysts["error"].keys())}')
    except Exception as e:
        print(f'   ⚠ catalysts step failed: {e}')
        issues.append(f'catalysts step exception: {type(e).__name__}')

    # Benchmark history (SPY + HSI/HSTECH) for the Equity Curve overlay.
    # Refreshed once per day at brief time; consumed by build_dashboard.
    print('[12/12] Fetch benchmark history')
    try:
        bm_out, bm_ok = _run('scripts/data/fetch_benchmark_history.py', timeout=30)
        if not bm_ok:
            print(f'   ⚠ benchmark fetch failed: {bm_out[-150:]}')
            issues.append('benchmark history fetch failed')
        else:
            # Surface a one-line summary
            tail = bm_out.strip().splitlines()[-1] if bm_out.strip() else ''
            print(f'   {tail}')
    except Exception as e:
        print(f'   ⚠ benchmark step failed: {e}')
        issues.append(f'benchmark step exception: {type(e).__name__}')

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
        'peer_scan':     peer_scan,
        'self_calibration': self_calib,
        'risk_metrics':  risk,
        'catalysts':     catalysts,
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
