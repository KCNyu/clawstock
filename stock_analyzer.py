#!/usr/bin/env python3
"""
Rick's Stock Portfolio Analyzer
Custom tool for kcn's portfolio analysis
Supports both US and Hong Kong stocks
"""

import json
import os
import requests
from datetime import datetime
from typing import Dict, List, Optional

class StockAnalyzer:
    def __init__(self):
        self.load_api_keys()
        self.load_portfolio()
    
    def load_api_keys(self):
        """Load API keys from .api_keys file"""
        keys = {}
        with open('.api_keys', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        keys[key] = value
        
        self.finnhub_key = keys.get('FINNHUB_API_KEY')
        self.alpha_vantage_key = keys.get('ALPHA_VANTAGE_API_KEY')
        self.polygon_key = keys.get('POLYGON_API_KEY')
    
    def load_portfolio(self):
        """Load portfolio from portfolio.json"""
        with open('portfolio.json', 'r') as f:
            self.portfolio = json.load(f)
    
    def get_quote_finnhub(self, ticker: str) -> Optional[Dict]:
        """Get real-time quote from Finnhub"""
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={self.finnhub_key}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            # Check if data is valid (Finnhub returns 'c' for current price)
            if data and 'c' in data and data['c'] > 0:
                return data
            return None
        except Exception as e:
            print(f"⚠️  Finnhub failed for {ticker}: {e}")
            return None
    
    def get_quote_alpha_vantage(self, ticker: str) -> Optional[Dict]:
        """Get real-time quote from Alpha Vantage (fallback)"""
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={self.alpha_vantage_key}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Alpha Vantage format: {"Global Quote": {"05. price": "123.45", ...}}
            if 'Global Quote' in data and '05. price' in data['Global Quote']:
                quote = data['Global Quote']
                return {
                    'c': float(quote['05. price']),  # current price
                    'h': float(quote['03. high']),   # high
                    'l': float(quote['04. low']),    # low
                    'o': float(quote['02. open']),   # open
                    'pc': float(quote['08. previous close'])  # previous close
                }
            return None
        except Exception as e:
            print(f"⚠️  Alpha Vantage failed for {ticker}: {e}")
            return None
    
    def get_quote_polygon(self, ticker: str) -> Optional[Dict]:
        """Get real-time quote from Polygon.io (fallback)"""
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?adjusted=true&apiKey={self.polygon_key}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Polygon format: {"results": [{"c": 123.45, "h": 125, "l": 122, "o": 123}]}
            if 'results' in data and len(data['results']) > 0:
                result = data['results'][0]
                return {
                    'c': result['c'],   # close (current)
                    'h': result['h'],   # high
                    'l': result['l'],   # low
                    'o': result['o'],   # open
                    'pc': result['c']   # use close as previous close
                }
            return None
        except Exception as e:
            print(f"⚠️  Polygon.io failed for {ticker}: {e}")
            return None
    
    def get_quote(self, ticker: str) -> Optional[Dict]:
        """Get quote with automatic fallback: Finnhub -> Alpha Vantage -> Polygon.io"""
        # Try Finnhub first (primary)
        quote = self.get_quote_finnhub(ticker)
        if quote:
            print(f"✓ {ticker}: Finnhub")
            return quote
        
        # Fallback to Alpha Vantage
        print(f"→ {ticker}: Trying Alpha Vantage...")
        quote = self.get_quote_alpha_vantage(ticker)
        if quote:
            print(f"✓ {ticker}: Alpha Vantage")
            return quote
        
        # Fallback to Polygon.io
        print(f"→ {ticker}: Trying Polygon.io...")
        quote = self.get_quote_polygon(ticker)
        if quote:
            print(f"✓ {ticker}: Polygon.io")
            return quote
        
        print(f"✗ {ticker}: All APIs failed")
        return None
    
    def get_company_profile_finnhub(self, ticker: str) -> Optional[Dict]:
        """Get company profile from Finnhub"""
        url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={self.finnhub_key}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching profile for {ticker}: {e}")
            return None
    
    def get_news_finnhub(self, ticker: str, days: int = 7) -> Optional[List[Dict]]:
        """Get recent news from Finnhub"""
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={start_date.strftime('%Y-%m-%d')}&to={end_date.strftime('%Y-%m-%d')}&token={self.finnhub_key}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching news for {ticker}: {e}")
            return None
    
    def update_us_portfolio_prices(self):
        """Update US stock portfolio with current prices"""
        print("Updating US portfolio prices...")
        us_portfolio = self.portfolio['portfolios']['us_stocks']
        
        for holding in us_portfolio['holdings']:
            ticker = holding['ticker']
            quote = self.get_quote(ticker)
            if quote and 'c' in quote:
                old_price = holding['current_price']
                new_price = quote['c']
                holding['current_price'] = new_price
                
                # Recalculate P&L
                cost = holding['cost_basis']
                holding['pnl_percent'] = ((new_price - cost) / cost) * 100
                
                print(f"{ticker}: ${old_price:.2f} -> ${new_price:.2f}")
        
        # Update totals
        total_cost = sum(h['shares'] * h['cost_basis'] for h in us_portfolio['holdings'])
        total_current = sum(h['shares'] * h['current_price'] for h in us_portfolio['holdings'])
        total_pnl = total_current - total_cost
        
        us_portfolio['total_cost'] = total_cost
        us_portfolio['total_current_value'] = total_current
        us_portfolio['total_pnl'] = total_pnl
        us_portfolio['total_pnl_percent'] = (total_pnl / total_cost) * 100
        
        print(f"US Portfolio P&L: ${total_pnl:.2f} ({us_portfolio['total_pnl_percent']:.2f}%)")
    
    def update_hk_portfolio_prices(self):
        """Update Hong Kong stock portfolio with current prices"""
        print("\nUpdating HK portfolio prices...")
        hk_portfolio = self.portfolio['portfolios']['hk_stocks']
        
        for holding in hk_portfolio['holdings']:
            ticker = holding['ticker_finnhub']
            quote = self.get_quote(ticker)
            if quote and 'c' in quote:
                old_price = holding['current_price']
                new_price = quote['c']
                holding['current_price'] = new_price
                holding['current_value'] = new_price * holding['shares']
                
                # Calculate today's change
                if 'pc' in quote:  # previous close
                    prev_close = quote['pc']
                    holding['today_change'] = (new_price - prev_close) * holding['shares']
                
                print(f"{holding['ticker']}: HKD {old_price:.2f} -> HKD {new_price:.2f}")
        
        # Update totals
        total_current = sum(h['current_value'] for h in hk_portfolio['holdings'])
        today_change = sum(h.get('today_change', 0) for h in hk_portfolio['holdings'])
        
        hk_portfolio['total_current_value'] = total_current
        hk_portfolio['today_total_change'] = today_change
        
        print(f"HK Portfolio Value: HKD {total_current:.2f} (Today: {today_change:+.2f})")
    
    def update_all_prices(self):
        """Update both US and HK portfolios"""
        self.update_us_portfolio_prices()
        self.update_hk_portfolio_prices()
        
        # Update timestamp
        self.portfolio['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Save updated portfolio
        with open('portfolio.json', 'w') as f:
            json.dump(self.portfolio, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Portfolio updated at {self.portfolio['last_updated']}")
    
    def analyze_holding(self, ticker: str, market: str = 'us') -> Dict:
        """Comprehensive analysis of a single holding"""
        print(f"\n{'='*60}")
        print(f"Analyzing {ticker} ({market.upper()})...")
        print(f"{'='*60}")
        
        analysis = {
            'ticker': ticker,
            'market': market,
            'timestamp': datetime.now().isoformat()
        }
        
        # For HK stocks, use the Finnhub format
        finnhub_ticker = ticker
        if market == 'hk':
            # Remove leading zeros and add .HK suffix
            finnhub_ticker = f"{int(ticker)}.HK"
        
        # Get current quote
        quote = self.get_quote(finnhub_ticker)
        if quote:
            analysis['quote'] = {
                'current': quote.get('c'),
                'high': quote.get('h'),
                'low': quote.get('l'),
                'open': quote.get('o'),
                'previous_close': quote.get('pc')
            }
            currency = 'HKD' if market == 'hk' else 'USD'
            print(f"Current Price: {currency} {quote.get('c'):.2f}")
            print(f"Day Range: {currency} {quote.get('l'):.2f} - {currency} {quote.get('h'):.2f}")
        
        # Get company profile
        profile = self.get_company_profile_finnhub(finnhub_ticker)
        if profile and profile.get('name'):
            analysis['profile'] = profile
            print(f"Company: {profile.get('name')}")
            print(f"Industry: {profile.get('finnhubIndustry', 'N/A')}")
            if profile.get('marketCapitalization'):
                print(f"Market Cap: ${profile.get('marketCapitalization', 0):.2f}B")
        
        # Get recent news
        news = self.get_news_finnhub(finnhub_ticker, days=3)
        if news and len(news) > 0:
            analysis['recent_news'] = news[:5]  # Top 5 news items
            print(f"\nRecent News ({len(news)} items in last 3 days):")
            for i, item in enumerate(news[:3], 1):
                print(f"{i}. {item.get('headline')[:80]}...")
        else:
            print("\nNo recent news available.")
        
        return analysis
    
    def generate_portfolio_report(self) -> str:
        """Generate a comprehensive portfolio report"""
        report = []
        report.append("=" * 80)
        report.append(f"PORTFOLIO REPORT - {self.portfolio['owner'].upper()}")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        report.append("")
        
        # US Stocks
        us = self.portfolio['portfolios']['us_stocks']
        report.append("US STOCKS (USD)")
        report.append("-" * 80)
        report.append(f"Total Cost Basis:    ${us['total_cost']:,.2f}")
        report.append(f"Current Value:       ${us['total_current_value']:,.2f}")
        report.append(f"Total P&L:           ${us['total_pnl']:,.2f} ({us['total_pnl_percent']:.2f}%)")
        report.append("")
        report.append(f"{'Ticker':<8} {'Shares':<8} {'Cost':<10} {'Current':<10} {'P&L':<12} {'%':<10}")
        report.append("-" * 80)
        
        for h in us['holdings']:
            pnl_value = h['shares'] * (h['current_price'] - h['cost_basis'])
            emoji = "🎉" if h['pnl_percent'] > 0 else "📉" if h['pnl_percent'] < -5 else ""
            report.append(
                f"{h['ticker']:<8} {h['shares']:<8} ${h['cost_basis']:<9.2f} "
                f"${h['current_price']:<9.2f} ${pnl_value:<11.2f} "
                f"{h['pnl_percent']:>6.2f}% {emoji}"
            )
        
        report.append("")
        
        # HK Stocks
        hk = self.portfolio['portfolios']['hk_stocks']
        report.append("HONG KONG STOCKS (HKD)")
        report.append("-" * 80)
        report.append(f"Total Value:         HKD {hk['total_current_value']:,.2f}")
        report.append(f"Today's Change:      HKD {hk['today_total_change']:+,.2f}")
        report.append("")
        report.append(f"{'Code':<8} {'Shares':<8} {'Price':<12} {'Value':<12} {'Today':<12}")
        report.append("-" * 80)
        
        for h in hk['holdings']:
            today_change = h.get('today_change', 0)
            emoji = "🎉" if today_change > 0 else "📉" if today_change < -1000 else ""
            report.append(
                f"{h['ticker']:<8} {h['shares']:<8} "
                f"HKD {h['current_price']:<8.2f} "
                f"HKD {h['current_value']:<8.2f} "
                f"HKD {today_change:>8.2f} {emoji}"
            )
        
        report.append("=" * 80)
        
        # Summary
        # Convert HKD to USD for total (approximate rate: 1 USD = 7.8 HKD)
        hkd_to_usd = hk['total_current_value'] / 7.8
        total_usd = us['total_current_value'] + hkd_to_usd
        
        report.append("")
        report.append("TOTAL PORTFOLIO (USD equivalent)")
        report.append("-" * 80)
        report.append(f"US Stocks:           ${us['total_current_value']:,.2f}")
        report.append(f"HK Stocks:           ${hkd_to_usd:,.2f} (HKD {hk['total_current_value']:,.2f})")
        report.append(f"Total Value:         ${total_usd:,.2f}")
        report.append("=" * 80)
        
        return "\n".join(report)

def main():
    analyzer = StockAnalyzer()
    
    # Update prices
    analyzer.update_all_prices()
    
    # Generate report
    print("\n")
    print(analyzer.generate_portfolio_report())
    
    # Optionally analyze specific holdings
    # print("\n\nDETAILED ANALYSIS")
    # print("=" * 80)
    # analyzer.analyze_holding("NVDA", "us")
    # analyzer.analyze_holding("02208", "hk")

if __name__ == '__main__':
    main()
