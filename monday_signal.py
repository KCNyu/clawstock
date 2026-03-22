#!/usr/bin/env python3
"""周一开盘信号脚本"""
import requests
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else 'us'

def get_hk_prices():
    stocks = {
        '07226': ('南方2x恒科', 5200, 4.497),
        '9988': ('阿里巴巴', 0, 0),
        '700': ('腾讯', 0, 0),
    }
    results = {}
    for code, (name, shares, cost) in stocks.items():
        sym = f'{code}.hk'
        try:
            r = requests.get(f'https://stooq.com/q/d/l/?s={sym}&i=d', timeout=8)
            last = r.text.strip().split('\n')[-1]
            parts = last.split(',')
            price = float(parts[4])
            results[code] = {'name': name, 'price': price, 'shares': shares, 'cost': cost}
        except:
            results[code] = {'name': name, 'price': None}
    return results

def get_us_prices():
    api_key = 'd6m1kj9r01qu3p05oh6gd6m1kj9r01qu3p05oh70'
    tickers = {'TQQQ': 43.08, 'NVDA': 172.70, 'QQQ': 582.06}
    results = {}
    for sym, prev in tickers.items():
        try:
            r = requests.get(f'https://finnhub.io/api/v1/quote?symbol={sym}&token={api_key}', timeout=10)
            d = r.json()
            results[sym] = {'price': d['c'], 'prev': d['pc'], 'change': d['dp']}
        except:
            results[sym] = {'price': None}
    return results

def get_news_signal():
    try:
        r = requests.get(
            'https://news.google.com/rss/search?q=Iran+war+ceasefire+Trump+stock+market&hl=en-US&gl=US&ceid=US:en',
            timeout=10
        )
        headlines = []
        import re
        titles = re.findall(r'<title>(.*?)</title>', r.text)[2:6]
        return titles
    except:
        return []

if mode == 'hk':
    prices = get_hk_prices()
    news = get_news_signal()
    
    msg = "🇭🇰 港股开盘信号\n\n"
    
    ali = prices.get('9988', {})
    tencent = prices.get('700', {})
    hk2x = prices.get('07226', {})
    
    if ali.get('price'):
        msg += f"阿里 9988: HKD {ali['price']}\n"
    if tencent.get('price'):
        msg += f"腾讯 700: HKD {tencent['price']}\n"
    if hk2x.get('price'):
        p = hk2x['price']
        pnl = (p - 4.497) / 4.497 * 100
        msg += f"07226 2x恒科: HKD {p} ({pnl:+.1f}%)\n"
    
    msg += "\n📰 最新消息:\n"
    for h in news[:3]:
        msg += f"• {h}\n"
    
    msg += "\n📌 今日关注: 恒生科技方向 + 战争消息变化"
    print(msg)

elif mode == 'us':
    prices = get_us_prices()
    news = get_news_signal()
    
    msg = "🇺🇸 美股开盘信号\n\n"
    
    tqqq = prices.get('TQQQ', {})
    nvda = prices.get('NVDA', {})
    qqq = prices.get('QQQ', {})
    
    if tqqq.get('price'):
        c = tqqq['change'] or 0
        emoji = '🟢' if c > 0 else '🔴'
        msg += f"TQQQ: ${tqqq['price']:.2f} {emoji}{c:+.1f}%\n"
        # 操作信号
        p = tqqq['price']
        if p >= 45:
            msg += "  ✅ 信号: TQQQ站上$45，反弹确认，可考虑建仓\n"
        elif p <= 40:
            msg += "  ⚠️ 信号: TQQQ破$40，继续观望等$38\n"
        else:
            msg += "  ⏳ 信号: 中性区间，等方向确认\n"
    
    if nvda.get('price'):
        c = nvda['change'] or 0
        emoji = '🟢' if c > 0 else '🔴'
        msg += f"NVDA: ${nvda['price']:.2f} {emoji}{c:+.1f}%\n"
        if nvda['price'] < 165:
            msg += "  ⚠️ NVDA破$165关键支撑，大盘情绪恶化\n"
    
    if qqq.get('price'):
        c = qqq['change'] or 0
        emoji = '🟢' if c > 0 else '🔴'
        msg += f"QQQ: ${qqq['price']:.2f} {emoji}{c:+.1f}%\n"
    
    msg += "\n📰 最新消息:\n"
    for h in news[:3]:
        msg += f"• {h}\n"
    
    msg += "\n📌 止损线: TQQQ $40 | SOXL $42 | 阿里 $108"
    print(msg)
