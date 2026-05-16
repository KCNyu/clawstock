#!/usr/bin/env python3
"""
简单持仓表格可视化 - 带盈亏金额
"""

import json
import matplotlib.pyplot as plt

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 读取数据
with open('portfolio.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

us_stocks = data['portfolios']['us_stocks']
hk_stocks = data['portfolios']['hk_stocks']

# 创建图表
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
fig.suptitle(f'{data["owner"]} 的投资组合', fontsize=18, fontweight='bold', y=0.98)

# ========== 美股表格 ==========
ax1.axis('tight')
ax1.axis('off')

us_table_data = []
us_table_data.append(['股票代码', '股数', '成本价', '当前价', '市值', '盈亏金额', '盈亏%'])

for h in us_stocks['holdings']:
    ticker = h['ticker']
    shares = h['shares']
    cost = f"${h['cost_basis']:.2f}"
    current = f"${h['current_price']:.2f}"
    value = f"${h['shares'] * h['current_price']:.2f}"
    
    # 计算盈亏金额
    pnl_amount = (h['current_price'] - h['cost_basis']) * h['shares']
    pnl_amount_str = f"${pnl_amount:+.2f}"
    
    pnl_pct = f"{h['pnl_percent']:+.2f}%"
    us_table_data.append([ticker, shares, cost, current, value, pnl_amount_str, pnl_pct])

# 添加总计行
us_table_data.append(['', '', '', '', '总计', 
                      f"${us_stocks['total_pnl']:+.2f}",
                      f"{us_stocks['total_pnl_percent']:+.2f}%"])

# 创建表格
table1 = ax1.table(cellText=us_table_data, cellLoc='center', loc='center',
                   colWidths=[0.12, 0.08, 0.13, 0.13, 0.15, 0.15, 0.12])

table1.auto_set_font_size(False)
table1.set_fontsize(10)
table1.scale(1, 2.5)

# 设置表头样式
for i in range(7):
    cell = table1[(0, i)]
    cell.set_facecolor('#4A90E2')
    cell.set_text_props(weight='bold', color='white')

# 设置盈亏列颜色
for i in range(1, len(us_table_data)):
    # 盈亏金额列
    pnl_amount_text = us_table_data[i][5]
    cell_amount = table1[(i, 5)]
    if '+' in pnl_amount_text:
        cell_amount.set_facecolor('#D4EDDA')
        cell_amount.set_text_props(color='#155724', weight='bold')
    elif '-' in pnl_amount_text:
        cell_amount.set_facecolor('#F8D7DA')
        cell_amount.set_text_props(color='#721C24', weight='bold')
    
    # 盈亏百分比列
    pnl_pct_text = us_table_data[i][6]
    cell_pct = table1[(i, 6)]
    if '+' in pnl_pct_text:
        cell_pct.set_facecolor('#D4EDDA')
        cell_pct.set_text_props(color='#155724', weight='bold')
    elif '-' in pnl_pct_text:
        cell_pct.set_facecolor('#F8D7DA')
        cell_pct.set_text_props(color='#721C24', weight='bold')

# 设置总计行样式
last_row = len(us_table_data) - 1
for i in range(7):
    cell = table1[(last_row, i)]
    cell.set_facecolor('#F0F0F0')
    cell.set_text_props(weight='bold')

ax1.set_title('美股持仓 (USD)', fontsize=14, fontweight='bold', pad=20, loc='left')

# ========== 港股表格 ==========
ax2.axis('tight')
ax2.axis('off')

hk_table_data = []
hk_table_data.append(['代码', '名称', '股数', '成本价', '当前价', '市值', '盈亏金额', '盈亏%'])

for h in hk_stocks['holdings']:
    ticker = h['ticker']
    name = h['name']
    shares = h['shares']
    cost = f"HK${h['cost_basis']:.2f}"
    current = f"HK${h['current_price']:.2f}"
    value = f"HK${h['current_value']:.2f}"
    
    # 计算盈亏金额
    pnl_amount = (h['current_price'] - h['cost_basis']) * h['shares']
    pnl_amount_str = f"HK${pnl_amount:+.2f}"
    
    pnl_pct = f"{h['pnl_percent']:+.2f}%"
    hk_table_data.append([ticker, name, shares, cost, current, value, pnl_amount_str, pnl_pct])

# 计算正确的总计
hk_total_cost_calc = sum(h['cost_basis'] * h['shares'] for h in hk_stocks['holdings'])
hk_total_value_calc = sum(h['current_value'] for h in hk_stocks['holdings'])
hk_total_pnl_calc = hk_total_value_calc - hk_total_cost_calc
hk_total_pnl_pct_calc = (hk_total_pnl_calc / hk_total_cost_calc) * 100

# 添加总计行
hk_table_data.append(['', '', '', '', '', '总计',
                      f"HK${hk_total_pnl_calc:+.2f}",
                      f"{hk_total_pnl_pct_calc:+.2f}%"])

# 创建表格
table2 = ax2.table(cellText=hk_table_data, cellLoc='center', loc='center',
                   colWidths=[0.08, 0.18, 0.08, 0.12, 0.12, 0.15, 0.15, 0.1])

table2.auto_set_font_size(False)
table2.set_fontsize(9)
table2.scale(1, 2.5)

# 设置表头样式
for i in range(8):
    cell = table2[(0, i)]
    cell.set_facecolor('#E67E22')
    cell.set_text_props(weight='bold', color='white')

# 设置盈亏列颜色
for i in range(1, len(hk_table_data)):
    # 盈亏金额列
    pnl_amount_text = hk_table_data[i][6]
    cell_amount = table2[(i, 6)]
    if '+' in pnl_amount_text:
        cell_amount.set_facecolor('#D4EDDA')
        cell_amount.set_text_props(color='#155724', weight='bold')
    elif '-' in pnl_amount_text:
        cell_amount.set_facecolor('#F8D7DA')
        cell_amount.set_text_props(color='#721C24', weight='bold')
    
    # 盈亏百分比列
    pnl_pct_text = hk_table_data[i][7]
    cell_pct = table2[(i, 7)]
    if '+' in pnl_pct_text:
        cell_pct.set_facecolor('#D4EDDA')
        cell_pct.set_text_props(color='#155724', weight='bold')
    elif '-' in pnl_pct_text:
        cell_pct.set_facecolor('#F8D7DA')
        cell_pct.set_text_props(color='#721C24', weight='bold')

# 设置总计行样式
last_row = len(hk_table_data) - 1
for i in range(8):
    cell = table2[(last_row, i)]
    cell.set_facecolor('#F0F0F0')
    cell.set_text_props(weight='bold')

ax2.set_title('港股持仓 (HKD)', fontsize=14, fontweight='bold', pad=20, loc='left')

plt.tight_layout()
plt.savefig('portfolio_table.png', dpi=150, bbox_inches='tight', facecolor='white')
print("✅ 表格已生成: portfolio_table.png")
plt.close()
