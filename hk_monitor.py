#!/usr/bin/env python3
"""
港股持仓盯盘脚本 - 每次运行输出最新持仓状态并推送 Telegram
"""
import urllib.request, json, subprocess, sys
from datetime import datetime

# ── 持仓配置 ──────────────────────────────────────────
HOLDINGS = {
    '02208': {'name': '金风科技',       'shares': 600,  'cost': 14.084},
    '03032': {'name': '恒生科技ETF',    'shares': 200,  'cost': 5.405},
    '07226': {'name': 'XL恒科(2x)',    'shares': 5200, 'cost': 4.4973},
    '07709': {'name': 'XL海力士(2x)',  'shares': 600,  'cost': 32.04},
    '07747': {'name': 'XL三星(2x)',    'shares': 200,  'cost': 81.85},
    '03033': {'name': '南方恒科ETF',   'shares': 1000, 'cost': 5.14},
}
INDEXES = ['r_hkHSI', 'r_hkHSTECH']
TG_CHAT_ID = '2033937852'

# ── 拉数据 ────────────────────────────────────────────
def fetch_tencent(codes):
    query = ','.join(f'hk{c}' if not c.startswith('r_') else c for c in codes)
    url = f'https://sqt.gtimg.cn/q={query}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=8) as r:
        raw = r.read().decode('gbk', errors='replace')
    result = {}
    for seg in raw.split(';'):
        if '~' not in seg:
            continue
        parts = seg.split('~')
        if len(parts) < 5:
            continue
        # extract code from key like v_hk02208 or v_r_hkHSI
        key_raw = parts[0].split('"')[0].split('=')[0].replace('v_', '').replace('\n', '').strip()
        code = key_raw.replace('hk', '', 1) if key_raw.startswith('hk') else key_raw
        try:
            price = float(parts[3])
            prev  = float(parts[4])
            chg   = round((price - prev) / prev * 100, 2) if prev else 0.0
        except:
            continue
        result[code] = {'name': parts[1], 'price': price, 'prev': prev, 'chg': chg}
    return result

# ── 格式化报告 ────────────────────────────────────────
def build_report(data):
    now = datetime.now().strftime('%H:%M')
    lines = [f'📊 港股盯盘 {now}']

    # 指数
    hsi   = data.get('r_hkHSI',    {})
    htech = data.get('r_hkHSTECH', {})
    if hsi:
        arrow = '🟢' if hsi['chg'] >= 0 else '🔴'
        lines.append(f"{arrow} 恒指 {hsi['price']:,.0f}  {hsi['chg']:+.2f}%")
    if htech:
        arrow = '🟢' if htech['chg'] >= 0 else '🔴'
        lines.append(f"{arrow} 恒科 {htech['price']:,.0f}  {htech['chg']:+.2f}%")

    lines.append('─' * 28)

    total_cost = total_val = 0
    alerts = []

    for code, cfg in HOLDINGS.items():
        q = data.get(code)
        if not q:
            lines.append(f"⚠️  {cfg['name']} 无数据")
            continue

        price  = q['price']
        chg    = q['chg']
        shares = cfg['shares']
        cost_p = cfg['cost']
        val    = price * shares
        cost   = cost_p * shares
        pnl    = val - cost
        pnl_p  = pnl / cost * 100
        to_be  = (cost_p - price) / price * 100  # 距回本还需涨%

        total_cost += cost
        total_val  += val

        day_arrow = '🟢' if chg >= 0 else '🔴'
        pnl_arrow = '✅' if pnl >= 0 else '📉'

        lines.append(
            f"{day_arrow} {cfg['name']}\n"
            f"   现价 {price:.3f}  今日{chg:+.2f}%\n"
            f"   {pnl_arrow} 累计 {pnl:+,.0f}HKD ({pnl_p:+.1f}%)  "
            f"{'已回本' if to_be <= 0 else f'距回本{to_be:+.1f}%'}"
        )

        # 预警：单日涨跌超10% 或 距回本<5%
        if abs(chg) >= 10:
            alerts.append(f"⚡ {cfg['name']} 今日{chg:+.1f}%，注意操作！")
        if 0 < to_be <= 5:
            alerts.append(f"🎯 {cfg['name']} 距回本仅{to_be:.1f}%，快了！")

    total_pnl = total_val - total_cost
    lines.append('─' * 28)
    lines.append(
        f"港股合计  HKD {total_val:,.0f}\n"
        f"总盈亏  {total_pnl:+,.0f}  ({total_pnl/total_cost*100:+.1f}%)"
    )

    if alerts:
        lines.append('─' * 28)
        lines += alerts

    # ── 操作建议 ──────────────────────────────────────
    suggestions = []
    entry_alerts = []  # 加仓机会专项提醒

    for code, cfg in HOLDINGS.items():
        q = data.get(code)
        if not q:
            continue
        price  = q['price']
        chg    = q['chg']
        cost_p = cfg['cost']
        to_be  = (cost_p - price) / price * 100

        name = cfg['name']
        is_leveraged = '(2x)' in name

        # 杠杆ETF 大涨后建议减仓
        if is_leveraged and chg >= 10:
            suggestions.append(f'🔔 {name} 今日+{chg:.0f}%，杠杆品大涨建议考虑减仓1/3~1/2锁利')

        # 距回本很近
        if 0 < to_be <= 3:
            suggestions.append(f'🎯 {name} 距回本仅{to_be:.1f}%，可挂单 {cost_p:.3f} 附近止盈')

        # 已超本
        if to_be < -5 and not is_leveraged:
            suggestions.append(f'💰 {name} 已超成本{abs(to_be):.1f}%，可考虑止盈部分')

        # 杠杆ETF 大跌预警
        if is_leveraged and chg <= -8:
            suggestions.append(f'⚠️ {name} 今日-{abs(chg):.0f}%，杠杆放大下跌，注意止损')

        # 跌破成本较多
        if to_be >= 15 and is_leveraged:
            suggestions.append(f'❄️ {name} 距回本{to_be:.0f}%，杠杆ETF不建议摊平，耐心等待')

    # ── 加仓时机监控（存储板块 + 恒科板块）────────────
    # 存储杠杆ETF：回调到理想加仓区且当日止跌企稳
    mem_hix = data.get('07709')
    mem_sam = data.get('07747')
    if mem_hix:
        p, chg = mem_hix['price'], mem_hix['chg']
        if 24.5 <= p <= 26.5:
            stability = '企稳中✅' if -3 <= chg <= 3 else f'仍波动({chg:+.1f}%)'
            entry_alerts.append(
                f'🟡【加仓机会-存储】XL海力士(2x) 回调至 {p:.2f}\n'
                f'   已进入理想加仓区 24.5~26.5，{stability}\n'
                f'   摊平后均价约 30.0，距回本{((32.04-((600*32.04+300*p)/900))/((600*32.04+300*p)/900)*100):.0f}%'
            )
        elif p < 24.5:
            entry_alerts.append(f'🔴【存储破位】XL海力士(2x) {p:.2f} 跌破24.5支撑，暂缓加仓，观察24.0')

    if mem_sam:
        p, chg = mem_sam['price'], mem_sam['chg']
        if 64.0 <= p <= 67.5:
            stability = '企稳中✅' if -3 <= chg <= 3 else f'仍波动({chg:+.1f}%)'
            entry_alerts.append(
                f'🟡【加仓机会-存储】XL三星(2x) 回调至 {p:.2f}\n'
                f'   已进入理想加仓区 64~67.5，{stability}\n'
                f'   摊平后均价约 75.9，距回本{((81.85-75.9)/75.9*100):.0f}%'
            )
        elif p < 64.0:
            entry_alerts.append(f'🔴【存储破位】XL三星(2x) {p:.2f} 跌破64支撑，暂缓加仓')

    # 恒生科技：回调到支撑区且HSTECH守住4960
    hstech = data.get('r_hkHSTECH')
    etf_032 = data.get('03032')
    etf_033 = data.get('03033')

    if hstech and etf_032 and etf_033:
        hs_price = hstech['price']
        hs_chg   = hstech['chg']
        p032 = etf_032['price']
        p033 = etf_033['price']

        # 恒科回踩支撑区 4960~5020 且不破位
        if 4960 <= hs_price <= 5020 and hs_chg > -2:
            entry_alerts.append(
                f'🟡【加仓机会-恒科】恒生科技指数回踩至 {hs_price:.0f}\n'
                f'   处于支撑区 4960~5020，跌幅{hs_chg:+.2f}%，缩量企稳信号\n'
                f'   03033({p033:.3f}) 加仓后距回本约{((5.14-p033)/p033*100):.1f}%\n'
                f'   03032({p032:.3f}) 加仓后距回本约{((5.405-p032)/p032*100):.1f}%'
            )
        # 恒科强势突破5100+，动能信号
        elif hs_price >= 5100 and hs_chg >= 1.5:
            entry_alerts.append(
                f'🟢【恒科突破】恒生科技指数站上 {hs_price:.0f}（+{hs_chg:.2f}%）\n'
                f'   突破5100压力位，趋势信号增强\n'
                f'   03033 距回本{((5.14-p033)/p033*100):.1f}%，若持续可考虑加仓07226'
            )

    if entry_alerts:
        lines.append('─' * 28)
        lines.append('📍 加仓机会提醒')
        lines += entry_alerts

    if suggestions:
        lines.append('─' * 28)
        lines.append('💡 操作建议')
        lines += suggestions
    else:
        lines.append('─' * 28)
        lines.append('💡 持仓观望，等待信号')

    return '\n'.join(lines)

# ── 发送 Telegram ─────────────────────────────────────
OPENCLAW_BIN = '/root/.local/share/pnpm/openclaw'

def send_telegram(msg):
    cmd = [
        OPENCLAW_BIN, 'message', 'send',
        '--channel', 'telegram',
        '--target', TG_CHAT_ID,
        '--message', msg,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        print(f'[ERROR] 发送失败: {result.stderr}', file=sys.stderr)
        return False
    return True

# ── 主逻辑 ────────────────────────────────────────────
def main():
    codes = list(HOLDINGS.keys()) + INDEXES
    try:
        data = fetch_tencent(codes)
    except Exception as e:
        print(f'[ERROR] 获取数据失败: {e}', file=sys.stderr)
        sys.exit(1)

    report = build_report(data)
    print(report)  # 本地也打印

    if '--no-send' not in sys.argv:
        ok = send_telegram(report)
        sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
