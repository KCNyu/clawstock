const fs = require('fs');
const p = '/root/.openclaw/workspace/portfolio.json';
const data = JSON.parse(fs.readFileSync(p, 'utf8'));
const quotes = {
  NVDA:{c:177.50,dp:0.062,h:177.79,l:175.76,o:177.155,pc:177.39},
  RKLB:{c:67.695,dp:-0.0517,h:70.32,l:66.60,o:67.73,pc:67.73},
  CRCL:{c:92.28,dp:2.238,h:94.6982,l:91.02,o:93.09,pc:90.26},
  OKLO:{c:48.805,dp:1.4025,h:49.85,l:47.98,o:48.10,pc:48.13},
  QQQ:{c:588.43,dp:0.5898,h:590.61,l:584.69,o:586.23,pc:584.98},
  TCOM:{c:50.07,dp:-0.8122,h:50.74,l:49.94,o:50.01,pc:50.48},
  TQQQ:{c:44.09,dp:1.754,h:44.585,l:43.27,o:43.60,pc:43.33},
  HOOD:{c:69.77,dp:1.2627,h:70.82,l:68.71,o:69.31,pc:68.90}
};
const us = data.portfolios.us_stocks;
let totalValue = 0, totalCost = 0, totalPnl = 0, todayChange = 0;
for (const h of us.holdings) {
  const q = quotes[h.ticker];
  if (!q) continue;
  h.current_price = q.c;
  h.today_change_pct = q.dp;
  h.day_high = q.h;
  h.day_low = q.l;
  h.day_open = q.o;
  h.prev_close = q.pc;
  h.current_value = +(h.shares * q.c).toFixed(2);
  h.pnl_abs = +((q.c - h.cost_basis) * h.shares).toFixed(2);
  h.pnl_percent = ((q.c - h.cost_basis) / h.cost_basis) * 100;
  h.today_change = +((q.c - q.pc) * h.shares).toFixed(2);
  h.data_source = 'finnhub-2026-04-06 close ET (Eastmoney 302 delay redirect/unavailable)';
  totalValue += h.current_value;
  totalCost += h.cost_basis * h.shares;
  totalPnl += h.pnl_abs;
  todayChange += h.today_change;
}
us.total_cost = +totalCost.toFixed(2);
us.total_current_value = +totalValue.toFixed(2);
us.total_pnl = +totalPnl.toFixed(2);
us.total_pnl_percent = +(totalPnl / totalCost * 100).toFixed(6);
us.today_total_change = +todayChange.toFixed(2);
us.last_updated = '2026-04-06 16:00 ET';
data.last_updated = '2026-04-07 04:00:00 HKT';
fs.writeFileSync(p, JSON.stringify(data, null, 2) + '\n');
console.log(JSON.stringify({ totalValue, totalCost, totalPnl, todayChange }, null, 2));
