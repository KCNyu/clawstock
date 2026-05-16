#!/usr/bin/env python3
"""
持仓可视化工具 - 修复字体版本
"""

import json
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib import rcParams
import numpy as np
from datetime import datetime

# 清除字体缓存并重新加载
import matplotlib

# 查找并设置中文字体
chinese_fonts = []
for font in fm.fontManager.ttflist:
    if 'CJK' in font.name or 'WenQuanYi' in font.name or 'Noto' in font.name:
        chinese_fonts.append(font.name)

print(f"找到的中文字体: {chinese_fonts[:5]}")

# 设置字体 - 使用 Noto Sans CJK SC
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'Noto Sans CJK TC', 'WenQuanYi Zen Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10

# 读取持仓数据
with open('portfolio.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

us_stocks = data['portfolios']['us_stocks']
hk_stocks = data['portfolios']['hk_stocks']

# 创建大图表
fig = plt.figure(figsize=(16, 12))
fig.suptitle(f'📊 {data["owner"]} 的投资组合 | 更新时间: {data["last_updated"]}', 
             fontsize=20, fontweight='bold', y=0.98)

# ============ 1. 美股持仓饼图 ============
ax1 = plt.subplot(2, 3, 1)
us_tickers = [h['ticker'] for h in us_stocks['holdings']]
us_values = [h['shares'] * h['current_price'] for h in us_stocks['holdings']]
colors1 = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
explode = [0.05 if i == us_values.index(max(us_values)) else 0 for i in range(len(us_values))]

wedges, texts, autotexts = ax1.pie(us_values, labels=us_tickers, autopct='%1.1f%%',
                                     colors=colors1, explode=explode, startangle=90)
for autotext in autotexts:
    autotext.set_color('white')
    autotext.set_fontweight('bold')
ax1.set_title('美股持仓分布 (USD)', fontsize=14, fontweight='bold', pad=20)

# ============ 2. 港股持仓饼图 ============
ax2 = plt.subplot(2, 3, 2)
hk_labels = [f"{h['ticker']}\n{h['name']}" for h in hk_stocks['holdings']]
hk_values = [h['current_value'] for h in hk_stocks['holdings']]
colors2 = ['#95E1D3', '#F38181', '#AA96DA', '#FCBAD3', '#FFFFD2']
explode2 = [0.05 if i == hk_values.index(max(hk_values)) else 0 for i in range(len(hk_values))]

wedges2, texts2, autotexts2 = ax2.pie(hk_values, labels=hk_labels, autopct='%1.1f%%',
                                        colors=colors2, explode=explode2, startangle=90)
for autotext in autotexts2:
    autotext.set_color('white')
    autotext.set_fontweight('bold')
    autotext.set_fontsize(9)
ax2.set_title('港股持仓分布 (HKD)', fontsize=14, fontweight='bold', pad=20)

# ============ 3. 美股盈亏柱状图 ============
ax3 = plt.subplot(2, 3, 4)
us_pnl = [h['pnl_percent'] for h in us_stocks['holdings']]
colors_pnl = ['#2ECC71' if x > 0 else '#E74C3C' for x in us_pnl]
bars = ax3.bar(us_tickers, us_pnl, color=colors_pnl, alpha=0.8, edgecolor='black', linewidth=1.5)

# 添加数值标签
for bar, pnl in zip(bars, us_pnl):
    height = bar.get_height()
    ax3.text(bar.get_x() + bar.get_width()/2., height,
             f'{pnl:+.2f}%',
             ha='center', va='bottom' if height > 0 else 'top',
             fontweight='bold', fontsize=10)

ax3.axhline(y=0, color='black', linestyle='-', linewidth=1)
ax3.set_ylabel('盈亏 (%)', fontsize=12, fontweight='bold')
ax3.set_title('美股盈亏情况', fontsize=14, fontweight='bold', pad=20)
ax3.grid(axis='y', alpha=0.3, linestyle='--')

# ============ 4. 港股盈亏柱状图 ============
ax4 = plt.subplot(2, 3, 5)
hk_tickers = [h['ticker'] for h in hk_stocks['holdings']]
hk_pnl = [h['pnl_percent'] for h in hk_stocks['holdings']]
colors_pnl2 = ['#2ECC71' if x > 0 else '#E74C3C' for x in hk_pnl]
bars2 = ax4.bar(hk_tickers, hk_pnl, color=colors_pnl2, alpha=0.8, edgecolor='black', linewidth=1.5)

# 添加数值标签
for bar, pnl in zip(bars2, hk_pnl):
    height = bar.get_height()
    ax4.text(bar.get_x() + bar.get_width()/2., height,
             f'{pnl:+.2f}%',
             ha='center', va='bottom' if height > 0 else 'top',
             fontweight='bold', fontsize=9)

ax4.axhline(y=0, color='black', linestyle='-', linewidth=1)
ax4.set_ylabel('盈亏 (%)', fontsize=12, fontweight='bold')
ax4.set_title('港股盈亏情况', fontsize=14, fontweight='bold', pad=20)
ax4.grid(axis='y', alpha=0.3, linestyle='--')
plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right')

# ============ 5. 总体概览 ============
ax5 = plt.subplot(2, 3, 3)
ax5.axis('off')

# 美股总览
us_total_cost = us_stocks['total_cost']
us_total_value = us_stocks['total_current_value']
us_total_pnl = us_stocks['total_pnl']
us_total_pnl_pct = us_stocks['total_pnl_percent']

# 港股总览
hk_total_cost = hk_stocks['total_cost']
hk_total_value = hk_stocks['total_current_value']
hk_total_pnl = hk_stocks['total_pnl']
hk_total_pnl_pct = hk_stocks['total_pnl_percent']

summary_text = f"""
━━━━━━━━━━━━━━━━━━━━━━
        总体概览
━━━━━━━━━━━━━━━━━━━━━━

🇺🇸 美股账户 (USD)
   成本: ${us_total_cost:,.2f}
   市值: ${us_total_value:,.2f}
   盈亏: ${us_total_pnl:+,.2f} ({us_total_pnl_pct:+.2f}%)

🇭🇰 港股账户 (HKD)
   成本: HK${hk_total_cost:,.2f}
   市值: HK${hk_total_value:,.2f}
   盈亏: HK${hk_total_pnl:+,.2f} ({hk_total_pnl_pct:+.2f}%)

━━━━━━━━━━━━━━━━━━━━━━
"""

ax5.text(0.5, 0.5, summary_text, 
         ha='center', va='center',
         fontsize=11,
         bbox=dict(boxstyle='round,pad=1', facecolor='#F8F9FA', edgecolor='#DEE2E6', linewidth=2))

# ============ 6. 持仓市值对比 ============
ax6 = plt.subplot(2, 3, 6)

# 转换港股为美元（假设汇率 1 USD = 7.8 HKD）
exchange_rate = 7.8
hk_value_usd = hk_total_value / exchange_rate

categories = ['美股\n(USD)', '港股\n(折合USD)']
values = [us_total_value, hk_value_usd]
colors_compare = ['#3498DB', '#E67E22']

bars_compare = ax6.bar(categories, values, color=colors_compare, alpha=0.8, 
                       edgecolor='black', linewidth=2, width=0.6)

# 添加数值标签
for bar, val in zip(bars_compare, values):
    height = bar.get_height()
    ax6.text(bar.get_x() + bar.get_width()/2., height,
             f'${val:,.0f}',
             ha='center', va='bottom',
             fontweight='bold', fontsize=12)

ax6.set_ylabel('市值 (USD)', fontsize=12, fontweight='bold')
ax6.set_title('持仓市值对比 (汇率: 1 USD = 7.8 HKD)', fontsize=14, fontweight='bold', pad=20)
ax6.grid(axis='y', alpha=0.3, linestyle='--')

# 调整布局
plt.tight_layout(rect=[0, 0, 1, 0.96])

# 保存图片
output_file = 'portfolio_visualization.png'
plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white')
print(f"✅ 图表已生成: {output_file}")

plt.close()
