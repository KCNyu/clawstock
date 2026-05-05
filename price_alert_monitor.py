#!/usr/bin/env python3
"""
Price Alert Monitor
Checks stock prices and sends alerts when targets are hit
"""

import json
import requests
from datetime import datetime

class PriceAlertMonitor:
    def __init__(self):
        self.load_api_keys()
        self.load_alerts()
    
    def load_api_keys(self):
        keys = {}
        with open('.api_keys', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        keys[key] = value
        self.finnhub_key = keys.get('FINNHUB_API_KEY')
    
    def load_alerts(self):
        """Define price alerts"""
        self.alerts = {
            'us_stocks': [
                {
                    'ticker': 'CRCL',
                    'name': 'Circle',
                    'current': 101.92,
                    'alerts': [
                        {'price': 102.00, 'action': '🎯 卖出 5股', 'type': 'above'},
                        {'price': 98.00, 'action': '⚠️ 考虑全部止损', 'type': 'below'},
                    ]
                },
                {
                    'ticker': 'NVDA',
                    'name': '英伟达',
                    'current': 177.83,
                    'alerts': [
                        {'price': 175.00, 'action': '🎯 买入 2股', 'type': 'below'},
                        {'price': 170.00, 'action': '⚠️ 止损位', 'type': 'below'},
                        {'price': 185.00, 'action': '📈 突破阻力位', 'type': 'above'},
                    ]
                },
                {
                    'ticker': 'RKLB',
                    'name': 'Rocket Lab',
                    'current': 70.12,
                    'alerts': [
                        {'price': 73.00, 'action': '📈 考虑减仓', 'type': 'above'},
                        {'price': 68.00, 'action': '⚠️ 止损位', 'type': 'below'},
                    ]
                },
                {
                    'ticker': 'QQQ',
                    'name': '纳指ETF',
                    'current': 599.76,
                    'alerts': [
                        {'price': 610.00, 'action': '📈 回到高位', 'type': 'above'},
                        {'price': 590.00, 'action': '⚠️ 关键支撑', 'type': 'below'},
                    ]
                },
            ],
            'hk_stocks': [
                {
                    'ticker': '02208',
                    'name': '金风科技',
                    'current': 14.46,
                    'alerts': [
                        {'price': 15.00, 'action': '📈 考虑止盈', 'type': 'above'},
                        {'price': 13.50, 'action': '⚠️ 支撑位', 'type': 'below'},
                    ]
                },
                {
                    'ticker': '03032',
                    'name': '恒生科技ETF',
                    'current': 4.924,
                    'alerts': [
                        {'price': 4.90, 'action': '🎯 买入 1000股', 'type': 'below'},
                        {'price': 5.20, 'action': '📈 突破阻力', 'type': 'above'},
                    ]
                },
                {
                    'ticker': '07226',
                    'name': 'XL二南方恒科',
                    'current': 3.978,
                    'alerts': [
                        {'price': 3.70, 'action': '⚠️ 止损位', 'type': 'below'},
                        {'price': 4.20, 'action': '📈 考虑清仓', 'type': 'above'},
                    ]
                },
                # 07709/07747 已清仓 2026-05-05，移除相关提醒
            ]
        }
    
    def get_us_price(self, ticker):
        """Get current US stock price"""
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={self.finnhub_key}"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            return data.get('c')
        except:
            return None
    
    def get_hk_price(self, ticker):
        """Get current HK stock price from Tencent"""
        code = f"hk{ticker}"
        url = f"https://qt.gtimg.cn/q={code}"
        try:
            response = requests.get(url, timeout=10)
            response.encoding = 'gbk'
            content = response.text
            if 'v_hk' not in content:
                return None
            start = content.find('"') + 1
            end = content.rfind('"')
            data_str = content[start:end]
            parts = data_str.split('~')
            if len(parts) < 4:
                return None
            return float(parts[3])
        except:
            return None
    
    def check_alerts(self):
        """Check all price alerts"""
        print("="*80)
        print(f"价格提醒检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        triggered_alerts = []
        
        # Check US stocks
        print("\n🇺🇸 美股检查：")
        for stock in self.alerts['us_stocks']:
            ticker = stock['ticker']
            current_price = self.get_us_price(ticker)
            
            if current_price:
                print(f"\n{ticker} ({stock['name']}): ${current_price:.2f}")
                
                for alert in stock['alerts']:
                    target = alert['price']
                    action = alert['action']
                    alert_type = alert['type']
                    
                    triggered = False
                    if alert_type == 'above' and current_price >= target:
                        triggered = True
                    elif alert_type == 'below' and current_price <= target:
                        triggered = True
                    
                    if triggered:
                        msg = f"  🔔 触发提醒！价格 ${current_price:.2f} {alert_type} ${target:.2f}"
                        msg += f"\n     → {action}"
                        print(msg)
                        triggered_alerts.append({
                            'ticker': ticker,
                            'name': stock['name'],
                            'price': current_price,
                            'target': target,
                            'action': action
                        })
        
        # Check HK stocks
        print("\n🇭🇰 港股检查：")
        for stock in self.alerts['hk_stocks']:
            ticker = stock['ticker']
            current_price = self.get_hk_price(ticker)
            
            if current_price:
                print(f"\n{ticker} ({stock['name']}): HKD {current_price:.3f}")
                
                for alert in stock['alerts']:
                    target = alert['price']
                    action = alert['action']
                    alert_type = alert['type']
                    
                    triggered = False
                    if alert_type == 'above' and current_price >= target:
                        triggered = True
                    elif alert_type == 'below' and current_price <= target:
                        triggered = True
                    
                    if triggered:
                        msg = f"  🔔 触发提醒！价格 HKD {current_price:.3f} {alert_type} HKD {target:.2f}"
                        msg += f"\n     → {action}"
                        print(msg)
                        triggered_alerts.append({
                            'ticker': ticker,
                            'name': stock['name'],
                            'price': current_price,
                            'target': target,
                            'action': action
                        })
        
        print("\n" + "="*80)
        if triggered_alerts:
            print(f"⚠️ 共有 {len(triggered_alerts)} 个价格提醒被触发！")
        else:
            print("✅ 暂无价格提醒触发")
        print("="*80)
        
        return triggered_alerts

if __name__ == '__main__':
    monitor = PriceAlertMonitor()
    monitor.check_alerts()
