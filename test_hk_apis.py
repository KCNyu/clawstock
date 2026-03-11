#!/usr/bin/env python3
"""
Test different HK stock data sources
"""

import requests

def test_tencent_api(ticker):
    """Test Tencent Finance API"""
    # Format: hk + 5-digit code
    code = f"hk{ticker}"
    url = f"https://qt.gtimg.cn/q={code}"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Tencent API Response for {ticker}:")
        print(response.text[:500])
        print()
        return response.text
    except Exception as e:
        print(f"Tencent API Error: {e}")
        return None

def test_eastmoney_api(ticker):
    """Test Eastmoney API"""
    # Remove leading zeros
    code = str(int(ticker))
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid=116.{code}&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f57,f58,f60,f107,f152,f162,f167,f168,f169,f170,f171"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Eastmoney API Response for {ticker}:")
        print(response.text[:500])
        print()
        return response.text
    except Exception as e:
        print(f"Eastmoney API Error: {e}")
        return None

def test_futu_api(ticker):
    """Test Futu/Yahoo-like API"""
    code = f"{int(ticker)}.HK"
    url = f"https://stock.xueqiu.com/v5/stock/quote.json?symbol={code}&extend=detail"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Xueqiu API Response for {ticker}:")
        print(response.text[:500])
        print()
        return response.text
    except Exception as e:
        print(f"Xueqiu API Error: {e}")
        return None

# Test with 02208
print("="*80)
print("Testing different APIs for HK stock 02208")
print("="*80)
print()

test_tencent_api("02208")
test_eastmoney_api("02208")
test_futu_api("02208")
