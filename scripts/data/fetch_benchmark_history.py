#!/usr/bin/env python3
"""
fetch_benchmark_history.py — daily-close history for SPY (US) + HSI/HSTECH (HK).

Used by the Equity Curve widget to overlay a normalized benchmark line so kcn
can see the portfolio's cumulative alpha at a glance.

Sources:
  - SPY:    Polygon aggregates (needs POLYGON_API_KEY)
  - HSI/HSTECH: Tencent web.ifzq.gtimg.cn kline (free, no key)

Output: assets/data/benchmark.json
  {
    "generated_at": "...",
    "window_days": 60,
    "series": {
      "SPY":    [{"date": "2026-04-01", "close": 686.1}, ...],
      "HSI":    [{"date": "2026-04-01", "close": 25294.0}, ...],
      "HSTECH": [...]
    }
  }

Run:
  python3 scripts/data/fetch_benchmark_history.py            # write file
  python3 scripts/data/fetch_benchmark_history.py --dry-run  # print, no write
  python3 scripts/data/fetch_benchmark_history.py --days 90  # custom window
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import requests

WS_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_FILE = WS_ROOT / 'assets' / 'data' / 'benchmark.json'
TIMEOUT = 12
DEFAULT_DAYS = 60

sys.path.insert(0, str(WS_ROOT / 'scripts' / 'data'))
from fetch_us_stocks import load_api_keys  # type: ignore
from safe_io import safe_write_json  # type: ignore


def fetch_polygon_daily(ticker: str, days: int, api_key: str) -> List[Dict]:
    """Polygon aggregates: daily close for the last N calendar days."""
    if not api_key:
        return []
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    url = (
        f'https://api.polygon.io/v2/aggs/ticker/{ticker}'
        f'/range/1/day/{start.isoformat()}/{end.isoformat()}'
        f'?adjusted=true&sort=asc&limit=400&apiKey={api_key}'
    )
    try:
        r = requests.get(url, timeout=TIMEOUT)
        data = r.json()
        results = data.get('results') or []
        out = []
        for x in results:
            ts = x.get('t', 0) / 1000
            close = x.get('c')
            if not close:
                continue
            out.append({
                'date':  datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%d'),
                'close': round(float(close), 4),
            })
        return out
    except Exception as e:
        print(f'  warn: polygon {ticker} fetch failed: {e}', file=sys.stderr)
        return []


def fetch_tencent_hk_daily(sym: str, days: int) -> List[Dict]:
    """Tencent kline: HK index daily close for the last N calendar days.

    sym is the Tencent symbol form, e.g. 'hkHSI' / 'hkHSTECH'.
    Response shape: data[sym].day = [[date, open, close, high, low, volume], ...]
    """
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    url = (
        'https://web.ifzq.gtimg.cn/appstock/app/kline/kline'
        f'?param={sym},day,{start.isoformat()},{end.isoformat()},400'
    )
    try:
        r = requests.get(url, timeout=TIMEOUT)
        d = r.json()
        rows = (d.get('data') or {}).get(sym, {})
        # Tencent sometimes returns "day", sometimes "qfqday" (adjusted); take whichever exists
        series = rows.get('day') or rows.get('qfqday') or []
        out = []
        for row in series:
            if len(row) < 3:
                continue
            try:
                close = float(row[2])
            except (TypeError, ValueError):
                continue
            out.append({'date': row[0], 'close': round(close, 4)})
        return out
    except Exception as e:
        print(f'  warn: tencent {sym} fetch failed: {e}', file=sys.stderr)
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=DEFAULT_DAYS,
                        help='Calendar-day lookback window (default: 60)')
    parser.add_argument('--dry-run', action='store_true', help='Print, do not write file')
    args = parser.parse_args()

    keys = load_api_keys()
    series: Dict[str, List[Dict]] = {}

    # SPY (S&P 500 ETF) — primary US benchmark
    spy = fetch_polygon_daily('SPY', args.days, keys.get('POLYGON_API_KEY', ''))
    if spy:
        series['SPY'] = spy
        print(f'  SPY:    {len(spy)} bars ({spy[0]["date"]} → {spy[-1]["date"]})')
    else:
        print('  SPY: skipped (no data)')

    # HSI (恒生指数) — primary HK benchmark
    hsi = fetch_tencent_hk_daily('hkHSI', args.days)
    if hsi:
        series['HSI'] = hsi
        print(f'  HSI:    {len(hsi)} bars ({hsi[0]["date"]} → {hsi[-1]["date"]})')
    else:
        print('  HSI: skipped (no data)')

    # HSTECH — secondary HK benchmark (tracks tech beta closer to kcn's HK leg)
    hstech = fetch_tencent_hk_daily('hkHSTECH', args.days)
    if hstech:
        series['HSTECH'] = hstech
        print(f'  HSTECH: {len(hstech)} bars ({hstech[0]["date"]} → {hstech[-1]["date"]})')

    out = {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        'window_days': args.days,
        'series': series,
    }

    if args.dry_run:
        print(json.dumps(out, indent=2)[:800])
        return

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    safe_write_json(str(OUT_FILE), out)
    print(f'  ✅ Wrote {OUT_FILE} ({sum(len(s) for s in series.values())} total bars)')


if __name__ == '__main__':
    main()
