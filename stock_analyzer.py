#!/usr/bin/env python3
"""
Rick's Stock Portfolio Analyzer
Custom tool for kcn's portfolio analysis
Supports both US and Hong Kong stocks
"""

import json
import os
import requests
import yfinance as yf
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

    # Eastmoney market prefix map for US stocks (NASDAQ=105, NYSE=106)
    EASTMONEY_US_PREFIX = {
        'NVDA': '105', 'RKLB': '105', 'QQQ': '105', 'AAPL': '105', 'TSLA': '105',
        'MSFT': '105', 'AMZN': '105', 'GOOGL': '105', 'META': '105', 'NVDL': '105',
        'CRCL': '106', 'OKLO': '106', 'HIMS': '106', 'PLTR': '106',
    }

    def get_us_quotes_eastmoney(self, tickers: List[str]) -> Dict[str, Dict]:
        """Batch fetch US stock quotes from Eastmoney (NASDAQ=105, NYSE=106)"""
        secids = []
        for t in tickers:
            prefix = self.EASTMONEY_US_PREFIX.get(t, '105')  # default NASDAQ
            secids.append(f'{prefix}.{t}')
        url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            'fltt': 2, 'invt': 2,
            'fields': 'f12,f14,f2,f3,f18,f15,f16,f17',
            'secids': ','.join(secids),
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        }
        headers = {'Referer': 'https://quote.eastmoney.com/'}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            results = {}
            for item in r.json().get('data', {}).get('diff', []):
                ticker = item['f12']
                current = item.get('f2')
                prev_close = item.get('f18')
                if current and current != '-':
                    results[ticker] = {
                        'c': float(current),
                        'pc': float(prev_close) if prev_close else float(current),
                        'h': float(item.get('f15') or current),
                        'l': float(item.get('f16') or current),
                        'o': float(item.get('f17') or current),
                        'name': item.get('f14', ''),
                        'source': 'Eastmoney'
                    }
            return results
        except Exception as e:
            print(f"⚠️  Eastmoney US batch failed: {e}")
            return {}

    def get_hk_quotes_eastmoney(self, codes: List[str]) -> Dict[str, Dict]:
        """Batch fetch HK stock quotes from Eastmoney (no rate limit, CN data)"""
        secids = ','.join([f'116.{c}' for c in codes])
        url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            'fltt': 2, 'invt': 2,
            'fields': 'f12,f14,f2,f3,f4,f5,f15,f16,f17,f18',
            'secids': secids,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        }
        headers = {'Referer': 'https://quote.eastmoney.com/'}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            results = {}
            for item in data.get('data', {}).get('diff', []):
                code = item['f12']  # e.g. '02208'
                current = item.get('f2')
                prev_close = item.get('f18')
                high = item.get('f15')
                low = item.get('f16')
                open_p = item.get('f17')
                if current and current != '-':
                    results[code] = {
                        'c': float(current),
                        'pc': float(prev_close) if prev_close else float(current),
                        'h': float(high) if high else float(current),
                        'l': float(low) if low else float(current),
                        'o': float(open_p) if open_p else float(current),
                        'name': item.get('f14', ''),
                        'source': 'Eastmoney'
                    }
            return results
        except Exception as e:
            print(f"⚠️  Eastmoney batch failed: {e}")
            return {}

    def get_quote_yfinance(self, symbol: str) -> Optional[Dict]:
        """Get quote from Yahoo Finance (works for both US and HK stocks)"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            current = info.get('lastPrice') or info.get('regularMarketPrice')
            prev_close = info.get('regularMarketPreviousClose') or info.get('previousClose')
            if not current:
                return None
            return {
                'c': current,
                'h': info.get('dayHigh', current),
                'l': info.get('dayLow', current),
                'o': info.get('open', current),
                'pc': prev_close or current,
                'source': 'Yahoo Finance'
            }
        except Exception as e:
            print(f"⚠️  Yahoo Finance failed for {symbol}: {e}")
            return None

    def get_quote_sina_hk(self, code: str) -> Optional[Dict]:
        """Get HK stock quote from Sina Finance (e.g. code='02208')"""
        # Sina expects 5-digit zero-padded code
        padded = code.lstrip('0').zfill(5)
        symbol = f"r_hk{padded}"
        url = f"https://hq.sinajs.cn/list={symbol}"
        headers = {'Referer': 'https://finance.sina.com.cn'}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            text = response.text
            # Format: var hq_str_r_hkXXXXX="name,price,change,pct,open,high,low,vol,...";
            if '=""' in text or '=""' in text:
                return None
            import re
            match = re.search(r'"([^"]+)"', text)
            if not match:
                return None
            fields = match.group(1).split(',')
            if len(fields) < 7 or not fields[1].strip():
                return None
            current = float(fields[1])
            prev_close = current - float(fields[2]) if fields[2] else current
            return {
                'c': current,
                'h': float(fields[5]) if fields[5] else current,
                'l': float(fields[6]) if fields[6] else current,
                'o': float(fields[4]) if fields[4] else current,
                'pc': prev_close,
                'source': 'Sina'
            }
        except Exception as e:
            print(f"⚠️  Sina HK failed for {code}: {e}")
            return None

    def get_quote_tencent_hk(self, code: str) -> Optional[Dict]:
        """Get HK stock quote from Tencent Finance (e.g. code='02208')"""
        padded = code.zfill(6)
        symbol = f"r_hk{padded}"
        url = f"https://qt.gtimg.cn/q={symbol}"
        try:
            response = requests.get(url, timeout=10)
            response.encoding = 'gbk'
            text = response.text
            # Format: v_r_hkXXXXXX="1~name~code~price~prev_close~change~pct~...";
            import re
            match = re.search(r'"([^"]+)"', text)
            if not match:
                return None
            fields = match.group(1).split('~')
            if len(fields) < 6 or not fields[3].strip():
                return None
            current = float(fields[3])
            prev_close = float(fields[4]) if fields[4] else current
            return {
                'c': current,
                'h': float(fields[33]) if len(fields) > 33 and fields[33] else current,
                'l': float(fields[34]) if len(fields) > 34 and fields[34] else current,
                'o': float(fields[5]) if fields[5] else current,
                'pc': prev_close,
                'source': 'Tencent'
            }
        except Exception as e:
            print(f"⚠️  Tencent HK failed for {code}: {e}")
            return None

    def get_quote_sina_us(self, ticker: str) -> Optional[Dict]:
        """Get US stock quote from Sina Finance (e.g. ticker='NVDA')"""
        symbol = f"gb_{ticker.lower()}"
        url = f"https://hq.sinajs.cn/list={symbol}"
        headers = {'Referer': 'https://finance.sina.com.cn'}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            text = response.text
            import re
            match = re.search(r'"([^"]+)"', text)
            if not match:
                return None
            fields = match.group(1).split(',')
            # Sina US format: name, price, after_price, change_pct, open, high, low, ...
            if len(fields) < 5 or not fields[1].strip():
                return None
            current = float(fields[1])
            open_p = float(fields[5]) if len(fields) > 5 and fields[5] else current
            high_p = float(fields[6]) if len(fields) > 6 and fields[6] else current
            low_p  = float(fields[7]) if len(fields) > 7 and fields[7] else current
            # prev close = current / (1 + pct/100)
            try:
                pct = float(fields[3].replace('%',''))
                prev_close = current / (1 + pct / 100)
            except Exception:
                prev_close = current
            return {
                'c': current,
                'h': high_p,
                'l': low_p,
                'o': open_p,
                'pc': prev_close,
                'source': 'Sina'
            }
        except Exception as e:
            print(f"⚠️  Sina US failed for {ticker}: {e}")
            return None

    def get_hk_quote(self, code: str) -> Optional[Dict]:
        """Get HK stock quote: yfinance -> Tencent -> Sina"""
        # Yahoo Finance uses XXXXX.HK format (no leading zeros beyond 4 digits)
        yf_symbol = f"{code.lstrip('0') or '0'}.HK"
        quote = self.get_quote_yfinance(yf_symbol)
        if quote:
            print(f"✓ {code}: Yahoo Finance ({yf_symbol})")
            return quote
        # Fallback to Tencent
        print(f"→ {code}: Trying Tencent Finance...")
        quote = self.get_quote_tencent_hk(code)
        if quote:
            print(f"✓ {code}: Tencent Finance")
            return quote
        # Fallback to Sina
        print(f"→ {code}: Trying Sina Finance...")
        quote = self.get_quote_sina_hk(code)
        if quote:
            print(f"✓ {code}: Sina Finance")
            return quote
        print(f"✗ {code}: All HK APIs failed")
        return None

    def get_quote(self, ticker: str) -> Optional[Dict]:
        """Get US quote with automatic fallback: yfinance -> Sina -> Finnhub -> Alpha Vantage -> Polygon.io"""
        # Try Yahoo Finance first
        quote = self.get_quote_yfinance(ticker)
        if quote:
            print(f"✓ {ticker}: Yahoo Finance")
            return quote

        # Try Sina Finance
        quote = self.get_quote_sina_us(ticker)
        if quote:
            print(f"✓ {ticker}: Sina Finance")
            return quote

        # Fallback to Finnhub
        print(f"→ {ticker}: Trying Finnhub...")
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
        """Update US stock portfolio: Eastmoney -> yfinance -> Finnhub -> AV -> Polygon"""
        print("Updating US portfolio prices...")
        us_portfolio = self.portfolio['portfolios']['us_stocks']
        symbols = [h['ticker'] for h in us_portfolio['holdings']]

        # 1st: Eastmoney batch (CN data, no rate limit, works from abroad)
        em_data = self.get_us_quotes_eastmoney(symbols)
        missing = [s for s in symbols if s not in em_data]

        # 2nd: yfinance batch for missing tickers
        yf_data = {}
        if missing:
            try:
                tickers_obj = yf.Tickers(' '.join(missing))
                for sym in missing:
                    try:
                        info = tickers_obj.tickers[sym].fast_info
                        current = info.get('lastPrice') or info.get('regularMarketPrice')
                        if current:
                            yf_data[sym] = current
                    except Exception:
                        pass
            except Exception as e:
                print(f"⚠️  yfinance batch failed: {e}")

        for holding in us_portfolio['holdings']:
            ticker = holding['ticker']
            old_price = holding['current_price']

            if ticker in em_data:
                q = em_data[ticker]
                new_price = q['c']
                pct = (q['c'] - q['pc']) / q['pc'] * 100 if q['pc'] else 0
                print(f"✓ {ticker} {q['name']}: ${old_price:.2f} -> ${new_price:.2f} ({pct:+.2f}%) [Eastmoney]")
            elif ticker in yf_data:
                new_price = yf_data[ticker]
                print(f"✓ {ticker}: ${old_price:.2f} -> ${new_price:.2f} [Yahoo Finance]")
            else:
                # Per-ticker last-resort fallback
                quote = self.get_quote_finnhub(ticker) or \
                        self.get_quote_alpha_vantage(ticker) or \
                        self.get_quote_polygon(ticker)
                if not quote:
                    print(f"✗ {ticker}: All APIs failed")
                    continue
                new_price = quote['c']
                print(f"✓ {ticker}: ${old_price:.2f} -> ${new_price:.2f} [fallback]")

            holding['current_price'] = new_price
            holding['pnl_percent'] = ((new_price - holding['cost_basis']) / holding['cost_basis']) * 100

        total_cost = sum(h['shares'] * h['cost_basis'] for h in us_portfolio['holdings'])
        total_current = sum(h['shares'] * h['current_price'] for h in us_portfolio['holdings'])
        total_pnl = total_current - total_cost
        us_portfolio['total_cost'] = total_cost
        us_portfolio['total_current_value'] = total_current
        us_portfolio['total_pnl'] = total_pnl
        us_portfolio['total_pnl_percent'] = (total_pnl / total_cost) * 100
        print(f"US Portfolio P&L: ${total_pnl:.2f} ({us_portfolio['total_pnl_percent']:.2f}%)")
    
    def update_hk_portfolio_prices(self):
        """Update Hong Kong stock portfolio with current prices (Eastmoney batch)"""
        print("\nUpdating HK portfolio prices...")
        hk_portfolio = self.portfolio['portfolios']['hk_stocks']
        codes = [h['ticker'] for h in hk_portfolio['holdings']]

        # Primary: Eastmoney batch (reliable, no rate limit)
        em_data = self.get_hk_quotes_eastmoney(codes)
        
        for holding in hk_portfolio['holdings']:
            code = holding['ticker']
            quote = em_data.get(code)
            if quote:
                old_price = holding['current_price']
                holding['current_price'] = quote['c']
                holding['current_value'] = quote['c'] * holding['shares']
                holding['today_change'] = (quote['c'] - quote['pc']) * holding['shares']
                pct = (quote['c'] - quote['pc']) / quote['pc'] * 100 if quote['pc'] else 0
                print(f"✓ {code} {quote['name']}: HKD {old_price:.3f} -> HKD {quote['c']:.3f} ({pct:+.2f}%)")
            else:
                # Fallback to yfinance
                yf_sym = f"{code.lstrip('0') or '0'}.HK"
                yf_quote = self.get_quote_yfinance(yf_sym)
                if yf_quote:
                    old_price = holding['current_price']
                    holding['current_price'] = yf_quote['c']
                    holding['current_value'] = yf_quote['c'] * holding['shares']
                    holding['today_change'] = (yf_quote['c'] - yf_quote['pc']) * holding['shares']
                    print(f"✓ {code} (yfinance): HKD {old_price:.3f} -> HKD {yf_quote['c']:.3f}")
                else:
                    print(f"✗ {code}: All HK APIs failed")

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
