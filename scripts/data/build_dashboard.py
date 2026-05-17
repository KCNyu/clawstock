#!/usr/bin/env python3
"""
build_dashboard.py — aggregates portfolio.json + snapshots + plans into a single
JSON the static dashboard (docs/ via Jekyll Pages) consumes.

Output: assets/data/dashboard.json

Run after each portfolio mutation (cron commit) so Pages stays fresh.
"""
import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

WS_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = WS_ROOT / 'assets' / 'data'
OUT_FILE = OUT_DIR / 'dashboard.json'

# ── Anti-bloat caps ──────────────────────────────────────────────────────
# Dashboard only embeds the most recent snapshots + plan summaries.
# Older history lives on disk; if dashboard ever needs full history, load lazily.
MAX_SNAPSHOTS_EMBEDDED = 90        # ≈ 4 months of trading days (kept in dashboard.json)
MAX_PLANS_EMBEDDED     = 5         # last 5 plans (each can be a few KB)
MAX_PLAN_BYTES         = 4096      # cap each plan blob to 4KB; if larger, just keep summary
MAX_OUT_BYTES          = 200_000   # final dashboard.json hard cap (~200KB)


def load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'  warn: failed to load {path}: {e}', file=sys.stderr)
        return None


def trim_holding(h, currency):
    """Trim a holding dict to UI-relevant fields."""
    return {
        'ticker': h.get('ticker') or h.get('code'),
        'name': h.get('name', ''),
        'currency': currency,
        'shares': h.get('shares', 0),
        'cost_basis': round(h.get('cost_basis') or 0, 4),
        'current_price': round(h.get('current_price') or 0, 4),
        'current_value': round(h.get('current_value') or 0, 2),
        'pnl_abs': round(h.get('pnl_abs') or 0, 2),
        'pnl_percent': round(h.get('pnl_percent') or 0, 2),
        'today_change_pct': round(h.get('today_change_pct') or 0, 2),
        'is_active': (h.get('shares') or 0) > 0,
        'trades_count': len(h.get('trades') or []),
    }


def compute_hhi(holdings):
    """HHI = Σ weight²; return (hhi, top2, weights[], total_value)."""
    active = [h for h in holdings if h['is_active'] and h['current_value'] > 0]
    total = sum(h['current_value'] for h in active)
    if total <= 0:
        return {'hhi': 0, 'top2': 0, 'positions': [], 'total': 0}
    weights = []
    for h in active:
        w = h['current_value'] / total
        weights.append({
            'ticker': h['ticker'],
            'name': h['name'],
            'value': h['current_value'],
            'weight': round(w, 4),
        })
    weights.sort(key=lambda x: -x['weight'])
    hhi = round(sum(w['weight'] ** 2 for w in weights), 4)
    top2 = round(sum(w['weight'] for w in weights[:2]), 4)
    return {'hhi': hhi, 'top2': top2, 'positions': weights, 'total': round(total, 2)}


def hhi_verdict(hhi, top2):
    if hhi < 0.15 and top2 < 0.40:
        return {'level': 'healthy', 'label': '健康', 'color': '#4ade80'}
    if hhi < 0.25 and top2 < 0.60:
        return {'level': 'moderate', 'label': '偏集中', 'color': '#facc15'}
    if hhi < 0.40 and top2 < 0.75:
        return {'level': 'concentrated', 'label': '集中风险', 'color': '#fb923c'}
    return {'level': 'danger', 'label': '危险集中', 'color': '#ef4444'}


def load_snapshots():
    """Returns recent-N snapshot summaries (NOT full holdings). Capped at MAX_SNAPSHOTS_EMBEDDED."""
    paths = sorted(glob.glob(str(WS_ROOT / 'memory' / 'snapshots' / '*.json')))
    # Keep only the most recent N — chronological order so dashboard line chart still ascends
    paths = paths[-MAX_SNAPSHOTS_EMBEDDED:]
    results = []
    for p in paths:
        d = load_json(p)
        if not d:
            continue
        fname = os.path.basename(p)
        # filename: YYYY-MM-DD.json or YYYY-MM-DD-tag.json
        date = fname.split('.')[0].split('-')
        date = '-'.join(date[:3]) if len(date) >= 3 else fname
        pf = d.get('portfolios', {})
        us = pf.get('us_stocks', {})
        hk = pf.get('hk_stocks', {})
        results.append({
            'date': date,
            'file': fname,
            'us_total_value': us.get('total_current_value', 0),
            'us_total_cost': us.get('total_cost', 0),
            'us_total_pnl': us.get('total_pnl', 0),
            'us_today_change': us.get('today_total_change', 0),
            'hk_total_value': hk.get('total_current_value', 0),
            'hk_total_cost': hk.get('total_cost', 0),
            'hk_total_pnl': hk.get('total_pnl', 0),
            'hk_today_change': hk.get('today_total_change', 0),
        })
    return results


def load_plans():
    """Recent-N plan summaries. Large plans get trimmed to bullet list."""
    paths = sorted(glob.glob(str(WS_ROOT / 'memory' / '*-plan.json')))
    paths = paths[-MAX_PLANS_EMBEDDED:]
    results = []
    for p in paths:
        d = load_json(p)
        if not d:
            continue
        fname = os.path.basename(p)
        date = fname.replace('-plan.json', '')
        raw = json.dumps(d, ensure_ascii=False)
        if len(raw.encode('utf-8')) > MAX_PLAN_BYTES:
            # Plan too big — keep only top-level summary fields (actions count, tldr)
            actions = d.get('actions') or d.get('plan') or []
            d = {
                'date': d.get('date', date),
                'actions_count': len(actions),
                'tldr': d.get('summary') or d.get('tldr') or '',
                'has_retrospective': bool(d.get('retrospective')),
                'context': d.get('context', {}),
                'truncated': True,
                'original_bytes': len(raw),
            }
        results.append({'date': date, 'file': fname, 'plan': d})
    return results


def total_plans_count():
    return len(glob.glob(str(WS_ROOT / 'memory' / '*-plan.json')))


def total_snapshots_count():
    return len(glob.glob(str(WS_ROOT / 'memory' / 'snapshots' / '*.json')))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    portfolio = load_json(WS_ROOT / 'portfolio.json')
    if not portfolio:
        print('FATAL: portfolio.json missing', file=sys.stderr)
        return 1

    us_pf = portfolio['portfolios']['us_stocks']
    hk_pf = portfolio['portfolios']['hk_stocks']

    us_h = [trim_holding(h, 'USD') for h in us_pf.get('holdings', [])]
    hk_h = [trim_holding(h, 'HKD') for h in hk_pf.get('holdings', [])]

    us_conc = compute_hhi(us_h)
    hk_conc = compute_hhi(hk_h)
    us_conc['verdict'] = hhi_verdict(us_conc['hhi'], us_conc['top2'])
    hk_conc['verdict'] = hhi_verdict(hk_conc['hhi'], hk_conc['top2'])

    fx_cache = load_json(WS_ROOT / '.cache' / 'fx_rate.json') or {}

    snapshots = load_snapshots()
    plans = load_plans()

    out = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'last_updated': portfolio.get('last_updated', ''),
        'fx': {
            'usdhkd': fx_cache.get('rate'),
            'source': fx_cache.get('source'),
            'fetched_at': fx_cache.get('fetched_at'),
        },
        'totals': {
            'us': {
                'value_usd': us_pf.get('total_current_value', 0),
                'cost_usd': us_pf.get('total_cost', 0),
                'pnl_usd': us_pf.get('total_pnl', 0),
                'pnl_pct': us_pf.get('total_pnl_percent', 0),
                'today_change_usd': us_pf.get('today_total_change', 0),
                'realized_usd': us_pf.get('realized_pnl', 0),
            },
            'hk': {
                'value_hkd': hk_pf.get('total_current_value', 0),
                'cost_hkd': hk_pf.get('total_cost', 0),
                'pnl_hkd': hk_pf.get('total_pnl', 0),
                'pnl_pct': hk_pf.get('total_pnl_percent', 0),
                'today_change_hkd': hk_pf.get('today_total_change', 0),
                'realized_hkd': hk_pf.get('realized_pnl', 0),
            },
        },
        'concentration': {
            'us': us_conc,
            'hk': hk_conc,
        },
        'holdings': {
            'us': us_h,
            'hk': hk_h,
        },
        'snapshots': snapshots,
        'snapshots_total': total_snapshots_count(),
        'snapshots_embedded_cap': MAX_SNAPSHOTS_EMBEDDED,
        'plans_count': total_plans_count(),
        'recent_plans': plans,
        'recent_plans_cap': MAX_PLANS_EMBEDDED,
        'indices': us_pf.get('indices_snapshot', {}),
        'market_context': portfolio.get('market_context', {}),
    }

    # Serialize with no indentation to save bytes; pretty-print only if under budget
    payload_min = json.dumps(out, ensure_ascii=False)
    payload_pretty = json.dumps(out, ensure_ascii=False, indent=2)
    payload = payload_pretty if len(payload_pretty.encode('utf-8')) <= MAX_OUT_BYTES else payload_min
    size_bytes = len(payload.encode('utf-8'))

    if size_bytes > MAX_OUT_BYTES:
        # Last resort: drop recent_plans entirely + keep snapshot summaries only
        print(f'⚠️  payload still {size_bytes} bytes > {MAX_OUT_BYTES} cap — dropping recent_plans', file=sys.stderr)
        out['recent_plans'] = []
        out['recent_plans_dropped'] = True
        payload = json.dumps(out, ensure_ascii=False)
        size_bytes = len(payload.encode('utf-8'))

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write(payload)

    print(f'✓ wrote {OUT_FILE} ({size_bytes:,} bytes)')
    print(f'  US: {len(us_h)} holdings, {len([h for h in us_h if h["is_active"]])} active, value ${us_conc["total"]:.0f}')
    print(f'  HK: {len(hk_h)} holdings, {len([h for h in hk_h if h["is_active"]])} active, value HK${hk_conc["total"]:.0f}')
    print(f'  Snapshots: {len(snapshots)} embedded / {out["snapshots_total"]} on disk')
    print(f'  Plans: {len(plans)} embedded / {out["plans_count"]} on disk')
    print(f'  Snapshots: {len(snapshots)} | Plans: {len(plans)}')
    print(f'  FX USDHKD: {fx_cache.get("rate")} ({fx_cache.get("source")})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
