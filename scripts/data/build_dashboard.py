#!/usr/bin/env python3
"""
build_dashboard.py — aggregates portfolio.json + snapshots + plans into a single
JSON the static dashboard (docs/ via Jekyll Pages) consumes.

Output: assets/data/dashboard.json

Run after each portfolio mutation (cron commit) so Pages stays fresh.
"""
import csv
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
        'name': h.get('name') or h.get('stock_name', ''),
        'currency': currency,
        'shares': h.get('shares', 0),
        'cost_basis': round(h.get('cost_basis') or 0, 4),
        'current_price': round(h.get('current_price') or 0, 4),
        'current_value': round(h.get('current_value') or 0, 2),
        'today_change': round(h.get('today_change') or 0, 2),
        'today_change_pct': round(h.get('today_change_pct') or 0, 2),
        'day_high': round(h.get('day_high') or 0, 4),
        'day_low': round(h.get('day_low') or 0, 4),
        'pnl_abs': round(h.get('pnl_abs') or 0, 2),
        'pnl_percent': round(h.get('pnl_percent') or 0, 2),
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


# ── Dashboard v2 NEW field computers ─────────────────────────────────────
# Each function MUST swallow internal exceptions and return its empty/null
# default so a partial failure can't take down the whole dashboard build.

def _pct_change(curr, prev):
    """(curr - prev) / prev * 100, rounded to 2 decimals; None if prev <= 0 or invalid."""
    try:
        if prev is None or curr is None:
            return None
        prev = float(prev)
        if prev == 0:
            return None
        return round((float(curr) - prev) / abs(prev) * 100, 2)
    except Exception:
        return None


def compute_delta(snapshots):
    """Equity rolling-window % change vs today.

    snapshots is the same list build_dashboard already prepares: ascending date,
    so today = snapshots[-1], yesterday = snapshots[-2], etc.
    """
    empty = {
        'us': {'today_pct': None, '7d_pct': None, '30d_pct': None},
        'hk': {'today_pct': None, '7d_pct': None, '30d_pct': None},
    }
    try:
        if not snapshots:
            return empty
        n = len(snapshots)
        today = snapshots[-1]

        def at(offset_back, key):
            idx = n - 1 - offset_back
            if idx < 0:
                return None
            return snapshots[idx].get(key)

        def region(value_key):
            today_v = today.get(value_key)
            return {
                'today_pct': _pct_change(today_v, at(1, value_key)) if n >= 2 else None,
                '7d_pct':    _pct_change(today_v, at(7, value_key)) if n >= 8 else None,
                '30d_pct':   _pct_change(today_v, at(30, value_key)) if n >= 31 else None,
            }
        return {
            'us': region('us_total_value'),
            'hk': region('hk_total_value'),
        }
    except Exception as e:
        print(f'  warn: compute_delta failed: {e}', file=sys.stderr)
        return empty


def compute_today_movers(us_h, hk_h):
    """abs(today_change_pct) >= 3.0 holdings across both regions, top 10 by abs."""
    try:
        items = []
        for h in (us_h or []):
            pct = h.get('today_change_pct')
            if pct is None:
                continue
            if abs(pct) >= 3.0:
                items.append({
                    'ticker': h.get('ticker'),
                    'name': h.get('name', ''),
                    'region': 'us',
                    'today_change_pct': round(pct, 2),
                    'current_price': h.get('current_price'),
                })
        for h in (hk_h or []):
            pct = h.get('today_change_pct')
            if pct is None:
                continue
            if abs(pct) >= 3.0:
                items.append({
                    'ticker': h.get('ticker'),
                    'name': h.get('name', ''),
                    'region': 'hk',
                    'today_change_pct': round(pct, 2),
                    'current_price': h.get('current_price'),
                })
        items.sort(key=lambda x: -abs(x['today_change_pct']))
        return items[:10]
    except Exception as e:
        print(f'  warn: compute_today_movers failed: {e}', file=sys.stderr)
        return []


def _latest_brief_context():
    """Return (path, dict) of newest memory/.tmp/brief-context-*.json by mtime, or (None, None)."""
    try:
        paths = glob.glob(str(WS_ROOT / 'memory' / '.tmp' / 'brief-context-*.json'))
        if not paths:
            return None, None
        latest = max(paths, key=os.path.getmtime)
        return latest, load_json(latest)
    except Exception as e:
        print(f'  warn: _latest_brief_context failed: {e}', file=sys.stderr)
        return None, None


# Tickers we treat as leveraged ETFs even when context doesn't tag them.
_LEVERAGED_TICKERS = {'SOXL', 'TQQQ', 'MSFU', 'PLTU', 'ROBN', 'RKLX', '07226'}


def extract_anomalies(brief_ctx, us_h, hk_h):
    """Risk signals derived from the latest brief-context.

    Recognized types:
      - rsi_overbought          (rsi >= 70 in any embedded indicator block)
      - peer_divergence         (divergence_signal present, severity by gap pp)
      - high_weight_loss        (concentration weight >= 25% AND holding pnl_percent <= -10)
      - leveraged_etf_stop      (leveraged ticker w/ self_pnl_pct <= -15 OR today_change_pct <= -8)
      - no_context              (single entry, fallback when no context file found)
    """
    try:
        if not brief_ctx:
            return [{
                'type': 'no_context',
                'ticker': '',
                'detail': 'no brief-context-*.json found in memory/.tmp/',
                'severity': 'low',
            }]
        out = []
        holdings_by_ticker = {}
        for h in (us_h or []):
            holdings_by_ticker[str(h.get('ticker') or '').upper()] = h
        for h in (hk_h or []):
            holdings_by_ticker[str(h.get('ticker') or '')] = h

        peer_scan = brief_ctx.get('peer_scan') or {}
        if isinstance(peer_scan, dict):
            peer_items = peer_scan.items()
        elif isinstance(peer_scan, list):
            peer_items = [(p.get('ticker'), p) for p in peer_scan]
        else:
            peer_items = []

        # peer_divergence anomalies
        for ticker, v in peer_items:
            if not isinstance(v, dict):
                continue
            sig = v.get('divergence_signal')
            if not sig:
                continue
            self_pct = v.get('self_pct_1d')
            # Try to extract gap pp from signal string like "... (gap +6.4pp)"
            gap_pp = None
            try:
                if isinstance(sig, str) and 'gap' in sig:
                    import re
                    m = re.search(r'gap\s*([+-]?\d+(?:\.\d+)?)\s*pp', sig)
                    if m:
                        gap_pp = abs(float(m.group(1)))
            except Exception:
                gap_pp = None
            severity = 'low'
            if gap_pp is not None:
                if gap_pp >= 8: severity = 'high'
                elif gap_pp >= 4: severity = 'medium'
            out.append({
                'type': 'peer_divergence',
                'ticker': str(ticker),
                'detail': sig if isinstance(sig, str) else f'self {self_pct}% diverges from peers',
                'severity': severity,
            })

        # high_weight_loss anomalies (concentration top tickers w/ deep loss)
        conc = brief_ctx.get('concentration') or {}
        for region in ('us', 'hk'):
            region_conc = conc.get(region) or {}
            weights = region_conc.get('weights') or []
            for w in weights:
                tk = str(w.get('ticker') or '')
                weight_pct = w.get('weight_pct') or 0
                if weight_pct < 25:
                    continue
                h = holdings_by_ticker.get(tk.upper()) or holdings_by_ticker.get(tk)
                if not h:
                    continue
                pnl_pct = h.get('pnl_percent')
                if pnl_pct is not None and pnl_pct <= -10:
                    sev = 'high' if (weight_pct >= 40 or pnl_pct <= -20) else 'medium'
                    out.append({
                        'type': 'high_weight_loss',
                        'ticker': tk,
                        'detail': f'weight {weight_pct:.1f}% + pnl {pnl_pct:.1f}%',
                        'severity': sev,
                    })

        # leveraged_etf_stop anomalies
        for ticker, v in peer_items:
            tk_str = str(ticker or '').upper()
            if tk_str not in _LEVERAGED_TICKERS:
                continue
            if not isinstance(v, dict):
                continue
            self_pnl = v.get('self_pnl_pct')
            self_today = v.get('self_pct_1d')
            triggered = False
            detail_bits = []
            if isinstance(self_pnl, (int, float)) and self_pnl <= -15:
                triggered = True
                detail_bits.append(f'pnl {self_pnl:.1f}%')
            if isinstance(self_today, (int, float)) and self_today <= -8:
                triggered = True
                detail_bits.append(f'today {self_today:.1f}%')
            if triggered:
                sev = 'high' if (isinstance(self_pnl, (int, float)) and self_pnl <= -25) else 'medium'
                out.append({
                    'type': 'leveraged_etf_stop',
                    'ticker': str(ticker),
                    'detail': 'leveraged ETF: ' + ', '.join(detail_bits),
                    'severity': sev,
                })

        # rsi_overbought — only fire if brief_ctx carries an rsi block; current
        # context files don't, but keep the scanner so future preflight runs work.
        def _scan_rsi(node):
            if isinstance(node, dict):
                tk = node.get('ticker') or node.get('symbol')
                rsi = node.get('rsi') or node.get('rsi_14') or node.get('RSI')
                if tk and isinstance(rsi, (int, float)) and rsi >= 70:
                    out.append({
                        'type': 'rsi_overbought',
                        'ticker': str(tk),
                        'detail': f'RSI {rsi:.1f} >= 70',
                        'severity': 'high' if rsi >= 80 else 'medium',
                    })
                for v in node.values():
                    _scan_rsi(v)
            elif isinstance(node, list):
                for it in node:
                    _scan_rsi(it)
        try:
            _scan_rsi(brief_ctx.get('us_fundamentals'))
            _scan_rsi(brief_ctx.get('indicators'))
        except Exception:
            pass

        return out
    except Exception as e:
        print(f'  warn: extract_anomalies failed: {e}', file=sys.stderr)
        return []


def extract_peer_divergence(brief_ctx):
    """List of divergence_signal=true peer scan rows from brief context."""
    try:
        if not brief_ctx:
            return []
        peer_scan = brief_ctx.get('peer_scan') or {}
        if isinstance(peer_scan, dict):
            items = peer_scan.items()
        elif isinstance(peer_scan, list):
            items = [(p.get('ticker'), p) for p in peer_scan]
        else:
            return []
        out = []
        for ticker, v in items:
            if not isinstance(v, dict):
                continue
            if not v.get('divergence_signal'):
                continue
            self_pct = v.get('self_pct_1d')
            best_peer = None
            best_peer_name = None
            peer_pct = None
            best_gap = None
            for p in (v.get('listed_peers') or []):
                pp = p.get('pct_1d')
                if pp is None or self_pct is None:
                    continue
                gap = pp - self_pct  # peer beating self → positive
                if best_gap is None or abs(gap) > abs(best_gap):
                    best_gap = gap
                    best_peer = p.get('ticker')
                    best_peer_name = p.get('name')
                    peer_pct = pp
            try:
                self_pct_v = round(float(self_pct), 2) if self_pct is not None else None
            except Exception:
                self_pct_v = None
            try:
                peer_pct_v = round(float(peer_pct), 2) if peer_pct is not None else None
            except Exception:
                peer_pct_v = None
            try:
                div_pp = round(float(best_gap), 2) if best_gap is not None else None
            except Exception:
                div_pp = None
            out.append({
                'ticker': str(ticker),
                'self_pct_1d': self_pct_v,
                'best_peer': best_peer or '',
                'best_peer_name': best_peer_name or '',
                'peer_pct_1d': peer_pct_v,
                'divergence_pp': div_pp,
            })
        return out
    except Exception as e:
        print(f'  warn: extract_peer_divergence failed: {e}', file=sys.stderr)
        return []


_CALIB_BUCKETS = ['cut', 'trim_on_rebound', 'hold_and_watch', 't_only', 'add_only_on_trigger']
_CALIB_BANDS = [
    ('0-50%',  0.0, 0.5),
    ('50-60%', 0.5, 0.6),
    ('60-70%', 0.6, 0.7),
    ('70-80%', 0.7, 0.8),
    ('80-100%', 0.8, 1.0001),
]


def _read_calibration_rows():
    """Returns list of dict rows from memory/calibration.csv, or []."""
    path = WS_ROOT / 'memory' / 'calibration.csv'
    try:
        if not path.exists():
            return []
        with open(path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f'  warn: _read_calibration_rows failed: {e}', file=sys.stderr)
        return []


def _to_float(s):
    try:
        if s is None or s == '':
            return None
        return float(s)
    except Exception:
        return None


def compute_calibration():
    """Brier + per-band + per-bucket accuracy from calibration.csv (resolved rows only, ≤30d)."""
    bands_empty = [{'band': b[0], 'n': 0, 'actual_win_rate': 0.0} for b in _CALIB_BANDS]
    per_bucket_empty = {b: {'n': 0, 'win_rate': 0.0} for b in _CALIB_BUCKETS}
    empty = {
        'brier_30d': None,
        'samples': 0,
        'bands': bands_empty,
        'per_bucket': per_bucket_empty,
    }
    try:
        rows = _read_calibration_rows()
        if not rows:
            return empty
        # Resolved = outcome in {win, loss, flat} (skip pending/blank).
        # 30d window: keep rows whose plan_date is within 30 days of today.
        today = datetime.utcnow().date()
        resolved = []
        for r in rows:
            outcome = (r.get('outcome') or '').strip().lower()
            if outcome not in ('win', 'loss', 'flat'):
                continue
            try:
                pd = datetime.strptime(r.get('plan_date', '')[:10], '%Y-%m-%d').date()
            except Exception:
                continue
            if (today - pd).days > 30:
                continue
            resolved.append((r, outcome))

        n = len(resolved)
        if n == 0:
            return empty

        # Brier: (confidence - actual)^2, actual ∈ {1 for win, 0 for loss/flat}
        brier_sum = 0.0
        brier_count = 0
        for r, outcome in resolved:
            conf = _to_float(r.get('confidence'))
            if conf is None:
                continue
            actual = 1.0 if outcome == 'win' else 0.0
            brier_sum += (conf - actual) ** 2
            brier_count += 1
        brier_30d = round(brier_sum / brier_count, 4) if (brier_count >= 5) else None

        # Bands
        bands_out = []
        for label, lo, hi in _CALIB_BANDS:
            wins = 0
            total = 0
            for r, outcome in resolved:
                conf = _to_float(r.get('confidence'))
                if conf is None:
                    continue
                if lo <= conf < hi:
                    total += 1
                    if outcome == 'win':
                        wins += 1
            win_rate = round(wins / total, 4) if total else 0.0
            bands_out.append({'band': label, 'n': total, 'actual_win_rate': win_rate})

        # Per-bucket
        per_bucket = {}
        for b in _CALIB_BUCKETS:
            wins = 0
            total = 0
            for r, outcome in resolved:
                if (r.get('bucket') or '').strip() == b:
                    total += 1
                    if outcome == 'win':
                        wins += 1
            win_rate = round(wins / total, 4) if total else 0.0
            per_bucket[b] = {'n': total, 'win_rate': win_rate}

        return {
            'brier_30d': brier_30d,
            'samples': n,
            'bands': bands_out,
            'per_bucket': per_bucket,
        }
    except Exception as e:
        print(f'  warn: compute_calibration failed: {e}', file=sys.stderr)
        return empty


def recent_actions_from_csv(limit=20):
    """Last `limit` rows of calibration.csv, most recent plan_date first."""
    try:
        rows = _read_calibration_rows()
        if not rows:
            return []
        # Sort by plan_date desc (string sort works for YYYY-MM-DD); stable for ties.
        rows.sort(key=lambda r: r.get('plan_date', ''), reverse=True)
        out = []
        for r in rows[:limit]:
            outcome = (r.get('outcome') or '').strip().lower()
            if outcome not in ('win', 'loss', 'flat', 'pending'):
                outcome = 'pending'
            out.append({
                'date': r.get('plan_date', ''),
                'ticker': r.get('ticker', ''),
                'bucket': r.get('bucket', ''),
                'confidence': _to_float(r.get('confidence')),
                'trigger_type': r.get('trigger_type', ''),
                'outcome': outcome,
                'pnl_5d': _to_float(r.get('pnl_5d')),
            })
        return out
    except Exception as e:
        print(f'  warn: recent_actions_from_csv failed: {e}', file=sys.stderr)
        return []


def compute_drawdown(snapshots):
    """30-day rolling drawdown per region.

    `max_pct_30d_*` = most negative ((value_i - peak_so_far) / peak_so_far) across
    the last min(len, 30) snapshots — i.e. worst peak-to-trough retracement in window.
    `current_pct_*` = (today - 30d-ago) / 30d-ago * 100  (uses min(29, len-1) offset).
    """
    empty = {
        'max_pct_30d_hk': None,
        'max_pct_30d_us': None,
        'current_pct_hk': None,
        'current_pct_us': None,
    }
    try:
        if not snapshots:
            return empty
        n = len(snapshots)
        window = snapshots[-30:] if n >= 30 else snapshots[:]

        def max_drawdown_pct(key):
            peak = None
            worst = None
            for s in window:
                v = s.get(key)
                if v is None:
                    continue
                try:
                    v = float(v)
                except Exception:
                    continue
                if peak is None or v > peak:
                    peak = v
                if peak and peak > 0:
                    dd = (v - peak) / peak * 100
                    if worst is None or dd < worst:
                        worst = dd
            return round(worst, 2) if worst is not None else None

        # current vs 30d-ago using min(29, n-1) offset back from today
        offset = min(29, n - 1)
        base_idx = (n - 1) - offset
        today = snapshots[-1]
        base = snapshots[base_idx]

        def current_pct(key):
            t = today.get(key)
            b = base.get(key)
            if t is None or b is None:
                return None
            try:
                t = float(t); b = float(b)
            except Exception:
                return None
            if b == 0:
                return None
            return round((t - b) / abs(b) * 100, 2)

        return {
            'max_pct_30d_hk': max_drawdown_pct('hk_total_value'),
            'max_pct_30d_us': max_drawdown_pct('us_total_value'),
            'current_pct_hk': current_pct('hk_total_value'),
            'current_pct_us': current_pct('us_total_value'),
        }
    except Exception as e:
        print(f'  warn: compute_drawdown failed: {e}', file=sys.stderr)
        return empty


# ───────────────────────────────────────────────────────────────────────────
# v2.1: broker-style analytics
# ───────────────────────────────────────────────────────────────────────────

# Sector / theme map (hardcoded — peer-map.json doesn't carry sector explicitly)
SECTOR_MAP = {
    # US
    'NVDA': 'Semiconductor',  'SOXL': 'Semiconductor ETF',
    'RKLB': 'Aerospace',      'RKLX': 'Aerospace',
    'CRCL': 'Crypto / Stablecoin',
    'OKLO': 'Nuclear / Energy',
    'QQQ':  'Index ETF',      'TQQQ': 'Index ETF',
    'TCOM': 'Travel / Online',
    'HOOD': 'Fintech',        'ROBN': 'Fintech',
    'PLTU': 'AI / Defense',
    'MSFU': 'Tech Mega-cap',
    # HK
    '00100': 'AI / 大模型',
    '02208': '新能源',
    '03032': '恒生科技 ETF', '07226': '恒生科技 ETF',
    '03033': '恒生科技 ETF',
    '07709': 'KR ADR (旧仓)', '07747': 'KR ADR (旧仓)',
}

# 2x/3x leveraged ETF set
LEVERAGED_TICKERS = {'SOXL', 'TQQQ', 'PLTU', 'RKLX', 'ROBN', 'MSFU', '07226'}


def compute_sector_exposure(portfolio):
    """Group active holdings by sector, with % of region book."""
    result = {'us': [], 'hk': []}
    try:
        for region in ('us_stocks', 'hk_stocks'):
            r_key = 'us' if region == 'us_stocks' else 'hk'
            holdings = portfolio['portfolios'][region].get('holdings', [])
            active = [h for h in holdings if h.get('shares', 0) > 0]
            total_value = sum(h.get('current_value', 0) or 0 for h in active)
            if total_value <= 0:
                continue
            by_sector = {}
            for h in active:
                sec = SECTOR_MAP.get(h['ticker'], 'Other')
                bucket = by_sector.setdefault(sec, {'value': 0.0, 'tickers': []})
                bucket['value'] += (h.get('current_value') or 0)
                bucket['tickers'].append(h['ticker'])
            for sec, info in by_sector.items():
                result[r_key].append({
                    'sector': sec,
                    'value': round(info['value'], 2),
                    'pct': round(info['value'] / total_value * 100, 2),
                    'tickers': info['tickers'],
                })
            result[r_key].sort(key=lambda x: x['pct'], reverse=True)
    except Exception as e:
        print(f'  warn: compute_sector_exposure failed: {e}', file=sys.stderr)
    return result


def compute_leveraged_etf_exposure(portfolio, fx_rate):
    """Percent of book in 2x/3x leveraged ETFs, per region + combined (USD-base)."""
    out = {'us_pct': None, 'hk_pct': None, 'combined_pct': None, 'tickers': []}
    try:
        us_active = [h for h in portfolio['portfolios']['us_stocks'].get('holdings', [])
                     if h.get('shares', 0) > 0]
        hk_active = [h for h in portfolio['portfolios']['hk_stocks'].get('holdings', [])
                     if h.get('shares', 0) > 0]

        us_total = sum(h.get('current_value', 0) or 0 for h in us_active)
        hk_total = sum(h.get('current_value', 0) or 0 for h in hk_active)
        us_lev   = sum(h.get('current_value', 0) or 0 for h in us_active if h['ticker'] in LEVERAGED_TICKERS)
        hk_lev   = sum(h.get('current_value', 0) or 0 for h in hk_active if h['ticker'] in LEVERAGED_TICKERS)

        if us_total > 0: out['us_pct'] = round(us_lev / us_total * 100, 2)
        if hk_total > 0: out['hk_pct'] = round(hk_lev / hk_total * 100, 2)

        if fx_rate and fx_rate > 0 and (us_total + hk_total) > 0:
            us_usd_total = us_total
            hk_usd_total = hk_total / fx_rate
            us_usd_lev   = us_lev
            hk_usd_lev   = hk_lev / fx_rate
            combined_total = us_usd_total + hk_usd_total
            combined_lev   = us_usd_lev   + hk_usd_lev
            if combined_total > 0:
                out['combined_pct'] = round(combined_lev / combined_total * 100, 2)

        out['tickers'] = sorted(set(
            h['ticker'] for h in us_active + hk_active if h['ticker'] in LEVERAGED_TICKERS
        ))
    except Exception as e:
        print(f'  warn: compute_leveraged_etf_exposure failed: {e}', file=sys.stderr)
    return out


def compute_all_time_extremes(portfolio, top_n=3):
    """Top-N winners + bottom-N losers across all active holdings (by pnl_percent)."""
    out = {'winners': [], 'losers': []}
    try:
        rows = []
        for region in ('us_stocks', 'hk_stocks'):
            r_key = 'us' if region == 'us_stocks' else 'hk'
            for h in portfolio['portfolios'][region].get('holdings', []):
                if h.get('shares', 0) <= 0:
                    continue
                p = h.get('pnl_percent')
                if p is None:
                    continue
                rows.append({
                    'ticker':      h['ticker'],
                    'name':        h.get('stock_name') or h.get('name', h['ticker']),
                    'region':      r_key,
                    'pnl_percent': round(float(p), 2),
                    'pnl_abs':     h.get('pnl_abs'),
                    'current_value': h.get('current_value'),
                })
        rows.sort(key=lambda x: x['pnl_percent'], reverse=True)
        out['winners'] = rows[:top_n]
        out['losers']  = sorted(rows, key=lambda x: x['pnl_percent'])[:top_n]
    except Exception as e:
        print(f'  warn: compute_all_time_extremes failed: {e}', file=sys.stderr)
    return out


def compute_today_ranges(portfolio, top_n=8):
    """Today's high-low spread as % of current price, sorted desc."""
    rows = []
    try:
        for region in ('us_stocks', 'hk_stocks'):
            r_key = 'us' if region == 'us_stocks' else 'hk'
            for h in portfolio['portfolios'][region].get('holdings', []):
                if h.get('shares', 0) <= 0:
                    continue
                hi = h.get('day_high'); lo = h.get('day_low'); cur = h.get('current_price')
                if hi is None or lo is None or cur is None or cur <= 0:
                    continue
                try:
                    hi = float(hi); lo = float(lo); cur = float(cur)
                except Exception:
                    continue
                if hi == lo:
                    continue
                rows.append({
                    'ticker':    h['ticker'],
                    'region':    r_key,
                    'high':      round(hi, 4),
                    'low':       round(lo, 4),
                    'current':   round(cur, 4),
                    'range_pct': round((hi - lo) / cur * 100, 2),
                })
    except Exception as e:
        print(f'  warn: compute_today_ranges failed: {e}', file=sys.stderr)
    rows.sort(key=lambda x: x['range_pct'], reverse=True)
    return rows[:top_n]


def compute_realized_vs_unrealized(portfolio, fx_rate):
    """Realized + unrealized split per region + combined (USD-base)."""
    out = {
        'us': {'realized': None, 'unrealized': None},
        'hk': {'realized': None, 'unrealized': None},
        'combined_usd': {'realized': None, 'unrealized': None},
    }
    try:
        us = portfolio['portfolios']['us_stocks']
        hk = portfolio['portfolios']['hk_stocks']
        out['us']['realized']   = us.get('total_realized_pnl') or us.get('realized_pnl') or 0.0
        out['us']['unrealized'] = us.get('total_pnl') or 0.0
        out['hk']['realized']   = hk.get('total_realized_pnl') or hk.get('realized_pnl') or 0.0
        out['hk']['unrealized'] = hk.get('total_pnl') or 0.0
        if fx_rate and fx_rate > 0:
            out['combined_usd']['realized'] = round(
                out['us']['realized'] + out['hk']['realized'] / fx_rate, 2)
            out['combined_usd']['unrealized'] = round(
                out['us']['unrealized'] + out['hk']['unrealized'] / fx_rate, 2)
    except Exception as e:
        print(f'  warn: compute_realized_vs_unrealized failed: {e}', file=sys.stderr)
    return out


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

    # ── Dashboard v2 NEW fields (additive; never replace existing keys) ─
    brief_ctx_path, brief_ctx = _latest_brief_context()
    out['delta'] = compute_delta(snapshots)
    out['today_movers'] = compute_today_movers(us_h, hk_h)
    out['anomalies'] = extract_anomalies(brief_ctx, us_h, hk_h)
    out['peer_divergence'] = extract_peer_divergence(brief_ctx)
    out['calibration'] = compute_calibration()
    out['recent_plan_actions'] = recent_actions_from_csv(limit=20)
    out['drawdown'] = compute_drawdown(snapshots)
    # v2.1: broker-style analytics
    fx_rate = (out.get('fx') or {}).get('usdhkd')
    out['sector_exposure'] = compute_sector_exposure(portfolio)
    out['leveraged_etf'] = compute_leveraged_etf_exposure(portfolio, fx_rate)
    # Tier 2: pull pre-computed risk metrics (from portfolio_risk_metrics.py)
    risk_path = WS_ROOT / 'assets' / 'data' / 'risk.json'
    if risk_path.exists():
        try:
            out['risk'] = json.loads(risk_path.read_text())
        except Exception as e:
            print(f'  warn: risk.json parse fail: {e}', file=sys.stderr)
            out['risk'] = None
    else:
        out['risk'] = None

    # Embed GH Action outputs into dashboard.json so the static page can render them
    def _embed(key, fname):
        path = WS_ROOT / 'assets' / 'data' / fname
        if path.exists():
            try:
                out[key] = json.loads(path.read_text())
                return
            except Exception as e:
                print(f'  warn: {fname} parse fail: {e}', file=sys.stderr)
        out[key] = None

    _embed('catalysts', 'catalysts.json')              # fetch_catalysts.py + brief preflight [11/11]
    _embed('us_news_digest', 'us_news_digest.json')    # GH Action news-digest.yml (xiaomi)
    _embed('sentiment', 'sentiment.json')              # GH Action sentiment-scan.yml
    _embed('macro', 'macro.json')                      # GH Action macro-scan.yml
    out['all_time_extremes'] = compute_all_time_extremes(portfolio, top_n=3)
    out['today_ranges'] = compute_today_ranges(portfolio, top_n=8)
    out['realized_vs_unrealized'] = compute_realized_vs_unrealized(portfolio, fx_rate)
    if brief_ctx_path:
        print(f'  brief-context source: {os.path.basename(brief_ctx_path)}')

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

    from safe_io import safe_write_text
    safe_write_text(str(OUT_FILE), payload)

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
