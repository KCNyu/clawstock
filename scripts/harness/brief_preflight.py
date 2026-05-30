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
 12. Benchmark history (SPY + HSI/HSTECH) for equity curve overlay
 13. Load macro + sentiment snapshots (read assets/data/{macro,sentiment}.json)
 14. Write memory/.tmp/brief-context-{date}.json

Output (stdout): step-by-step progress; final summary with issue count.
Exit: 0 if no issues, 1 if any data leg failed.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Resolve workspace root from this file's location, NOT a hardcoded path: this
# script runs both under openclaw cron (local /root/.openclaw/workspace) AND on
# GH Action runners (brief-fallback.yml, checkout dir). A hardcoded /root path
# made preflight write context to a nonexistent path on the runner → the fallback
# brief then FATAL'd with "no preflight context" (2026-05-30 fix). parents[2] =
# scripts/harness/<this> → workspace root, correct in both environments.
WS = Path(__file__).resolve().parents[2]
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
    out, ok = _run('scripts/data/fetch_fx.py', ['--json'])
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
        out, ok = _run('scripts/data/fetch_us_filings.py', [ticker, '--financials', '--json'], timeout=30)
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


def _snapshot_price(date_iso, ticker):
    """current_price of `ticker` in the daily snapshot for date_iso, or None."""
    p = WS / 'memory' / 'snapshots' / f'{date_iso}.json'
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
    except Exception:
        return None
    for region in ('hk_stocks', 'us_stocks'):
        for h in d.get('portfolios', {}).get(region, {}).get('holdings', []):
            if h.get('ticker') == ticker:
                cp = h.get('current_price')
                try:
                    return float(cp) if cp else None
                except Exception:
                    return None
    return None


def _next_session_date(plan_date):
    """First snapshot date strictly after plan_date (snapshots exist one-per-trading-
    session, so this IS the next session — weekends/holidays skipped for free).
    None if no later snapshot exists yet (next session hasn't happened)."""
    import glob, os
    dates = sorted(os.path.basename(p)[:-5]
                   for p in glob.glob(str(WS / 'memory' / 'snapshots' / '20*.json')))
    for d in dates:
        if d > plan_date:
            return d
    return None


def _resolve_pending_outcomes():
    """Settle each pending calibration row at T+1 (the NEXT trading session) by
    backtesting "if the call had been followed".

    The brief predicts the next session, so the evaluation horizon is one session —
    NOT 5 days (corrected 2026-05-30; the old 5-day window + today_change_pct proxy
    measured noise and could never score an executed cut). Outcome = did following the
    call pay off over D→D+1, priced from the daily snapshots:
      cut / trim          → sold at D; win if the asset FELL by D+1 (dodged the drop)
      add_only_on_trigger → bought at D; win if it ROSE by D+1
      hold_and_watch/t_only/watch → kept exposure; win if it ROSE (≥0) by D+1
    The `pnl_5d` column (legacy name; kept to avoid a cross-file/​frontend rename) now
    stores the signed *benefit of following* %, so positive always = the call helped.
    Returns updated row count."""
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
        if r.get('outcome') != 'pending':
            continue
        plan_date = r.get('plan_date')
        ticker = r.get('ticker')
        if not (plan_date and ticker):
            continue
        d1 = _next_session_date(plan_date)
        if not d1:
            continue  # next session hasn't happened yet → leave pending

        # D price: the plan's recorded sim_entry (≈ D close); fall back to D's snapshot.
        try:
            price_d = float(r.get('sim_entry_price') or 0) or None
        except Exception:
            price_d = None
        if not price_d:
            price_d = _snapshot_price(plan_date, ticker)
        price_d1 = _snapshot_price(d1, ticker)

        if not price_d or not price_d1:
            r['outcome'] = 'unknown'
            r['pnl_5d'] = ''
            r['updated_at'] = datetime.now().isoformat()
            updated += 1
            continue

        ret = (price_d1 - price_d) / price_d * 100.0   # next-session asset return
        bucket = (r.get('bucket') or '').lower()
        if bucket in ('cut', 'trim_on_rebound'):
            benefit = -ret                              # selling helped if it fell
        else:                                           # add / hold / t_only / watch
            benefit = ret
        r['outcome'] = 'win' if benefit > 0 else 'loss'
        r['pnl_5d'] = round(benefit, 2)
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


def _advice_track_record(rows, cutoff):
    """Score the model's ADVICE over ALL settled rows (regardless of followed) — the
    unfiltered view that compute_self_calibration's followed-only block hides. Lets the
    brief see whether its active cut/trim/add signals actually beat a coin flip and
    whether its high-confidence calls are overconfident (2026-05-30)."""
    ACTIVE = {'cut', 'trim_on_rebound', 'add_only_on_trigger', 'add_on_breakout'}
    scored = []
    for r in rows:
        if r.get('plan_date', '') < cutoff or r.get('outcome') not in ('win', 'loss'):
            continue
        try:
            conf = float(r.get('confidence', 0))
        except Exception:
            conf = None
        scored.append({'bucket': r.get('bucket', ''), 'confidence': conf,
                       'win': 1 if r.get('outcome') == 'win' else 0})

    def _agg(seg):
        if not seg:
            return None
        n = len(seg)
        wr = sum(s['win'] for s in seg) / n
        confs = [s['confidence'] for s in seg if s['confidence'] is not None]
        out = {'n': n, 'win_rate': round(wr, 2)}
        if confs:
            avg_c = sum(confs) / len(confs)
            out['avg_confidence'] = round(avg_c, 2)
            out['overconfidence_gap'] = round(avg_c - wr, 2)  # >0 = overconfident
        return out

    return {
        'horizon': 'T+1 (next session)',
        'n_settled': len(scored),
        'active_signals': _agg([s for s in scored if s['bucket'] in ACTIVE]),
        'passive_holds':  _agg([s for s in scored if s['bucket'] not in ACTIVE]),
        'per_bucket': {b: _agg([s for s in scored if s['bucket'] == b])
                       for b in sorted(set(s['bucket'] for s in scored))},
        'per_confidence_band': {k: _agg([s for s in scored
                                         if s['confidence'] is not None and lo <= s['confidence'] < hi])
                                for k, lo, hi in [('0.50-0.65', 0.50, 0.65),
                                                  ('0.65-0.75', 0.65, 0.75),
                                                  ('>=0.75', 0.75, 1.01)]},
        'note': 'win_rate over ALL settled calls (not just followed). active <0.50 = '
                'signals add no edge; overconfidence_gap >0 on high bands = trim confidence.',
    }


def compute_self_calibration():
    """Read memory/calibration.csv accumulated by past brief postflights;
    compute Brier score + per-bucket win rate over rolling 30 days."""
    _resolve_pending_followed()  # T+1/T+2 followed detection (cheap, every run)
    _resolve_pending_outcomes()  # T+1 next-session outcome resolution (2026-05-30)

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
        return {'samples': len(rows),
                'note': f'{len(rows)} plans logged but no followed-outcomes resolved yet',
                'advice_track_record': _advice_track_record(rows, cutoff)}

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
        'advice_track_record': _advice_track_record(rows, cutoff),
        'note': 'lower Brier = better calibrated. < 0.20 good, > 0.30 means model is overconfident. '
                'See advice_track_record for the unfiltered (all-settled) view of advice quality.',
    }


def load_macro_and_sentiment(today, issues):
    """Read GH-Action-produced macro.json + sentiment.json; trim to LLM-friendly subset.

    Files are written daily by sentiment-scan.yml / macro-scan.yml. Stale (>36h)
    or missing files emit a non-fatal warn — brief still runs, just without these
    sections.

    Returns: (macro_trim, sentiment_trim) — either may be {} on miss.
    """
    macro_path = WS / 'assets' / 'data' / 'macro.json'
    sent_path  = WS / 'assets' / 'data' / 'sentiment.json'
    stale_cutoff_h = 36

    def _age_hours(path):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            return (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
        except Exception:
            return None

    macro_trim = {}
    try:
        if not macro_path.exists():
            print(f'   ⚠ macro.json missing — sentiment-scan never ran')
            issues.append('macro snapshot missing')
        else:
            age = _age_hours(macro_path)
            m = json.loads(macro_path.read_text())
            def _q(k):
                v = m.get(k)
                if not v: return None
                return {'price': v.get('price'), 'change_pct': v.get('change_pct'),
                        'source': v.get('source')}
            macro_trim = {
                'as_of':        m.get('generated_at'),
                'age_hours':    round(age, 1) if age is not None else None,
                'vix':          _q('vix'),
                'dxy':          _q('dxy'),
                'treasury_10y_yield_pct': (m.get('treasury_10y') or {}).get('yield_pct'),
                'fear_greed':   m.get('fear_greed'),
                'hsi':          _q('hsi'),
                'hstech':       _q('hstech'),
                'spx':          _q('spx'),
                'nasdaq':       _q('nasdaq'),
                'fed_press':    (m.get('fed_press') or [])[:3],
            }
            if age and age > stale_cutoff_h:
                print(f'   ⚠ macro stale ({age:.1f}h old, cutoff {stale_cutoff_h}h)')
                issues.append(f'macro snapshot stale {age:.0f}h')
            else:
                fg = macro_trim['fear_greed'] or {}
                print(f'   macro: VIX {(macro_trim["vix"] or {}).get("price","?")}, '
                      f'F&G {fg.get("score","?")} ({fg.get("rating","?")}), '
                      f'fed_press {len(macro_trim["fed_press"])}')
    except Exception as e:
        print(f'   ⚠ macro load failed: {e}')
        issues.append(f'macro load exception: {type(e).__name__}')

    sentiment_trim = {}
    try:
        if not sent_path.exists():
            print(f'   ⚠ sentiment.json missing — sentiment-scan never ran')
            issues.append('sentiment snapshot missing')
        else:
            age = _age_hours(sent_path)
            s = json.loads(sent_path.read_text())
            tickers_out = []
            for t in s.get('tickers', []):
                reddit_n  = t.get('reddit_mentions_7d', 0)
                gn_en     = t.get('google_news_en') or []
                gn_zh     = t.get('google_news_zh') or []
                # Skip noise: 0 mention + 0 news
                if reddit_n == 0 and not gn_en and not gn_zh:
                    continue
                tickers_out.append({
                    'ticker': t.get('ticker'),
                    'name':   t.get('name'),
                    'region': t.get('region'),
                    'reddit_mentions_7d': reddit_n,
                    'reddit_top': [{'title': p.get('title'), 'score': p.get('score'),
                                    'comments': p.get('num_comments')}
                                   for p in (t.get('reddit_posts') or [])[:3]],
                    'news_top':   [n.get('title') for n in (gn_en + gn_zh)[:3] if n.get('title')],
                })
            sentiment_trim = {
                'as_of':       s.get('generated_at'),
                'age_hours':   round(age, 1) if age is not None else None,
                'sources':     s.get('sources', []),
                'tickers':     tickers_out,
            }
            if age and age > stale_cutoff_h:
                print(f'   ⚠ sentiment stale ({age:.1f}h old, cutoff {stale_cutoff_h}h)')
                issues.append(f'sentiment snapshot stale {age:.0f}h')
            else:
                with_signal = sum(1 for t in tickers_out if t['reddit_mentions_7d'] or t['news_top'])
                print(f'   sentiment: {with_signal}/{len(s.get("tickers",[]))} tickers '
                      f'have reddit/news signal')
    except Exception as e:
        print(f'   ⚠ sentiment load failed: {e}')
        issues.append(f'sentiment load exception: {type(e).__name__}')

    return macro_trim, sentiment_trim


def load_influencer_feed(issues):
    """Read GH-Action-produced influencer_feed.json (Trump/Musk radar).

    Written by influencer-scan.yml before the brief. Stale (>36h)/missing → warn,
    brief still runs without the 名人异动 section. Returns trimmed dict or {}.
    """
    path = WS / 'assets' / 'data' / 'influencer_feed.json'
    try:
        if not path.exists():
            print('   ⚠ influencer_feed.json missing — influencer-scan never ran')
            issues.append('influencer feed missing')
            return {}
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        age = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
        d = json.loads(path.read_text())
        # Trim each item to the fields the brief needs.
        def _trim(it):
            return {k: it.get(k) for k in
                    ('author', 'stance', 'relevance', 'held', 'new_ideas',
                     'sector_holdings', 'sectors', 'summary_cn')}
        out = {
            'as_of':     d.get('generated_at'),
            'age_hours': round(age, 1),
            'counts':    d.get('counts', {}),
            'held_hits': [_trim(x) for x in d.get('held_hits', [])][:6],
            'new_ideas': [_trim(x) for x in d.get('new_ideas', [])][:6],
            'sector_hits': [_trim(x) for x in d.get('sector_hits', [])][:4],
        }
        if age > 36:
            print(f'   ⚠ influencer feed stale ({age:.1f}h old)')
            issues.append(f'influencer feed stale {age:.0f}h')
        else:
            c = out['counts']
            print(f'   influencer: {c.get("held_hits",0)} held-hits, '
                  f'{c.get("new_ideas",0)} new-ideas, {c.get("sector_hits",0)} sector')
        return out
    except Exception as e:
        print(f'   ⚠ influencer feed load failed: {e}')
        issues.append(f'influencer load exception: {type(e).__name__}')
        return {}


def main():
    # Date in HKT (the system's canonical TZ), or honor the TODAY env that the
    # brief-fallback workflow exports — so the context filename here always matches
    # the date the fallback script reads. Naive now() = runner UTC, which mismatched
    # HKT in the 16:00–23:59 UTC window and broke off-schedule fallback runs.
    today = (os.environ.get('TODAY')
             or datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d'))
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    issues = []

    print(f'═════ brief_preflight.py | {today} ═════')

    # [1] Refresh prices
    print('\n[1/11] Refresh US prices')
    us_out, us_ok = _run('scripts/data/analyze_us_stocks.py', ['--no-news'])
    if not us_ok:
        issues.append(f'US refresh failed: {us_out[-200:]}')
        print(f'   ⚠️  {issues[-1]}')
    else:
        print('   ✓ done')

    print('[2/11] Refresh HK prices')
    hk_out, hk_ok = _run('scripts/data/analyze_hk_stocks.py', ['--no-news'])
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
    atr = self_calib.get('advice_track_record') or {}
    if atr.get('n_settled'):
        act, pas = atr.get('active_signals'), atr.get('passive_holds')
        if act:
            print(f'   advice (T+1, all settled n={atr["n_settled"]}): '
                  f'active {act["win_rate"]:.0%} (conf {act.get("avg_confidence",0):.2f}, '
                  f'overconf +{act.get("overconfidence_gap",0):.2f}) | '
                  f'passive {pas["win_rate"]:.0%}' if pas else '')
        hi = (atr.get('per_confidence_band') or {}).get('>=0.75')
        if hi:
            print(f'   ⚠ high-conf (≥0.75) win_rate {hi["win_rate"]:.0%} — overconfidence_gap +{hi.get("overconfidence_gap",0):.2f}')

    # [10] Risk metrics — Tier 2: β / vol / DD / Sharpe / margin sim
    print('[10/11] Risk metrics')
    risk = {}
    try:
        r = subprocess.run(['python3', str(WS / 'scripts' / 'data' / 'portfolio_risk_metrics.py')],
                           capture_output=True, text=True, timeout=180, check=False)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or '')[-500:]
            print(f'   ⚠ risk metrics exited {r.returncode}: ...{tail}')
        risk_path = WS / 'assets' / 'data' / 'risk.json'
        if risk_path.exists():
            risk = json.loads(risk_path.read_text())
            # Freshness check — silent failures can leave a stale file in place
            from datetime import datetime as _dt, timezone as _tz
            gen = risk.get('generated_at', '')
            try:
                age_h = (_dt.now(_tz.utc) - _dt.fromisoformat(gen.replace('Z','+00:00'))).total_seconds() / 3600
                if age_h > 26:  # daily refresh; >1 day = stale
                    print(f'   ⚠ risk.json stale: generated_at={gen} ({age_h:.0f}h ago)')
            except Exception:
                pass
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
    print('[12/13] Fetch benchmark history')
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

    # [13] Macro + sentiment snapshots — written by GH Action (macro-scan / sentiment-scan).
    # Read-only here; brief LLM consumes the trimmed subset so "▎大盘速读" and
    # "▎社交舆情速读" sections aren't flying blind.
    print('[13/13] Load macro + sentiment + influencer snapshots')
    macro_trim, sentiment_trim = load_macro_and_sentiment(today, issues)
    influencer_trim = load_influencer_feed(issues)

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
        'macro':         macro_trim,
        'sentiment':     sentiment_trim,
        'influencer':    influencer_trim,
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
