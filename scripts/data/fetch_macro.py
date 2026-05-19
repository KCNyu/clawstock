#!/usr/bin/env python3
"""
fetch_macro.py — daily macro sentiment for the brief.

Sources (all free, no API key):
  • VIX                — Yahoo Finance v8 chart API (^VIX)
  • US Treasury 10Y    — Yahoo v8 (^TNX, divide by 10 for %)
  • USD index (DXY)    — Yahoo v8 (DX-Y.NYB)
  • CNN Fear & Greed   — production-api.cnn.com (public, no key)
  • Federal Reserve press releases — federalreserve.gov RSS (last 7 days)

Writes: assets/data/macro.json
"""
import json
import os
import sys
from datetime import datetime, timezone

import requests

WS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_FILE = os.path.join(WS_ROOT, 'assets', 'data', 'macro.json')

UA = 'clawock-macro-scan/1.0 (github.com/KCNyu/clawock)'
HEADERS = {'User-Agent': UA}
TIMEOUT = 10


def yahoo_quote(symbol):
    """Latest + previous close for any Yahoo ticker."""
    try:
        r = requests.get(
            f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
            headers=HEADERS, timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None
        j = r.json()
        meta = j.get('chart', {}).get('result', [{}])[0].get('meta', {})
        price = meta.get('regularMarketPrice')
        prev  = meta.get('chartPreviousClose') or meta.get('previousClose')
        if not price:
            return None
        chg = ((price - prev) / prev * 100) if prev else 0
        return {
            'symbol': symbol,
            'price':  round(price, 4),
            'prev':   round(prev or price, 4),
            'change_pct': round(chg, 2),
            'as_of': meta.get('regularMarketTime'),
        }
    except Exception as e:
        print(f'  ⚠️ yahoo {symbol}: {e}', file=sys.stderr)
        return None


def cnn_fear_greed():
    """CNN Fear & Greed index — public production API."""
    try:
        r = requests.get(
            'https://production.dataviz.cnn.io/index/fearandgreed/graphdata',
            headers={**HEADERS, 'Accept': 'application/json'},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None
        j = r.json()
        cur = (j.get('fear_and_greed') or {})
        score = cur.get('score')
        if score is None:
            return None
        rating = cur.get('rating', '')
        prev_close = cur.get('previous_close')
        prev_1w    = cur.get('previous_1_week')
        return {
            'score':       round(score, 1),
            'rating':      rating,         # 'extreme fear' | 'fear' | 'neutral' | 'greed' | 'extreme greed'
            'prev_close':  round(prev_close, 1) if prev_close else None,
            'prev_1_week': round(prev_1w, 1) if prev_1w else None,
            'as_of':       cur.get('timestamp'),
        }
    except Exception as e:
        print(f'  ⚠️ CNN F&G: {e}', file=sys.stderr)
        return None


def fed_press_releases(days=7):
    """Federal Reserve press releases RSS — keep last `days` items."""
    import xml.etree.ElementTree as ET
    from datetime import timedelta
    try:
        r = requests.get('https://www.federalreserve.gov/feeds/press_all.xml',
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        root = ET.fromstring(r.content)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        items = []
        for it in root.findall('.//item'):
            title = it.findtext('title') or ''
            date_str = it.findtext('pubDate') or ''
            link = it.findtext('link') or ''
            try:
                from email.utils import parsedate_to_datetime
                pub = parsedate_to_datetime(date_str)
                if pub < cutoff:
                    continue
                items.append({'date': pub.strftime('%Y-%m-%d'),
                              'title': title.strip()[:200],
                              'url': link})
            except Exception:
                continue
        items.sort(key=lambda x: x['date'], reverse=True)
        return items[:15]
    except Exception as e:
        print(f'  ⚠️ Fed RSS: {e}', file=sys.stderr)
        return None


def main():
    out = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'vix':            yahoo_quote('^VIX'),
        'treasury_10y':   yahoo_quote('^TNX'),     # actually 10Y * 10 in price units
        'dxy':            yahoo_quote('DX-Y.NYB'),
        'fear_greed':     cnn_fear_greed(),
        'hsi':            yahoo_quote('^HSI'),
        'hstech':         yahoo_quote('^HSTECH'),
        'spx':            yahoo_quote('^GSPC'),
        'nasdaq':         yahoo_quote('^IXIC'),
        'fed_press':      fed_press_releases(days=7),
    }

    # 10Y treasury yield = price / 10
    if out['treasury_10y']:
        out['treasury_10y']['yield_pct'] = round(out['treasury_10y']['price'] / 10, 3)

    # Atomic write
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from safe_io import safe_write_json
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    safe_write_json(OUT_FILE, out)

    # Print summary
    print('=== macro snapshot ===')
    for k, v in out.items():
        if k == 'generated_at': continue
        if v is None:
            print(f'  {k:14s}  ⚠️ failed')
        elif k == 'fed_press':
            print(f'  {k:14s}  {len(v)} press releases (last 7d)')
            for r in v[:3]:
                print(f'    [{r["date"]}] {r["title"][:80]}')
        elif k == 'fear_greed':
            print(f'  {k:14s}  {v["score"]} ({v["rating"]})  · prev close {v.get("prev_close")}, 1w {v.get("prev_1_week")}')
        elif k == 'treasury_10y':
            print(f'  {k:14s}  {v["yield_pct"]}%  ({v["change_pct"]:+.2f}%)')
        else:
            print(f'  {k:14s}  {v["price"]:>10}  ({v["change_pct"]:+.2f}%)')
    print(f'\n✓ wrote {OUT_FILE} ({os.path.getsize(OUT_FILE):,} bytes)')


if __name__ == '__main__':
    sys.exit(main() or 0)
