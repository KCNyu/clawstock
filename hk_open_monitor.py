#!/usr/bin/env python3
"""
港股开盘监控脚本 - 2026-03-10
监控标的：韩国存储杠杆ETF + AI板块
"""

import urllib.request
import json
import time
from datetime import datetime

# Eastmoney API for HK stocks
def fetch_hk_quotes(symbols):
    """
    symbols: dict of {em_code: (hk_code, name)}
    em_code format: 116.07709 for 7709.HK
    """
    codes_str = ','.join(symbols.keys())
    url = f'https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14,f15,f16,f17,f18&secids={codes_str}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': 'https://quote.eastmoney.com',
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# 监控标的
watchlist = {
    '116.07709': ('07709.HK', '海力士2x', 23.68, 20.0, 28.0),  # (code, name, ref_price, stop_loss, take_profit)
    '116.07747': ('07747.HK', '三星2x', 63.34, 55.0, 70.0),
    '116.00100': ('0100.HK', 'MiniMax', 997.0, None, None),
    '116.03317': ('3317.HK', '迅策', 115.8, None, None),
    '116.09868': ('9868.HK', '小鹏', None, None, None),
}

def main():
    print('=' * 70)
    print(f'港股开盘监控 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)
    
    # Wait until 9:25 (pre-market)
    now = datetime.now()
    if now.hour < 9 or (now.hour == 9 and now.minute < 25):
        wait_secs = (9 - now.hour) * 3600 + (25 - now.minute) * 60 - now.second
        if wait_secs > 0:
            print(f'等待开盘前竞价（9:25），还有 {wait_secs//60} 分钟...')
            time.sleep(wait_secs)
    
    # Fetch opening prices
    try:
        data = fetch_hk_quotes(watchlist)
        print('\n【开盘行情 9:30】')
        
        alerts = []
        for d in data['data']['diff']:
            em_code = f"116.{d['f12']}"
            if em_code not in watchlist:
                continue
            
            hk_code, name, ref, stop, profit = watchlist[em_code]
            price = d['f2']
            chg_pct = d['f3']
            high = d['f15']
            low = d['f16']
            prev = d['f18']
            
            icon = '🟢' if chg_pct >= 0 else '🔴'
            print(f'{icon} {name}({hk_code}): {price} HKD ({chg_pct:+.2f}%) | 高:{high} 低:{low} 昨收:{prev}')
            
            # Alerts
            if stop and price <= stop:
                alerts.append(f'⚠️ {name} 触及止损线 {stop} HKD！现价 {price}')
            elif profit and price >= profit:
                alerts.append(f'🎯 {name} 触及止盈线 {profit} HKD！现价 {price}')
            
            # 加仓提醒
            if hk_code in ['07709.HK', '07747.HK']:
                if chg_pct <= -2:
                    alerts.append(f'💡 {name} 低开 {chg_pct:.1f}%，可考虑加仓')
        
        if alerts:
            print('\n【操作提醒】')
            for a in alerts:
                print(f'  {a}')
        
    except Exception as e:
        print(f'获取数据失败: {e}')
        print('备用方案：手动查看富途/老虎行情')

if __name__ == '__main__':
    main()
