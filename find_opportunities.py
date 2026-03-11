#!/usr/bin/env python3
"""
New Stock Opportunities Finder
Search for stocks with strong momentum and positive sentiment
"""

import requests
import json
from datetime import datetime, timedelta

class OpportunityFinder:
    def __init__(self):
        self.load_api_keys()
    
    def load_api_keys(self):
        keys = {}
        with open('.api_keys', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        keys[key] = value
        self.finnhub_key = keys.get('FINNHUB_API_KEY')
    
    def get_trending_stocks(self):
        """Get trending stocks from Finnhub"""
        # Popular tech and AI stocks to analyze
        candidates = [
            'MSFT',   # Microsoft
            'GOOGL',  # Google
            'AMZN',   # Amazon
            'META',   # Meta
            'TSLA',   # Tesla
            'AMD',    # AMD
            'PLTR',   # Palantir
            'COIN',   # Coinbase
            'SHOP',   # Shopify
            'SQ',     # Block (Square)
        ]
        
        opportunities = []
        
        print("搜索新的投资机会...")
        print("="*80)
        
        for ticker in candidates:
            print(f"\n分析 {ticker}...")
            
            # Get quote
            quote = self.get_quote(ticker)
            if not quote:
                continue
            
            # Get news sentiment
            news = self.get_news(ticker, days=3)
            
            # Simple scoring
            score = 0
            reasons = []
            
            # Price momentum
            current = quote.get('c', 0)
            prev_close = quote.get('pc', 0)
            if current > prev_close:
                change_pct = ((current - prev_close) / prev_close) * 100
                score += 2
                reasons.append(f"今日上涨 {change_pct:.2f}%")
            
            # News sentiment
            if news:
                positive_count = sum(1 for n in news if any(word in n.get('headline', '').lower() 
                    for word in ['surge', 'gain', 'profit', 'growth', 'bullish', 'upgrade', 'beat', 'strong']))
                if positive_count > 3:
                    score += 3
                    reasons.append(f"正面新闻 {positive_count} 条")
                
                if len(news) > 10:
                    score += 1
                    reasons.append(f"高关注度 ({len(news)} 条新闻)")
            
            if score >= 3:
                opportunities.append({
                    'ticker': ticker,
                    'current_price': current,
                    'change_pct': ((current - prev_close) / prev_close) * 100,
                    'score': score,
                    'reasons': reasons,
                    'news_count': len(news) if news else 0
                })
                
                print(f"  ✅ 发现机会！得分: {score}")
                for reason in reasons:
                    print(f"     • {reason}")
        
        return opportunities
    
    def get_quote(self, ticker):
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={self.finnhub_key}"
        try:
            response = requests.get(url, timeout=10)
            return response.json()
        except:
            return None
    
    def get_news(self, ticker, days=3):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={start_date.strftime('%Y-%m-%d')}&to={end_date.strftime('%Y-%m-%d')}&token={self.finnhub_key}"
        try:
            response = requests.get(url, timeout=10)
            return response.json()
        except:
            return None
    
    def generate_report(self):
        opportunities = self.get_trending_stocks()
        
        print("\n" + "="*80)
        print("新股投资机会报告")
        print("="*80)
        
        if not opportunities:
            print("暂未发现明显机会")
            return
        
        # Sort by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"\n发现 {len(opportunities)} 个潜在机会：\n")
        
        for i, opp in enumerate(opportunities, 1):
            print(f"{i}. {opp['ticker']}")
            print(f"   当前价: ${opp['current_price']:.2f}")
            print(f"   今日涨跌: {opp['change_pct']:+.2f}%")
            print(f"   得分: {opp['score']}/10")
            print(f"   理由:")
            for reason in opp['reasons']:
                print(f"     • {reason}")
            print()

if __name__ == '__main__':
    finder = OpportunityFinder()
    finder.generate_report()
