import json
from decimal import Decimal, ROUND_HALF_UP

path = '/root/.openclaw/workspace/portfolio.json'
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

quotes = {
    '02208': {'price': 13.58, 'pct': -3.55, 'change': -0.50, 'open': 14.26, 'high': 14.39, 'low': 13.50, 'prev': 14.08, 'source': 'eastmoney-delay-2026-04-07 09:30 HKT'},
    '03032': {'price': 4.646, 'pct': -1.73, 'change': -0.082, 'open': 4.706, 'high': 4.716, 'low': 4.608, 'prev': 4.728, 'source': 'eastmoney-delay-2026-04-07 09:30 HKT'},
    '07226': {'price': 3.51, 'pct': -3.31, 'change': -0.12, 'open': 3.598, 'high': 3.61, 'low': 3.446, 'prev': 3.63, 'source': 'eastmoney-delay-2026-04-07 09:30 HKT'},
    '07709': {'price': 21.24, 'pct': -11.50, 'change': -2.76, 'open': 23.2, 'high': 23.2, 'low': 20.1, 'prev': 24.0, 'source': 'eastmoney-delay-2026-04-07 09:30 HKT'},
    '07747': {'price': 62.7, 'pct': -9.31, 'change': -6.44, 'open': 69.42, 'high': 69.42, 'low': 59.44, 'prev': 69.14, 'source': 'eastmoney-delay-2026-04-07 09:30 HKT'},
    '03033': {'price': 4.57, 'pct': -1.64, 'change': -0.076, 'open': 4.624, 'high': 4.634, 'low': 4.526, 'prev': 4.646, 'source': 'eastmoney-delay-2026-04-07 09:30 HKT'},
}

def r2(x):
    return float(Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

hk = data['portfolios']['hk_stocks']
total_cost = 0.0
total_value = 0.0
total_pnl = 0.0
today_total_change = 0.0
for h in hk['holdings']:
    q = quotes.get(h['ticker'])
    if not q:
        continue
    shares = h['shares']
    cost = h['cost_basis']
    current_value = q['price'] * shares
    pnl_abs = current_value - cost * shares
    pnl_pct = (pnl_abs / (cost * shares)) * 100 if cost and shares else 0
    today_change = q['change'] * shares
    h['current_price'] = q['price']
    h['current_value'] = r2(current_value)
    h['pnl_abs'] = r2(pnl_abs)
    h['pnl_percent'] = r2(pnl_pct)
    h['today_change'] = r2(today_change)
    h['today_change_pct'] = q['pct']
    h['day_open'] = q['open']
    h['day_high'] = q['high']
    h['day_low'] = q['low']
    h['prev_close'] = q['prev']
    h['data_source'] = q['source']
    total_cost += cost * shares
    total_value += current_value
    total_pnl += pnl_abs
    today_total_change += today_change

hk['total_cost'] = r2(total_cost)
hk['total_current_value'] = r2(total_value)
hk['total_pnl'] = r2(total_pnl)
hk['total_pnl_percent'] = r2((total_pnl / total_cost) * 100 if total_cost else 0)
hk['today_total_change'] = r2(today_total_change)
hk['last_updated'] = '2026-04-07 09:30:00 HKT'

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write('\n')
