#!/usr/bin/env python3
import requests

api_key = 'd6m1kj9r01qu3p05oh6gd6m1kj9r01qu3p05oh70'

tickers = ['MSFT', 'GOOGL', 'META', 'PLTR', 'AI']

print("AI 相关股票实时价格：\n")

for ticker in tickers:
    url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={api_key}'
    response = requests.get(url)
    data = response.json()
    
    if 'c' in data and data['c'] > 0:
        current = data['c']
        change_pct = data.get('dp', 0)
        print(f'{ticker:6s}: ${current:8.2f}  (今日: {change_pct:+.2f}%)')
    else:
        print(f'{ticker:6s}: 数据获取失败')
