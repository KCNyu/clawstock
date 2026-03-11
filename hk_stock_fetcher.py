#!/usr/bin/env python3
"""
Hong Kong Stock Data Fetcher using Tencent Finance API
Free, no auth required, works great!
"""

import json
import requests
from datetime import datetime

def get_hk_stock_tencent(ticker_code):
    """
    Get HK stock data from Tencent Finance API
    ticker_code: e.g., "02208"
    """
    # Tencent API format: hk + 5-digit code
    code = f"hk{ticker_code}"
    url = f"https://qt.gtimg.cn/q={code}"
    
    try:
        response = requests.get(url, timeout=10)
        response.encoding = 'gbk'
        
        # Parse response
        # Format: v_hk02208="100~金风科技~02208~14.460~14.150~14.290~..."
        content = response.text
        
        if 'v_hk' not in content:
            return None
        
        # Extract data between quotes
        start = content.find('"') + 1
        end = content.rfind('"')
        data_str = content[start:end]
        
        parts = data_str.split('~')
        
        if len(parts) < 40:
            return None
        
        # Parse fields (based on Tencent API format)
        name = parts[1]
        current_price = float(parts[3])
        prev_close = float(parts[4])
        open_price = float(parts[5])
        volume = float(parts[6])
        high = float(parts[33])
        low = float(parts[34])
        
        change = current_price - prev_close
        change_percent = (change / prev_close * 100) if prev_close > 0 else 0
        
        data = {
            'ticker': ticker_code,
            'name': name,
            'current_price': current_price,
            'open': open_price,
            'high': high,
            'low': low,
            'previous_close': prev_close,
            'change': change,
            'change_percent': change_percent,
            'volume': int(volume),
        }
        
        return data
    except Exception as e:
        print(f"Error fetching {ticker_code}: {e}")
        import traceback
        traceback.print_exc()
        return None

def update_hk_portfolio():
    """Update all HK stocks in portfolio"""
    with open('portfolio.json', 'r') as f:
        portfolio = json.load(f)
    
    hk_stocks = portfolio['portfolios']['hk_stocks']['holdings']
    
    print("Fetching Hong Kong stock data from Tencent Finance...")
    print("="*80)
    
    success_count = 0
    
    for holding in hk_stocks:
        ticker = holding['ticker']
        print(f"\nFetching {ticker}...")
        
        data = get_hk_stock_tencent(ticker)
        
        if data:
            # Update holding
            old_price = holding['current_price']
            new_price = data['current_price']
            
            holding['current_price'] = new_price
            holding['current_value'] = new_price * holding['shares']
            holding['today_change'] = data['change'] * holding['shares']
            
            print(f"  ✅ {data['name']}")
            print(f"  Price: HKD {old_price:.3f} -> HKD {new_price:.3f}")
            print(f"  Change: {data['change_percent']:+.2f}%")
            print(f"  Day Range: HKD {data['low']:.3f} - HKD {data['high']:.3f}")
            print(f"  Volume: {data['volume']:,}")
            
            success_count += 1
        else:
            print(f"  ❌ Failed to fetch data")
    
    # Update totals
    hk_portfolio = portfolio['portfolios']['hk_stocks']
    hk_portfolio['total_current_value'] = sum(h['current_value'] for h in hk_stocks)
    hk_portfolio['today_total_change'] = sum(h.get('today_change', 0) for h in hk_stocks)
    
    # Save
    portfolio['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open('portfolio.json', 'w') as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*80)
    print(f"✅ HK Portfolio Updated! ({success_count}/{len(hk_stocks)} stocks)")
    print(f"Total Value: HKD {hk_portfolio['total_current_value']:,.2f}")
    print(f"Today's Change: HKD {hk_portfolio['today_total_change']:+,.2f}")
    
    return portfolio

if __name__ == '__main__':
    update_hk_portfolio()
