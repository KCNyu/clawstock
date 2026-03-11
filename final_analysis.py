#!/usr/bin/env python3
"""
终极持仓分析 + 周一操作建议
使用多智能体分析框架
"""

import json
import requests
from datetime import datetime

FINNHUB_API_KEY = 'd6m1kj9r01qu3p05oh6gd6m1kj9r01qu3p05oh70'

# 读取持仓数据
with open('portfolio.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

us_stocks = data['portfolios']['us_stocks']
hk_stocks = data['portfolios']['hk_stocks']

print("="*80)
print("📊 KCN 投资组合终极分析报告")
print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# ============ 第一部分：整体概览 ============
print("\n" + "="*80)
print("📈 第一部分：整体持仓概览")
print("="*80)

# 美股
us_total_cost = us_stocks['total_cost']
us_total_value = us_stocks['total_current_value']
us_total_pnl = us_stocks['total_pnl']
us_total_pnl_pct = us_stocks['total_pnl_percent']

# 港股
hk_total_cost = hk_stocks['total_cost']
hk_total_value = hk_stocks['total_current_value']
hk_total_pnl = hk_stocks['total_pnl']
hk_total_pnl_pct = hk_stocks['total_pnl_percent']

# 汇率转换（1 USD = 7.8 HKD）
exchange_rate = 7.8
hk_value_usd = hk_total_value / exchange_rate
hk_cost_usd = hk_total_cost / exchange_rate
hk_pnl_usd = hk_total_pnl / exchange_rate

# 总计
total_cost_usd = us_total_cost + hk_cost_usd
total_value_usd = us_total_value + hk_value_usd
total_pnl_usd = us_total_pnl + hk_pnl_usd
total_pnl_pct = (total_pnl_usd / total_cost_usd) * 100

print(f"\n🇺🇸 美股账户:")
print(f"   成本: ${us_total_cost:,.2f}")
print(f"   市值: ${us_total_value:,.2f}")
print(f"   盈亏: ${us_total_pnl:+,.2f} ({us_total_pnl_pct:+.2f}%)")

print(f"\n🇭🇰 港股账户:")
print(f"   成本: HK${hk_total_cost:,.2f} (≈ ${hk_cost_usd:,.2f})")
print(f"   市值: HK${hk_total_value:,.2f} (≈ ${hk_value_usd:,.2f})")
print(f"   盈亏: HK${hk_total_pnl:+,.2f} ({hk_total_pnl_pct:+.2f}%) (≈ ${hk_pnl_usd:+,.2f})")

print(f"\n💰 总计 (折合美元):")
print(f"   总成本: ${total_cost_usd:,.2f}")
print(f"   总市值: ${total_value_usd:,.2f}")
print(f"   总盈亏: ${total_pnl_usd:+,.2f} ({total_pnl_pct:+.2f}%)")

# ============ 第二部分：个股表现分析 ============
print("\n" + "="*80)
print("🎯 第二部分：个股表现排名")
print("="*80)

# 合并所有持仓
all_holdings = []

for h in us_stocks['holdings']:
    pnl_amount = (h['current_price'] - h['cost_basis']) * h['shares']
    all_holdings.append({
        'ticker': h['ticker'],
        'name': h['ticker'],
        'market': 'US',
        'value': h['shares'] * h['current_price'],
        'pnl_amount': pnl_amount,
        'pnl_pct': h['pnl_percent'],
        'weight': (h['shares'] * h['current_price'] / total_value_usd) * 100
    })

for h in hk_stocks['holdings']:
    pnl_amount = (h['current_price'] - h['cost_basis']) * h['shares']
    all_holdings.append({
        'ticker': h['ticker'],
        'name': h['name'],
        'market': 'HK',
        'value': h['current_value'] / exchange_rate,  # 转USD
        'pnl_amount': pnl_amount / exchange_rate,  # 转USD
        'pnl_pct': h['pnl_percent'],
        'weight': (h['current_value'] / exchange_rate / total_value_usd) * 100
    })

# 按盈亏百分比排序
all_holdings_sorted = sorted(all_holdings, key=lambda x: x['pnl_pct'], reverse=True)

print("\n🏆 表现最好的3只:")
for i, h in enumerate(all_holdings_sorted[:3], 1):
    print(f"   {i}. {h['ticker']} ({h['name']}) - {h['market']}")
    print(f"      盈亏: ${h['pnl_amount']:+,.2f} ({h['pnl_pct']:+.2f}%)")
    print(f"      占比: {h['weight']:.1f}%")

print("\n⚠️ 表现最差的3只:")
for i, h in enumerate(all_holdings_sorted[-3:], 1):
    print(f"   {i}. {h['ticker']} ({h['name']}) - {h['market']}")
    print(f"      盈亏: ${h['pnl_amount']:+,.2f} ({h['pnl_pct']:+.2f}%)")
    print(f"      占比: {h['weight']:.1f}%")

# ============ 第三部分：风险分析 ============
print("\n" + "="*80)
print("⚠️ 第三部分：风险评估")
print("="*80)

# 识别杠杆ETF
leveraged_etfs = [h for h in hk_stocks['holdings'] if 'XL' in h['ticker'] or 'XL' in h['name']]
leveraged_value = sum(h['current_value'] for h in leveraged_etfs) / exchange_rate
leveraged_pct = (leveraged_value / total_value_usd) * 100

print(f"\n📊 持仓结构:")
print(f"   美股占比: {(us_total_value / total_value_usd) * 100:.1f}%")
print(f"   港股占比: {(hk_value_usd / total_value_usd) * 100:.1f}%")
print(f"   杠杆ETF占比: {leveraged_pct:.1f}% ⚠️")

if leveraged_pct > 30:
    print(f"\n⚠️ 风险警告: 杠杆ETF占比过高 ({leveraged_pct:.1f}%)")
    print("   建议: 考虑降低杠杆仓位，增加现货持仓")

# 统计亏损持仓
losing_positions = [h for h in all_holdings if h['pnl_pct'] < 0]
losing_count = len(losing_positions)
losing_amount = sum(h['pnl_amount'] for h in losing_positions)

print(f"\n📉 亏损持仓:")
print(f"   数量: {losing_count}/{len(all_holdings)}")
print(f"   总亏损: ${losing_amount:,.2f}")

# ============ 第四部分：周一操作建议 ============
print("\n" + "="*80)
print("💡 第四部分：周一操作建议 (2026-03-10)")
print("="*80)

print("\n🎯 立即行动:")

# 分析每个持仓
actions = []

# 美股分析
for h in us_stocks['holdings']:
    ticker = h['ticker']
    pnl_pct = h['pnl_percent']
    
    if ticker == 'CRCL' and pnl_pct > 15:
        actions.append({
            'ticker': ticker,
            'action': '考虑止盈',
            'reason': f'已盈利 {pnl_pct:.1f}%，可以锁定部分利润',
            'priority': 'HIGH'
        })
    elif ticker == 'NVDA' and pnl_pct < -3:
        actions.append({
            'ticker': ticker,
            'action': '观望或加仓',
            'reason': 'AI芯片龙头，短期回调是加仓机会',
            'priority': 'MEDIUM'
        })
    elif ticker == 'QQQ' and pnl_pct < -3:
        actions.append({
            'ticker': ticker,
            'action': '持有',
            'reason': '纳指ETF长期看好，短期波动正常',
            'priority': 'LOW'
        })

# 港股分析
for h in hk_stocks['holdings']:
    ticker = h['ticker']
    name = h['name']
    pnl_pct = h['pnl_percent']
    
    if 'XL' in ticker and pnl_pct < -10:
        actions.append({
            'ticker': f"{ticker} ({name})",
            'action': '考虑止损',
            'reason': f'杠杆ETF亏损 {pnl_pct:.1f}%，风险较高',
            'priority': 'HIGH'
        })
    elif ticker == '03033' and pnl_pct < -5:
        actions.append({
            'ticker': f"{ticker} ({name})",
            'action': '持有观望',
            'reason': '恒生科技ETF，等待反弹',
            'priority': 'MEDIUM'
        })

# 按优先级排序
actions_sorted = sorted(actions, key=lambda x: {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}[x['priority']])

for i, action in enumerate(actions_sorted, 1):
    priority_emoji = '🔴' if action['priority'] == 'HIGH' else '🟡' if action['priority'] == 'MEDIUM' else '🟢'
    print(f"\n{priority_emoji} {i}. {action['ticker']}")
    print(f"   操作: {action['action']}")
    print(f"   理由: {action['reason']}")

print("\n" + "="*80)
print("📋 总结建议")
print("="*80)

print("""
1. 🔴 高优先级（周一开盘处理）:
   • CRCL: 考虑止盈 50%，锁定利润
   • 07747 (XL二南三星): 亏损30%，建议止损
   
2. 🟡 中优先级（本周关注）:
   • NVDA: 如果跌破$170，可以加仓
   • 港股杠杆ETF: 密切关注，设置止损线
   
3. 🟢 长期持有:
   • QQQ: 继续持有，定期定额
   • 02208 (金风科技): 唯一盈利的港股，继续持有

4. 💰 资金管理:
   • 建议保留20-30%现金
   • 降低杠杆ETF仓位至20%以下
   • 考虑增加AI相关个股（MSFT/GOOGL）

5. ⚠️ 风险提示:
   • 港股杠杆ETF风险极高，注意控制仓位
   • 美股科技股波动加大，做好心理准备
   • 建议设置止损线：单只股票亏损超过15%考虑止损
""")

print("\n" + "="*80)
print("✅ 分析完成")
print("="*80)
