#!/usr/bin/env python3
"""
港股AI板块监控脚本
用法: python3 hk_ai_monitor.py
"""

import urllib.request
import urllib.error
import json
import time
from datetime import datetime

WATCHLIST = {
    '00100': ('MiniMax',       '0100.HK'),
    '02706': ('海致科技集团',   '2706.HK'),
    '00020': ('商汤科技',       '0020.HK'),
    '03317': ('迅策科技',       '3317.HK'),
    '09888': ('百度集团',       '9888.HK'),
}

ALERT_THRESHOLD = 5.0   # 涨跌幅超过±5%触发提醒
MOONSHOT_THRESHOLD = 15.0  # 超过15%为大行情

def fetch_eastmoney(retries=3, delay=3):
    codes = ','.join(f'116.{c}' for c in WATCHLIST.keys())
    url = (
        'https://push2.eastmoney.com/api/qt/ulist.np/get'
        f'?fltt=2&invt=2&fields=f2,f3,f4,f12,f14,f15,f16,f17,f18&secids={codes}'
    )
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': 'https://quote.eastmoney.com',
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt < retries - 1:
                print(f'  [重试 {attempt+1}/{retries}] {e}')
                time.sleep(delay)
            else:
                raise

def fetch_yfinance_fallback():
    """yfinance fallback (slower, may be rate-limited)"""
    try:
        import yfinance as yf
        result = []
        for code, (name, sym) in WATCHLIST.items():
            try:
                t = yf.Ticker(sym)
                hist = t.history(period='2d')
                if len(hist) >= 2:
                    latest = hist.iloc[-1]
                    prev   = hist.iloc[-2]
                    chg    = (latest['Close'] - prev['Close']) / prev['Close'] * 100
                    result.append({
                        'f12': code, 'f14': name,
                        'f2': round(latest['Close'], 2),
                        'f3': round(chg, 2),
                        'f15': round(latest['High'], 2),
                        'f16': round(latest['Low'],  2),
                        'f18': round(prev['Close'],  2),
                    })
                    time.sleep(0.8)
            except Exception:
                pass
        return {'data': {'diff': result}}
    except ImportError:
        return None

def format_row(name, sym, price, chg, high, low, prev):
    if   chg >= MOONSHOT_THRESHOLD:  icon = '🚀'
    elif chg >=  5:                   icon = '🟢'
    elif chg >=  0:                   icon = '📈'
    elif chg >= -5:                   icon = '📉'
    else:                              icon = '🔴'
    return (
        f'{icon} {name:<12} {sym}  '
        f'{price:>8.2f} HKD  {chg:>+7.2f}%  '
        f'H:{high:<8.2f} L:{low:<8.2f}  昨收:{prev:.2f}'
    )

def main():
    print(f'\n{"="*74}')
    print(f'  港股AI板块实时行情  |  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{"="*74}')

    # Try Eastmoney first, fallback to yfinance
    data = None
    try:
        data = fetch_eastmoney()
        source = 'Eastmoney'
    except Exception as e:
        print(f'  ⚠️  Eastmoney 失败 ({e})，尝试 yfinance...')
        data = fetch_yfinance_fallback()
        source = 'yfinance'

    if not data:
        print('  ❌ 所有数据源失败，请稍后重试')
        return

    alerts = []
    for d in data['data']['diff']:
        code = d['f12']
        if code not in WATCHLIST:
            continue
        name, sym = WATCHLIST[code]
        chg = d['f3']
        row = format_row(name, sym, d['f2'], chg, d['f15'], d['f16'], d['f18'])
        print(row)
        if abs(chg) >= ALERT_THRESHOLD:
            severity = '🔥 大行情' if abs(chg) >= MOONSHOT_THRESHOLD else '⚡ 异动'
            alerts.append(f'  {severity}  {name}({sym})  {chg:+.2f}%')

    print(f'{"="*74}')
    print(f'  数据源: {source}')
    if alerts:
        print('\n  🔔 今日提醒:')
        for a in alerts:
            print(a)
    else:
        print('  ✅ 今日无异动 (±5%以内)')
    print()

if __name__ == '__main__':
    main()
