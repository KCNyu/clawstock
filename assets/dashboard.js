/* clawstock dashboard — fetches data + renders ECharts */

const DATA_URL = 'assets/data/dashboard.json';
const CHART_BG = '#131c2e';
const COLORS = {
  green: '#4ade80', red: '#ef4444', yellow: '#facc15', accent: '#4fa8ff',
  orange: '#fb923c', muted: '#8893b3', text: '#e8eaf2',
  treemap: ['#1e3a8a','#1e40af','#1d4ed8','#2563eb','#3b82f6','#4fa8ff','#60a5fa','#93c5fd'],
};

const fmt = {
  money(v, cur='') {
    if (v == null || isNaN(v)) return '—';
    const sign = v < 0 ? '-' : '';
    const abs = Math.abs(v);
    const s = abs >= 10000 ? abs.toFixed(0) : abs.toFixed(abs >= 100 ? 1 : 2);
    return `${sign}${cur}${Number(s).toLocaleString('en-US')}`;
  },
  pct(v) {
    if (v == null || isNaN(v)) return '—';
    return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
  },
  num(v, dp=2) {
    if (v == null || isNaN(v)) return '—';
    return Number(v.toFixed(dp)).toLocaleString('en-US');
  },
  pctSpan(v) {
    if (v == null || isNaN(v)) return '<span class="muted">—</span>';
    const cls = v >= 0 ? 'pos' : 'neg';
    return `<span class="${cls}">${fmt.pct(v)}</span>`;
  },
  moneySpan(v, cur) {
    if (v == null || isNaN(v)) return '<span class="muted">—</span>';
    const cls = v >= 0 ? 'pos' : 'neg';
    return `<span class="${cls}">${fmt.money(v, cur)}</span>`;
  },
  date(s) { return s ? s.split('T')[0] : '—'; },
};

let DATA = null;
let HOLDINGS = [];
let sortBy = { col: 'current_value', dir: 'desc' };
let chartRegistry = {};

async function loadData() {
  const r = await fetch(DATA_URL, { cache: 'no-store' });
  if (!r.ok) throw new Error('Failed to load ' + DATA_URL);
  return await r.json();
}

function renderHero(d) {
  const fx = d.fx.usdhkd || 0;
  const usVal = d.totals.us.value_usd || 0;
  const hkVal = d.totals.hk.value_hkd || 0;
  const bookUsd = usVal + (fx ? hkVal / fx : 0);
  const bookHkd = hkVal + usVal * fx;
  document.getElementById('hero-book').innerHTML =
    `$${fmt.num(bookUsd, 0)} <small class="muted">≈ HK$${fmt.num(bookHkd, 0)}</small>`;

  const todayUsd = (d.totals.us.today_change_usd || 0) + (fx ? (d.totals.hk.today_change_hkd || 0) / fx : 0);
  document.getElementById('hero-today').innerHTML = fmt.moneySpan(todayUsd, '$');

  document.getElementById('hero-fx').textContent = fx ? fx.toFixed(4) : '—';
  document.getElementById('hero-updated').textContent = fmt.date(d.last_updated);
  document.getElementById('footer-gen').textContent = fmt.date(d.generated_at);
}

function renderLegSummary(legId, totals, conc, currency) {
  const $ = document.getElementById(legId + '-summary');
  $.innerHTML = `
    <div class="stat"><span class="l">Value</span><span class="v">${currency}${fmt.num(totals.value_usd ?? totals.value_hkd, 0)}</span></div>
    <div class="stat"><span class="l">P&L</span><span class="v ${(totals.pnl_usd ?? totals.pnl_hkd) >= 0 ? 'pos' : 'neg'}">${currency}${fmt.num(totals.pnl_usd ?? totals.pnl_hkd, 0)} (${fmt.pct(totals.pnl_pct)})</span></div>
    <div class="stat"><span class="l">Today</span><span class="v ${(totals.today_change_usd ?? totals.today_change_hkd) >= 0 ? 'pos' : 'neg'}">${currency}${fmt.num(totals.today_change_usd ?? totals.today_change_hkd, 0)}</span></div>
  `;
}

function renderTreemap(elId, conc, currencySymbol) {
  const chart = echarts.init(document.getElementById(elId), null, { renderer: 'canvas' });
  chartRegistry[elId] = chart;
  const positions = conc.positions.map((p, i) => ({
    name: p.ticker + (p.name ? `\n${p.name}` : ''),
    value: p.value,
    weight: p.weight,
    itemStyle: { color: COLORS.treemap[i % COLORS.treemap.length] },
  }));
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: '#1a2540',
      borderColor: '#243150',
      textStyle: { color: '#e8eaf2' },
      formatter: (p) => `<b>${p.data.name}</b><br/>Value: ${currencySymbol}${fmt.num(p.data.value, 0)}<br/>Weight: ${(p.data.weight*100).toFixed(2)}%`,
    },
    series: [{
      type: 'treemap',
      data: positions,
      roam: false,
      breadcrumb: { show: false },
      label: {
        show: true,
        formatter: (p) => `${p.name.split('\n')[0]}\n${(p.data.weight*100).toFixed(1)}%`,
        color: '#fff',
        fontSize: 12,
      },
      upperLabel: { show: false },
      itemStyle: { borderColor: '#0b1220', borderWidth: 2, gap: 2 },
    }],
  });
}

function renderHHIGauge(d) {
  const el = document.getElementById('chart-hhi-gauge');
  const chart = echarts.init(el, null, { renderer: 'canvas' });
  chartRegistry['chart-hhi-gauge'] = chart;
  const usHhi = d.concentration.us.hhi || 0;
  const hkHhi = d.concentration.hk.hhi || 0;

  chart.setOption({
    backgroundColor: 'transparent',
    series: [
      {
        name: 'US HHI',
        type: 'gauge',
        center: ['30%', '60%'],
        radius: '90%',
        min: 0, max: 0.6,
        progress: { show: true, width: 14 },
        axisLine: { lineStyle: { width: 14, color: [[0.25,COLORS.green],[0.42,COLORS.yellow],[0.67,COLORS.orange],[1,COLORS.red]] } },
        axisTick: { show: false },
        splitLine: { length: 8, lineStyle: { color: '#fff' } },
        axisLabel: { color: COLORS.muted, fontSize: 10, distance: -28 },
        pointer: { length: '70%', width: 4 },
        anchor: { show: false },
        title: { offsetCenter: [0, '20%'], color: COLORS.muted, fontSize: 13 },
        detail: { offsetCenter: [0, '0%'], color: COLORS.text, fontSize: 22, formatter: v => v.toFixed(3) },
        data: [{ value: usHhi, name: 'US HHI' }],
      },
      {
        name: 'HK HHI',
        type: 'gauge',
        center: ['70%', '60%'],
        radius: '90%',
        min: 0, max: 0.6,
        progress: { show: true, width: 14 },
        axisLine: { lineStyle: { width: 14, color: [[0.25,COLORS.green],[0.42,COLORS.yellow],[0.67,COLORS.orange],[1,COLORS.red]] } },
        axisTick: { show: false },
        splitLine: { length: 8, lineStyle: { color: '#fff' } },
        axisLabel: { color: COLORS.muted, fontSize: 10, distance: -28 },
        pointer: { length: '70%', width: 4 },
        anchor: { show: false },
        title: { offsetCenter: [0, '20%'], color: COLORS.muted, fontSize: 13 },
        detail: { offsetCenter: [0, '0%'], color: COLORS.text, fontSize: 22, formatter: v => v.toFixed(3) },
        data: [{ value: hkHhi, name: 'HK HHI' }],
      },
    ],
  });
}

function renderMovers(d) {
  const el = document.getElementById('chart-movers');
  const chart = echarts.init(el, null, { renderer: 'canvas' });
  chartRegistry['chart-movers'] = chart;
  const all = [...d.holdings.us, ...d.holdings.hk]
    .filter(h => h.is_active && Math.abs(h.today_change_pct) >= 1.5)
    .sort((a, b) => b.today_change_pct - a.today_change_pct);

  if (all.length === 0) {
    el.innerHTML = '<p class="muted" style="text-align:center;padding:60px 0">今日无 ≥1.5% 异动</p>';
    return;
  }
  const items = all.map(h => ({
    name: `${h.ticker}${h.name ? ' '+h.name : ''}`,
    value: h.today_change_pct,
    itemStyle: { color: h.today_change_pct >= 0 ? COLORS.green : COLORS.red },
  }));

  chart.setOption({
    backgroundColor: 'transparent',
    grid: { top: 20, left: 130, right: 50, bottom: 20 },
    xAxis: { type: 'value', axisLabel: { color: COLORS.muted, formatter: '{value}%' }, splitLine: { lineStyle: { color: '#243150' } } },
    yAxis: { type: 'category', data: items.map(i => i.name), axisLabel: { color: COLORS.text, fontSize: 11 } },
    tooltip: { backgroundColor: '#1a2540', borderColor: '#243150', textStyle: { color: '#e8eaf2' } },
    series: [{
      type: 'bar',
      data: items,
      label: { show: true, position: 'right', color: COLORS.text, formatter: p => fmt.pct(p.value) },
      barMaxWidth: 18,
    }],
  });
}

function renderHoldingsTable() {
  const tbody = document.querySelector('#holdings-table tbody');
  const filterActive = document.getElementById('filter-active').checked;
  const filterMarket = document.getElementById('filter-market').value;
  let rows = HOLDINGS.slice();
  if (filterActive) rows = rows.filter(h => h.is_active);
  if (filterMarket === 'us') rows = rows.filter(h => h.currency === 'USD');
  if (filterMarket === 'hk') rows = rows.filter(h => h.currency === 'HKD');

  rows.sort((a, b) => {
    const av = a[sortBy.col]; const bv = b[sortBy.col];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === 'string') return sortBy.dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
    return sortBy.dir === 'asc' ? av - bv : bv - av;
  });

  document.getElementById('holdings-count').textContent = `${rows.length} positions`;
  tbody.innerHTML = rows.map(h => {
    const cur = h.currency === 'USD' ? '$' : 'HK$';
    return `<tr class="${h.is_active ? '' : 'inactive'}">
      <td><b>${h.ticker}</b></td>
      <td>${h.name || ''}</td>
      <td>${h.currency}</td>
      <td class="num">${fmt.num(h.shares, 0)}</td>
      <td class="num">${cur}${fmt.num(h.cost_basis)}</td>
      <td class="num">${cur}${fmt.num(h.current_price)}</td>
      <td class="num">${fmt.pctSpan(h.today_change_pct)}</td>
      <td class="num">${fmt.pctSpan(h.pnl_percent)}</td>
      <td class="num">${fmt.moneySpan(h.pnl_abs, cur)}</td>
      <td class="num">${cur}${fmt.num(h.current_value, 0)}</td>
    </tr>`;
  }).join('');

  document.querySelectorAll('.holdings-table th').forEach(th => {
    th.classList.remove('sorted-asc', 'sorted-desc');
    if (th.dataset.sort === sortBy.col) th.classList.add('sorted-' + sortBy.dir);
  });
}

function renderConcDetail(legId, conc) {
  const el = document.getElementById(legId);
  const verdict = conc.verdict;
  el.innerHTML = `
    <div class="top-row">
      <span>HHI</span>
      <span><b>${conc.hhi.toFixed(4)}</b> <span class="badge ${verdict.level}">${verdict.label}</span></span>
    </div>
    <div class="top-row">
      <span>Top 2</span>
      <span><b>${(conc.top2*100).toFixed(1)}%</b></span>
    </div>
    <div class="top-row">
      <span>Total Value</span>
      <span><b>${fmt.num(conc.total, 0)}</b></span>
    </div>
    <h4 style="margin-top:16px">Position Weights</h4>
    ${conc.positions.map(p => `
      <div class="conc-row">
        <div class="top-row" style="border:none;padding:4px 0">
          <span class="ticker">${p.ticker} <span class="muted" style="font-weight:normal">${p.name || ''}</span></span>
          <span class="weight">${(p.weight*100).toFixed(2)}%</span>
        </div>
        <div class="bar"><div class="bar-fill" style="width:${(p.weight*100).toFixed(1)}%"></div></div>
      </div>
    `).join('')}
  `;
}

function renderHistory(d) {
  const snaps = d.snapshots || [];
  const elV = document.getElementById('chart-history-value');
  const elP = document.getElementById('chart-history-pnl');
  if (snaps.length === 0) {
    elV.innerHTML = '<p class="muted" style="text-align:center;padding:120px 0">尚无 snapshot 数据（snapshots/{date}.json 每日 08:00 写入）</p>';
    elP.innerHTML = '<p class="muted" style="text-align:center;padding:90px 0">尚无 P&L 数据</p>';
    return;
  }

  const dates = snaps.map(s => s.date);
  const usVals = snaps.map(s => s.us_total_value || 0);
  const hkVals = snaps.map(s => s.hk_total_value || 0);
  const usPnl = snaps.map(s => s.us_today_change || 0);
  const hkPnl = snaps.map(s => s.hk_today_change || 0);

  const chartV = echarts.init(elV, null, { renderer: 'canvas' });
  chartRegistry['chart-history-value'] = chartV;
  chartV.setOption({
    backgroundColor: 'transparent',
    legend: { data: ['US (USD)', 'HK (HKD)'], textStyle: { color: COLORS.text } },
    tooltip: { trigger: 'axis', backgroundColor: '#1a2540', borderColor: '#243150', textStyle: { color: '#e8eaf2' } },
    grid: { top: 50, left: 70, right: 30, bottom: 50 },
    xAxis: { type: 'category', data: dates, axisLabel: { color: COLORS.muted } },
    yAxis: [
      { type: 'value', name: 'USD', position: 'left', axisLabel: { color: COLORS.muted }, splitLine: { lineStyle: { color: '#243150' } } },
      { type: 'value', name: 'HKD', position: 'right', axisLabel: { color: COLORS.muted } },
    ],
    series: [
      { name: 'US (USD)', type: 'line', data: usVals, smooth: true, itemStyle: { color: COLORS.accent }, yAxisIndex: 0 },
      { name: 'HK (HKD)', type: 'line', data: hkVals, smooth: true, itemStyle: { color: COLORS.orange }, yAxisIndex: 1 },
    ],
  });

  const chartP = echarts.init(elP, null, { renderer: 'canvas' });
  chartRegistry['chart-history-pnl'] = chartP;
  chartP.setOption({
    backgroundColor: 'transparent',
    legend: { data: ['US (USD)', 'HK (HKD)'], textStyle: { color: COLORS.text } },
    tooltip: { trigger: 'axis', backgroundColor: '#1a2540', borderColor: '#243150', textStyle: { color: '#e8eaf2' } },
    grid: { top: 50, left: 70, right: 30, bottom: 50 },
    xAxis: { type: 'category', data: dates, axisLabel: { color: COLORS.muted } },
    yAxis: { type: 'value', axisLabel: { color: COLORS.muted }, splitLine: { lineStyle: { color: '#243150' } } },
    series: [
      { name: 'US (USD)', type: 'bar', data: usPnl, itemStyle: { color: p => p.value >= 0 ? COLORS.green : COLORS.red } },
      { name: 'HK (HKD)', type: 'bar', data: hkPnl, itemStyle: { color: p => p.value >= 0 ? '#22c55e' : '#dc2626' } },
    ],
  });
}

function renderPlans(d) {
  const el = document.getElementById('plans-list');
  const plans = d.recent_plans || [];
  if (plans.length === 0) {
    el.innerHTML = '<p class="muted">尚无 daily plan 数据。</p>';
    return;
  }
  el.innerHTML = plans.reverse().map((p, idx) => {
    const summary = p.plan.summary || p.plan.tldr || '';
    const actions = (p.plan.actions || p.plan.plan || []);
    const retro = p.plan.retrospective;
    return `<div class="plan-card" data-idx="${idx}">
      <div class="plan-head">
        <span class="plan-title">${p.date}</span>
        <span class="plan-date muted">${actions.length} actions${retro ? ' · has retrospective' : ''}</span>
      </div>
      <pre>${escapeHtml(JSON.stringify(p.plan, null, 2))}</pre>
    </div>`;
  }).join('');

  el.querySelectorAll('.plan-card').forEach(card => {
    card.querySelector('.plan-head').addEventListener('click', () => card.classList.toggle('open'));
  });
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

function setupTabs() {
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      document.querySelector(`.tab-panel[data-panel="${t.dataset.tab}"]`).classList.add('active');
      Object.values(chartRegistry).forEach(c => c.resize());
    });
  });
}

function setupHoldingsControls() {
  document.querySelectorAll('.holdings-table th').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      if (sortBy.col === col) sortBy.dir = sortBy.dir === 'asc' ? 'desc' : 'asc';
      else { sortBy.col = col; sortBy.dir = 'desc'; }
      renderHoldingsTable();
    });
  });
  document.getElementById('filter-active').addEventListener('change', renderHoldingsTable);
  document.getElementById('filter-market').addEventListener('change', renderHoldingsTable);
}

window.addEventListener('resize', () => {
  Object.values(chartRegistry).forEach(c => c.resize());
});

async function main() {
  try {
    DATA = await loadData();
    HOLDINGS = [...DATA.holdings.us, ...DATA.holdings.hk];
    renderHero(DATA);
    renderLegSummary('us', DATA.totals.us, DATA.concentration.us, '$');
    renderLegSummary('hk', DATA.totals.hk, DATA.concentration.hk, 'HK$');
    renderTreemap('chart-us-treemap', DATA.concentration.us, '$');
    renderTreemap('chart-hk-treemap', DATA.concentration.hk, 'HK$');
    renderHHIGauge(DATA);
    renderMovers(DATA);
    renderHoldingsTable();
    renderConcDetail('conc-us-detail', DATA.concentration.us);
    renderConcDetail('conc-hk-detail', DATA.concentration.hk);
    renderHistory(DATA);
    renderPlans(DATA);
    setupTabs();
    setupHoldingsControls();
  } catch (e) {
    console.error(e);
    document.querySelector('main').innerHTML = `<div class="card"><h3>Failed to load data</h3><pre>${e.message}</pre></div>`;
  }
}

main();
