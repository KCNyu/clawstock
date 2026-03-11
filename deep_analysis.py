#!/usr/bin/env python3
"""
Deep Stock Analysis for Monday Trading Decision
Combines technical indicators, sentiment analysis, and news
"""

import json
import requests
from datetime import datetime, timedelta

class DeepStockAnalyzer:
    def __init__(self):
        self.load_api_keys()
        self.load_portfolio()
    
    def load_api_keys(self):
        keys = {}
        with open('.api_keys', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        keys[key] = value
        
        self.finnhub_key = keys.get('FINNHUB_API_KEY')
        self.alpha_vantage_key = keys.get('ALPHA_VANTAGE_API_KEY')
    
    def load_portfolio(self):
        with open('portfolio.json', 'r') as f:
            self.portfolio = json.load(f)
    
    def get_technical_indicators(self, ticker):
        """Get RSI, MACD, and other technical indicators from Alpha Vantage"""
        indicators = {}
        
        # RSI
        try:
            url = f"https://www.alphavantage.co/query?function=RSI&symbol={ticker}&interval=daily&time_period=14&series_type=close&apikey={self.alpha_vantage_key}"
            response = requests.get(url, timeout=10)
            data = response.json()
            if 'Technical Analysis: RSI' in data:
                latest_date = list(data['Technical Analysis: RSI'].keys())[0]
                indicators['rsi'] = float(data['Technical Analysis: RSI'][latest_date]['RSI'])
        except Exception as e:
            print(f"Error fetching RSI for {ticker}: {e}")
        
        # MACD
        try:
            url = f"https://www.alphavantage.co/query?function=MACD&symbol={ticker}&interval=daily&series_type=close&apikey={self.alpha_vantage_key}"
            response = requests.get(url, timeout=10)
            data = response.json()
            if 'Technical Analysis: MACD' in data:
                latest_date = list(data['Technical Analysis: MACD'].keys())[0]
                macd_data = data['Technical Analysis: MACD'][latest_date]
                indicators['macd'] = {
                    'macd': float(macd_data['MACD']),
                    'signal': float(macd_data['MACD_Signal']),
                    'hist': float(macd_data['MACD_Hist'])
                }
        except Exception as e:
            print(f"Error fetching MACD for {ticker}: {e}")
        
        return indicators
    
    def get_quote(self, ticker):
        """Get current quote from Finnhub"""
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={self.finnhub_key}"
        try:
            response = requests.get(url, timeout=10)
            return response.json()
        except Exception as e:
            print(f"Error fetching quote for {ticker}: {e}")
            return None
    
    def get_news_sentiment(self, ticker, days=7):
        """Get news and analyze sentiment"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={start_date.strftime('%Y-%m-%d')}&to={end_date.strftime('%Y-%m-%d')}&token={self.finnhub_key}"
        try:
            response = requests.get(url, timeout=10)
            news = response.json()
            
            # Simple sentiment analysis based on keywords
            positive_keywords = ['surge', 'gain', 'profit', 'growth', 'bullish', 'upgrade', 'beat', 'strong', 'rally', 'breakthrough']
            negative_keywords = ['fall', 'loss', 'decline', 'bearish', 'downgrade', 'miss', 'weak', 'crash', 'concern', 'risk']
            
            sentiment_score = 0
            for item in news[:20]:  # Analyze last 20 news items
                headline = item.get('headline', '').lower()
                summary = item.get('summary', '').lower()
                text = headline + ' ' + summary
                
                for word in positive_keywords:
                    if word in text:
                        sentiment_score += 1
                
                for word in negative_keywords:
                    if word in text:
                        sentiment_score -= 1
            
            return {
                'news_count': len(news),
                'sentiment_score': sentiment_score,
                'sentiment': 'Positive' if sentiment_score > 3 else 'Negative' if sentiment_score < -3 else 'Neutral',
                'recent_headlines': [n['headline'] for n in news[:5]]
            }
        except Exception as e:
            print(f"Error fetching news for {ticker}: {e}")
            return None
    
    def analyze_stock(self, ticker):
        """Comprehensive analysis of a stock"""
        print(f"\n{'='*80}")
        print(f"Analyzing {ticker}...")
        print(f"{'='*80}")
        
        analysis = {
            'ticker': ticker,
            'timestamp': datetime.now().isoformat()
        }
        
        # Get current price
        quote = self.get_quote(ticker)
        if quote:
            analysis['quote'] = quote
            print(f"Current: ${quote['c']:.2f} | High: ${quote['h']:.2f} | Low: ${quote['l']:.2f}")
        
        # Get technical indicators
        print("Fetching technical indicators...")
        indicators = self.get_technical_indicators(ticker)
        analysis['technical'] = indicators
        
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            print(f"RSI: {rsi:.2f}", end=" ")
            if rsi > 70:
                print("(Overbought ⚠️)")
            elif rsi < 30:
                print("(Oversold 🎯)")
            else:
                print("(Neutral)")
        
        if 'macd' in indicators:
            macd = indicators['macd']
            print(f"MACD: {macd['macd']:.4f} | Signal: {macd['signal']:.4f} | Hist: {macd['hist']:.4f}")
            if macd['hist'] > 0:
                print("MACD: Bullish crossover 📈")
            else:
                print("MACD: Bearish crossover 📉")
        
        # Get news sentiment
        print("Analyzing news sentiment...")
        sentiment = self.get_news_sentiment(ticker)
        analysis['sentiment'] = sentiment
        
        if sentiment:
            print(f"News Count: {sentiment['news_count']} | Sentiment: {sentiment['sentiment']} (Score: {sentiment['sentiment_score']})")
            print("\nRecent Headlines:")
            for i, headline in enumerate(sentiment['recent_headlines'][:3], 1):
                print(f"  {i}. {headline[:80]}...")
        
        return analysis
    
    def generate_recommendations(self):
        """Generate trading recommendations for Monday"""
        print("\n" + "="*80)
        print("MONDAY TRADING RECOMMENDATIONS")
        print("="*80)
        
        us_stocks = self.portfolio['portfolios']['us_stocks']['holdings']
        
        recommendations = []
        
        for holding in us_stocks:
            ticker = holding['ticker']
            analysis = self.analyze_stock(ticker)
            
            # Generate recommendation based on technical + sentiment
            recommendation = {
                'ticker': ticker,
                'current_position': holding,
                'action': 'HOLD',
                'confidence': 'Medium',
                'reasons': []
            }
            
            # Technical analysis
            if 'technical' in analysis and 'rsi' in analysis['technical']:
                rsi = analysis['technical']['rsi']
                if rsi > 70:
                    recommendation['reasons'].append(f"RSI超买 ({rsi:.1f}) - 可能回调")
                    recommendation['action'] = 'SELL' if holding['pnl_percent'] > 5 else 'HOLD'
                elif rsi < 30:
                    recommendation['reasons'].append(f"RSI超卖 ({rsi:.1f}) - 买入机会")
                    recommendation['action'] = 'BUY'
            
            if 'technical' in analysis and 'macd' in analysis['technical']:
                macd = analysis['technical']['macd']
                if macd['hist'] > 0:
                    recommendation['reasons'].append("MACD金叉 - 上涨趋势")
                else:
                    recommendation['reasons'].append("MACD死叉 - 下跌趋势")
            
            # Sentiment analysis
            if 'sentiment' in analysis and analysis['sentiment']:
                sentiment = analysis['sentiment']['sentiment']
                if sentiment == 'Positive':
                    recommendation['reasons'].append("新闻情绪积极")
                    if recommendation['action'] == 'HOLD':
                        recommendation['action'] = 'HOLD/BUY'
                elif sentiment == 'Negative':
                    recommendation['reasons'].append("新闻情绪消极")
                    if holding['pnl_percent'] < -5:
                        recommendation['reasons'].append("已亏损超5% - 考虑止损")
            
            # Position-based logic
            if holding['pnl_percent'] > 15:
                recommendation['reasons'].append(f"已盈利{holding['pnl_percent']:.1f}% - 考虑止盈")
                if recommendation['action'] == 'HOLD':
                    recommendation['action'] = 'SELL/HOLD'
            
            recommendations.append(recommendation)
        
        return recommendations

def main():
    analyzer = DeepStockAnalyzer()
    recommendations = analyzer.generate_recommendations()
    
    print("\n" + "="*80)
    print("SUMMARY - MONDAY ACTION PLAN")
    print("="*80)
    
    for rec in recommendations:
        print(f"\n{rec['ticker']}: {rec['action']}")
        print(f"Current P&L: {rec['current_position']['pnl_percent']:.2f}%")
        print("Reasons:")
        for reason in rec['reasons']:
            print(f"  • {reason}")

if __name__ == '__main__':
    main()
