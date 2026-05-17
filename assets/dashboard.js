/* clawock dashboard — UI Pro Max design system applied
   Colors:    bull #26A69A / bear #EF5350 / primary #3B82F6 / cta #F59E0B
   Charts:    ECharts 5.5, dark theme, tnum numerics, hover tooltips
*/

const DATA_URL = 'assets/data/dashboard.json';

const C = {
  bull:    '#26a69a',
  bear:    '#ef5350',
  primary: '#3b82f6',
  primary2:'#1e40af',
  accent:  '#60a5fa',
  cta:     '#f59e0b',
  muted:   '#8893b3',
  text:    '#e8eaf2',
  panel:   '#131c2e',
  panel2:  '#1a2540',
  border:  '#243150',
  warn:    '#facc15',
  // Sequential palette for treemap (cool blues)
  seq:     ['#1e3a8a','#1e40af','#2563eb','#3b82f6','#60a5fa','#93c5fd','#bfdbfe','#dbeafe'],
};

/* Common tooltip + axis style for ECharts */
const TT = {
  backgroundColor: 'rgba(20,28,44,0.96)',
  borderColor: C.border,
  borderWidth: 1,
  padding: [8, 10],
  textStyle: { color: C.text, fontSize: 12, fontFamily: 'Fira Sans, sans-serif' },
  extraCssText: 'box-shadow: 0 8px 24px rgba(0,0,0,0.5); border-radius: 8px;',
};

const AXIS_LABEL = { color: C.muted, fontSize: 11, fontFamily: 'Fira Code, monospace' };
const SPLIT_LINE = { lineStyle: { color: C.border, type: 'dashed' } };

const fmt = {
  money(v, cur = '') {
    if (v == null || isNaN(v)) return '—';
    const sign = v < 0 ? '-' : '';
    const abs = Math.abs(v);
    const s = abs >= 10000 ? Math.round(abs).toLocaleString('en-US')
                           : abs.toFixed(abs >= 100 ? 1 : 2);
    return `${sign}${cur}${s}`;
  },
  pct(v) {
    if (v == null || isNaN(v)) return '—';
    return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
  },
  num(v, dp = 2) {
    if (v == null || isNaN(v)) return '—';
    return Number(v.toFixed(dp)).toLocaleString('en-US');
  },
  pctSpan(v) {
    if (v == null || isNaN(v)) return '<span class="muted">—</span>';
    return `<span class="${v >= 0 ? 'pos' : 'neg'}">${fmt.pct(v)}</span>`;
  },
  moneySpan(v, cur) {
    if (v == null || isNaN(v)) return '<span class="muted">—</span>';
    return `<span class="${v >= 0 ? 'pos' : 'neg'}">${fmt.money(v, cur)}</span>`;
  },
  date(s) { return s ? s.split('T')[0] : '—'; },
};

let DATA = null;
let HOLDINGS = [];
let sortBy = { col: 'current_value', dir: 'desc' };
const charts = {};

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
  const todayUsd = (d.totals.us.today_change_usd || 0) + (fx ? (d.totals.hk.today_change_hkd || 0) / fx : 0);

  document.getElementById('hero-book').innerHTML =
    `$${fmt.num(bookUsd, 0)}<small>≈ HK$${fmt.num(bookHkd, 0)}</small>`;
  document.getElementById('hero-today').innerHTML = fmt.moneySpan(todayUsd, '$');
  document.getElementById('hero-fx').textContent  = fx ? fx.toFixed(4) : '—';
  document.getElementById('hero-updated').textContent = fmt.date(d.last_updated);
  document.getElementById('footer-gen').textContent = fmt.date(d.generated_at);

  // KPI top cards
  document.getElementById('kpi-us-value').textContent = '$' + fmt.num(usVal, 0);
  document.getElementById('kpi-us-pnl').innerHTML =
    `P&L ${fmt.moneySpan(d.totals.us.pnl_usd, '$')} <span class="muted">(${fmt.pct(d.totals.us.pnl_pct)})</span>`;

  document.getElementById('kpi-hk-value').textContent = 'HK$' + fmt.num(hkVal, 0);
  document.getElementById('kpi-hk-pnl').innerHTML =
    `P&L ${fmt.moneySpan(d.totals.hk.pnl_hkd, 'HK$')} <span class="muted">(${fmt.pct(d.totals.hk.pnl_pct)})</span>`;

  document.getElementById('kpi-today').innerHTML = fmt.moneySpan(todayUsd, '$');
  document.getElementById('kpi-today-sub').innerHTML =
    `US ${fmt.moneySpan(d.totals.us.today_change_usd, '$')} · HK ${fmt.moneySpan(d.totals.hk.today_change_hkd, 'HK$')}`;

  const maxHhi = Math.max(d.concentration.us.hhi, d.concentration.hk.hhi);
  const worstLeg = d.concentration.us.hhi >= d.concentration.hk.hhi ? 'us' : 'hk';
  const v = d.concentration[worstLeg].verdict;
  document.getElementById('kpi-hhi').textContent = maxHhi.toFixed(3);
  document.getElementById('kpi-hhi-sub').innerHTML =
    `${worstLeg.toUpperCase()} leg · <span class="badge ${v.level}">${v.label}</span>`;
}

function renderLegSummary(legId, totals, sym) {
  const value = totals.value_usd ?? totals.value_hkd;
  const pnl   = totals.pnl_usd   ?? totals.pnl_hkd;
  const today = totals.today_change_usd ?? totals.today_change_hkd;
  const el = document.getElementById(legId + '-summary');
  el.innerHTML = `
    <div class="stat"><span class="l">Value</span><span class="v tabular">${sym}${fmt.num(value, 0)}</span></div>
    <div class="stat"><span class="l">P&L</span><span class="v tabular ${pnl >= 0 ? 'pos' : 'neg'}">${sym}${fmt.num(pnl, 0)}<small>(${fmt.pct(totals.pnl_pct)})</small></span></div>
    <div class="stat"><span class="l">Today</span><span class="v tabular ${today >= 0 ? 'pos' : 'neg'}">${sym}${fmt.num(today, 0)}</span></div>
  `;
}

function renderTreemap(elId, conc, sym) {
  const el = document.getElementById(elId);
  charts[elId]?.dispose();
  const chart = echarts.init(el, null, { renderer: 'canvas' });
  charts[elId] = chart;

  const positions = conc.positions.map((p, i) => ({
    name: p.ticker + (p.name ? ` ${p.name}` : ''),
    value: p.value,
    weight: p.weight,
    ticker: p.ticker,
    itemStyle: { color: C.seq[i % C.seq.length] },
  }));

  if (!positions.length) {
    el.innerHTML = '<div class="empty-state"><svg width="32" height="32"><use href="#i-info"/></svg>No active positions</div>';
    return;
  }

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      ...TT,
      formatter: (p) => `
        <div style="font-family:Fira Sans;font-weight:600;margin-bottom:4px">${p.data.ticker}</div>
        <div style="font-family:Fira Code;font-size:11px;color:${C.muted}">${p.data.name.replace(p.data.ticker,'').trim()}</div>
        <div style="font-family:Fira Code;margin-top:6px">Value <b>${sym}${fmt.num(p.data.value, 0)}</b></div>
        <div style="font-family:Fira Code">Weight <b>${(p.data.weight*100).toFixed(2)}%</b></div>
      `,
    },
    series: [{
      type: 'treemap',
      data: positions,
      roam: false,
      breadcrumb: { show: false },
      label: {
        show: true,
        formatter: (p) => `{tick|${p.data.ticker}}\n{pct|${(p.data.weight*100).toFixed(1)}%}`,
        rich: {
          tick: { color: '#fff', fontSize: 13, fontFamily: 'Fira Sans, sans-serif', fontWeight: 600, lineHeight: 18 },
          pct:  { color: 'rgba(255,255,255,0.85)', fontSize: 11, fontFamily: 'Fira Code, monospace' },
        },
      },
      itemStyle: { borderColor: C.bg, borderWidth: 2, gapWidth: 2, borderRadius: 4 },
      emphasis: { itemStyle: { borderColor: C.cta, borderWidth: 2 } },
    }],
  });
}

function renderHHIGauge(d) {
  const el = document.getElementById('chart-hhi-gauge');
  charts['chart-hhi-gauge']?.dispose();
  const chart = echarts.init(el, null, { renderer: 'canvas' });
  charts['chart-hhi-gauge'] = chart;

  // Responsive gauge layout: side-by-side on wide, stacked on narrow
  const w = el.clientWidth;
  const stacked = w < 380;
  const radius = stacked ? '55%' : (w < 520 ? '70%' : '85%');

  const baseGauge = {
    type: 'gauge',
    min: 0,
    max: 0.6,
    radius,
    progress: { show: true, width: 10, roundCap: true },
    axisLine: {
      lineStyle: {
        width: 10,
        color: [[0.25, C.bull], [0.42, C.warn], [0.67, '#fb923c'], [1, C.bear]],
      },
    },
    axisTick: { show: false },
    splitLine: { length: 5, lineStyle: { color: 'rgba(255,255,255,0.35)', width: 1 } },
    axisLabel: { color: C.muted, fontSize: 9, fontFamily: 'Fira Code', distance: -22 },
    pointer: { length: '60%', width: 3, itemStyle: { color: C.text } },
    anchor: { show: false },
    title: { offsetCenter: [0, '28%'], color: C.muted, fontSize: 11, fontFamily: 'Fira Sans' },
    detail: {
      offsetCenter: [0, '5%'],
      color: C.text,
      fontSize: stacked ? 16 : 20,
      fontWeight: 600,
      fontFamily: 'Fira Code, monospace',
      formatter: v => v.toFixed(3),
    },
  };

  const series = stacked
    ? [
        { ...baseGauge, center: ['50%', '28%'], data: [{ value: d.concentration.us.hhi, name: 'US HHI' }] },
        { ...baseGauge, center: ['50%', '78%'], data: [{ value: d.concentration.hk.hhi, name: 'HK HHI' }] },
      ]
    : [
        { ...baseGauge, center: ['25%', '60%'], data: [{ value: d.concentration.us.hhi, name: 'US HHI' }] },
        { ...baseGauge, center: ['75%', '60%'], data: [{ value: d.concentration.hk.hhi, name: 'HK HHI' }] },
      ];

  chart.setOption({ backgroundColor: 'transparent', series });
}

function renderMovers(d) {
  const el = document.getElementById('chart-movers');
  charts['chart-movers']?.dispose();
  const all = [...d.holdings.us, ...d.holdings.hk]
    .filter(h => h.is_active && Math.abs(h.today_change_pct) >= 1.5)
    .sort((a, b) => b.today_change_pct - a.today_change_pct);

  if (!all.length) {
    el.innerHTML = '<div class="empty-state"><svg width="32" height="32"><use href="#i-info"/></svg>今日无 ≥1.5% 异动</div>';
    return;
  }

  const chart = echarts.init(el, null, { renderer: 'canvas' });
  charts['chart-movers'] = chart;

  const items = all.map(h => ({
    name: h.ticker,
    fullName: `${h.ticker}${h.name ? ' ' + h.name : ''}`,
    value: h.today_change_pct,
    itemStyle: { color: h.today_change_pct >= 0 ? C.bull : C.bear },
  }));

  chart.setOption({
    backgroundColor: 'transparent',
    grid: { top: 16, left: 80, right: 50, bottom: 28 },
    xAxis: {
      type: 'value',
      axisLabel: { ...AXIS_LABEL, formatter: '{value}%' },
      splitLine: SPLIT_LINE,
      axisLine: { lineStyle: { color: C.border } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'category',
      data: items.map(i => i.name),
      axisLabel: { color: C.text, fontSize: 11, fontFamily: 'Fira Code' },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    tooltip: {
      ...TT,
      trigger: 'item',
      formatter: (p) => `<b>${items[p.dataIndex].fullName}</b><br/><span style="font-family:Fira Code">${fmt.pct(p.value)}</span>`,
    },
    series: [{
      type: 'bar',
      data: items,
      label: {
        show: true,
        position: 'right',
        color: C.text,
        fontFamily: 'Fira Code',
        fontSize: 11,
        formatter: p => fmt.pct(p.value),
      },
      barMaxWidth: 18,
      itemStyle: { borderRadius: [0, 4, 4, 0] },
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

  document.getElementById('holdings-count').textContent = `(${rows.length})`;

  tbody.innerHTML = rows.map(h => {
    const cur = h.currency === 'USD' ? '$' : 'HK$';
    return `<tr class="${h.is_active ? '' : 'inactive'}">
      <td class="ticker-cell">${h.ticker}</td>
      <td>${h.name || ''}</td>
      <td><span class="badge moderate" style="background:rgba(59,130,246,0.12);color:${C.accent};font-size:10px;padding:1px 6px">${h.currency}</span></td>
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
  const v = conc.verdict;
  el.innerHTML = `
    <div class="top-row">
      <span class="muted">HHI</span>
      <span><b>${conc.hhi.toFixed(4)}</b> <span class="badge ${v.level}">${v.label}</span></span>
    </div>
    <div class="top-row">
      <span class="muted">Top 2</span>
      <span><b>${(conc.top2*100).toFixed(1)}%</b></span>
    </div>
    <div class="top-row">
      <span class="muted">Total Value</span>
      <span><b class="mono">${fmt.num(conc.total, 0)}</b></span>
    </div>
    <h4 style="margin-top:18px">Position Weights</h4>
    ${conc.positions.map(p => `
      <div style="padding:6px 0">
        <div class="top-row" style="border:none;padding:4px 0">
          <span class="ticker">${p.ticker} <span class="muted" style="font-weight:400;font-family:Fira Sans">${p.name || ''}</span></span>
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

  if (!snaps.length) {
    elV.innerHTML = '<div class="empty-state"><svg width="32" height="32"><use href="#i-info"/></svg>尚无 snapshot 数据<br/><span style="font-size:11px">brief_preflight 每日 08:00 写入 memory/snapshots/{date}.json</span></div>';
    elP.innerHTML = '<div class="empty-state"><svg width="32" height="32"><use href="#i-info"/></svg>尚无 P&L 数据</div>';
    return;
  }

  charts['chart-history-value']?.dispose();
  charts['chart-history-pnl']?.dispose();
  const chartV = echarts.init(elV, null, { renderer: 'canvas' });
  const chartP = echarts.init(elP, null, { renderer: 'canvas' });
  charts['chart-history-value'] = chartV;
  charts['chart-history-pnl'] = chartP;

  const dates = snaps.map(s => s.date);
  const usVals = snaps.map(s => s.us_total_value || 0);
  const hkVals = snaps.map(s => s.hk_total_value || 0);
  const usPnl  = snaps.map(s => s.us_today_change || 0);
  const hkPnl  = snaps.map(s => s.hk_today_change || 0);

  chartV.setOption({
    backgroundColor: 'transparent',
    legend: { data: ['US (USD)', 'HK (HKD)'], textStyle: { color: C.text, fontFamily: 'Fira Sans' }, top: 0, right: 10 },
    tooltip: { ...TT, trigger: 'axis' },
    grid: { top: 36, left: 70, right: 70, bottom: 40 },
    xAxis: {
      type: 'category', data: dates,
      axisLabel: AXIS_LABEL, axisLine: { lineStyle: { color: C.border } }, axisTick: { show: false },
    },
    yAxis: [
      { type: 'value', name: 'USD', position: 'left', axisLabel: AXIS_LABEL, splitLine: SPLIT_LINE, nameTextStyle: { color: C.muted } },
      { type: 'value', name: 'HKD', position: 'right', axisLabel: AXIS_LABEL, nameTextStyle: { color: C.muted } },
    ],
    series: [
      { name: 'US (USD)', type: 'line', data: usVals, smooth: true, symbolSize: 6, itemStyle: { color: C.accent }, lineStyle: { width: 2 }, yAxisIndex: 0, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(96,165,250,0.25)' }, { offset: 1, color: 'rgba(96,165,250,0)' }] } } },
      { name: 'HK (HKD)', type: 'line', data: hkVals, smooth: true, symbolSize: 6, itemStyle: { color: C.cta }, lineStyle: { width: 2 }, yAxisIndex: 1, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(245,158,11,0.20)' }, { offset: 1, color: 'rgba(245,158,11,0)' }] } } },
    ],
  });

  chartP.setOption({
    backgroundColor: 'transparent',
    legend: { data: ['US (USD)', 'HK (HKD)'], textStyle: { color: C.text, fontFamily: 'Fira Sans' }, top: 0, right: 10 },
    tooltip: { ...TT, trigger: 'axis' },
    grid: { top: 36, left: 70, right: 30, bottom: 40 },
    xAxis: { type: 'category', data: dates, axisLabel: AXIS_LABEL, axisLine: { lineStyle: { color: C.border } }, axisTick: { show: false } },
    yAxis: { type: 'value', axisLabel: AXIS_LABEL, splitLine: SPLIT_LINE },
    series: [
      { name: 'US (USD)', type: 'bar', data: usPnl, itemStyle: { color: p => p.value >= 0 ? C.bull : C.bear, borderRadius: [3, 3, 0, 0] } },
      { name: 'HK (HKD)', type: 'bar', data: hkPnl, itemStyle: { color: p => p.value >= 0 ? 'rgba(38,166,154,0.65)' : 'rgba(239,83,80,0.65)', borderRadius: [3, 3, 0, 0] } },
    ],
  });
}

function renderPlans(d) {
  const el = document.getElementById('plans-list');
  const plans = (d.recent_plans || []).slice().reverse();
  if (!plans.length) {
    el.innerHTML = '<div class="empty-state"><svg width="32" height="32"><use href="#i-info"/></svg>No daily plan data yet.</div>';
    return;
  }
  el.innerHTML = plans.map(p => {
    const actions = (p.plan.actions || p.plan.plan || []);
    const retro = p.plan.retrospective;
    return `<div class="plan-card">
      <div class="plan-head">
        <span class="plan-title">${p.date}</span>
        <span class="plan-meta">${actions.length} actions${retro ? ' · has retrospective' : ''}</span>
      </div>
      <pre>${escapeHtml(JSON.stringify(p.plan, null, 2))}</pre>
    </div>`;
  }).join('');
  el.querySelectorAll('.plan-card').forEach(card => {
    card.querySelector('.plan-head').addEventListener('click', () => card.classList.toggle('open'));
    card.querySelector('.plan-head').setAttribute('role', 'button');
    card.querySelector('.plan-head').setAttribute('tabindex', '0');
    card.querySelector('.plan-head').addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); card.classList.toggle('open'); }
    });
  });
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

function setupTabs() {
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(x => { x.classList.remove('active'); x.setAttribute('aria-selected', 'false'); });
      document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      t.setAttribute('aria-selected', 'true');
      document.querySelector(`.tab-panel[data-panel="${t.dataset.tab}"]`).classList.add('active');
      Object.values(charts).forEach(c => c && c.resize && c.resize());
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

let resizeTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    Object.values(charts).forEach(c => c && c.resize && c.resize());
  }, 120);
});

async function waitForECharts() {
  let tries = 0;
  while (typeof echarts === 'undefined' && tries < 50) {
    await new Promise(r => setTimeout(r, 60));
    tries++;
  }
}

async function main() {
  try {
    await waitForECharts();
    DATA = await loadData();
    HOLDINGS = [...DATA.holdings.us, ...DATA.holdings.hk];
    renderHero(DATA);
    renderLegSummary('us', DATA.totals.us, '$');
    renderLegSummary('hk', DATA.totals.hk, 'HK$');
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
    document.querySelector('main').innerHTML = `<div class="card span-4"><h3>Failed to load data</h3><pre style="background:var(--bg);padding:14px;border-radius:8px;font-size:11px">${e.message}</pre></div>`;
  }
}

main();
