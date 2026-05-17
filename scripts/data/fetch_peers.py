#!/usr/bin/env python3
"""
fetch_peers.py — fetch current price + 5-day P&L for peer tickers.

Used by brief_preflight to enrich context.json with peer_scan data.

Input: stdin JSON: [{"ticker": "00020", "region": "hk"}, {"ticker": "NVDA", "region": "us"}, ...]
Output: stdout JSON: {ticker: {price, pct_1d, pct_5d, source, error?}}

HK uses Tencent gtimg (current) + stooq (history). US uses Yahoo v8 + Nasdaq.
All public, no API key. Failure on a single ticker doesn't fail the batch.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import requests

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
HEADERS = {'User-Agent': UA}
TIMEOUT = 8


def _pct(c: float, base: float) -> float:
    return round((c - base) / base * 100, 2) if base else 0.0


def fetch_hk_one(ticker: str) -> Dict:
    """Returns {price, pct_1d, pct_5d, source, error?}."""
    out = {'ticker': ticker, 'region': 'hk'}
    # Tencent gtimg for current + prev close
    try:
        r = requests.get(f'https://qt.gtimg.cn/q=r_hk{ticker}', headers=HEADERS, timeout=TIMEOUT)
        r.encoding = 'gbk'
        line = r.text.strip()
        s, e = line.find('"') + 1, line.rfind('"')
        if s > 0 and e > s:
            parts = line[s:e].split('~')
            if len(parts) >= 6:
                price = float(parts[3])
                pc = float(parts[4]) if parts[4] else price
                out.update({
                    'price': price,
                    'prev_close': pc,
                    'pct_1d': _pct(price, pc),
                    'name': parts[1],
                    'source': 'tencent',
                })
    except Exception as e:
        out['error_tencent'] = str(e)[:80]

    # stooq for 5d historical close
    try:
        sym = f'{int(ticker):04d}.hk'
        r = requests.get(f'https://stooq.com/q/d/l/?s={sym}&i=d', headers=HEADERS, timeout=TIMEOUT)
        lines = r.text.strip().split('\n')
        if len(lines) >= 6:
            closes = [float(line.split(',')[4]) for line in lines[-6:]]  # 6 days incl today
            today = closes[-1]
            five_ago = closes[0]
            out['pct_5d'] = _pct(today, five_ago)
            if 'price' not in out:
                out['price'] = today
                out['source'] = 'stooq'
    except Exception as e:
        out['error_stooq'] = str(e)[:80]

    return out


def fetch_us_one(ticker: str) -> Dict:
    """Returns {price, pct_1d, pct_5d, source}."""
    out = {'ticker': ticker, 'region': 'us'}
    # Yahoo v8 chart API — 8 days range for 5d calc
    try:
        end = int(datetime.now().timestamp())
        start = end - 14 * 86400  # 14 days buffer for weekends
        r = requests.get(
            f'https://query2.finance.yahoo.com/v8/finance/chart/{ticker}',
            params={'period1': start, 'period2': end, 'interval': '1d'},
            headers=HEADERS, timeout=TIMEOUT,
        )
        d = r.json()
        meta = d.get('chart', {}).get('result', [{}])[0].get('meta', {})
        result = d.get('chart', {}).get('result', [{}])[0]
        ts = result.get('timestamp', [])
        closes = result.get('indicators', {}).get('quote', [{}])[0].get('close', [])
        # Filter out None values
        valid = [(t, c) for t, c in zip(ts, closes) if c is not None]
        if valid:
            today_close = valid[-1][1]
            prev_close = valid[-2][1] if len(valid) >= 2 else today_close
            five_ago = valid[-6][1] if len(valid) >= 6 else today_close
            current = meta.get('regularMarketPrice', today_close)
            out.update({
                'price': round(current, 4),
                'prev_close': round(prev_close, 4),
                'pct_1d': _pct(current, prev_close),
                'pct_5d': _pct(current, five_ago),
                'source': 'yahoo',
            })
    except Exception as e:
        out['error_yahoo'] = str(e)[:80]
        # Fallback: Nasdaq API
        try:
            for assetclass in ('stocks', 'etf'):
                rr = requests.get(
                    f'https://api.nasdaq.com/api/quote/{ticker}/info?assetclass={assetclass}',
                    headers={**HEADERS, 'Origin': 'https://www.nasdaq.com'}, timeout=TIMEOUT,
                )
                if rr.status_code == 200:
                    data = (rr.json().get('data') or {})
                    pd = data.get('primaryData') or {}
                    summary = data.get('summaryData') or {}
                    price_s = (pd.get('lastSalePrice') or '').replace('$', '').replace(',', '')
                    if price_s:
                        price = float(price_s)
                        pc_s = ((summary.get('PreviousClose') or {}).get('value') or '').replace('$','').replace(',','')
                        pc = float(pc_s) if pc_s else price
                        out.update({
                            'price': price, 'prev_close': pc,
                            'pct_1d': _pct(price, pc),
                            'source': f'nasdaq-{assetclass}',
                        })
                        break
        except Exception as e2:
            out['error_nasdaq'] = str(e2)[:80]
    return out


def main():
    try:
        peers = json.loads(sys.stdin.read())
    except Exception as e:
        print(json.dumps({'error': f'bad input: {e}'}))
        sys.exit(1)

    results = {}
    for p in peers:
        t = p['ticker']
        r = p.get('region', 'us')
        if r == 'hk':
            results[t] = fetch_hk_one(t)
        else:
            results[t] = fetch_us_one(t)

    print(json.dumps({
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'peers': results,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.exit(main() or 0)
