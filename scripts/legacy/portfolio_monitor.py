#!/usr/bin/env python3
"""
Portfolio Monitor for kcn
自动监控持仓，发现抄底/搏反弹机会时发 Telegram 提醒

触发条件：
1. 🔥 当日下跌 >= 5%，可能超卖反弹机会
2. 📉 惨跌警报：当日下跌 >= 8%，极端超卖
3. 🚀 反弹信号：日内从最低点反弹 >= 3%（V型反转）
4. 💡 加仓时机：价格跌破成本价 >= 8%（可考虑摊平）
"""

import json
import os
import sys
import requests
import time
from datetime import datetime, timezone, timedelta

# === 配置 ===
TELEGRAM_BOT_TOKEN = "8373204528:AAGvRWEMI9Zs84OcWGf0s_IaDuzCfINZplw"
TELEGRAM_CHAT_ID = "2033937852"
WORKSPACE = "/root/.openclaw/workspace"
PORTFOLIO_FILE = os.path.join(WORKSPACE, "portfolio.json")
STATE_FILE = os.path.join(WORKSPACE, "monitor_state.json")
API_KEYS_FILE = os.path.join(WORKSPACE, ".api_keys")

# 各股每手股数（港股必须整手买卖）
LOT_SIZES = {
    '02208': 100,   # 金风科技
    '03032': 100,   # 恒生科技ETF
    '03033': 100,   # 南方恒生科技
    '07226': 100,   # XL二南方恒科 2x
    # '07709': 100,   # 已清仓 2026-05-05
    # '07747': 100,   # 已清仓 2026-05-05
}

def to_lots(ticker, shares):
    """股数换算为手数（向下取整）"""
    lot = LOT_SIZES.get(ticker, 100)
    return max(1, shares // lot), lot

# 触发阈值
INTRADAY_DIP_THRESHOLD = -5.0      # 当日跌幅 >= 5% 触发提醒
EXTREME_DIP_THRESHOLD = -8.0       # 当日跌幅 >= 8% 极端提醒
BOUNCE_FROM_LOW_THRESHOLD = 2.0    # 从日内低点反弹 >= 2%（今天暴跌行情降低阈值）
BELOW_COST_THRESHOLD = -8.0        # 跌破成本 >= 8% 可考虑摊平
ALERT_COOLDOWN_MINUTES = 20        # bounce/dip 冷却时间（分钟）
EXTREME_DIP_COOLDOWN_MINUTES = 180 # 极端下跌只提醒一次，3小时内不重复

def load_api_keys():
    keys = {}
    with open(API_KEYS_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                keys[k] = v
    return keys

def load_portfolio():
    with open(PORTFOLIO_FILE, 'r') as f:
        return json.load(f)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"alerts_sent": {}, "price_history": {}}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def send_telegram(message):
    """发送 Telegram 消息"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"✅ Telegram 已发送")
        return True
    except Exception as e:
        print(f"❌ Telegram 发送失败: {e}")
        return False

def get_quote_finnhub(ticker, api_key):
    """从 Finnhub 获取实时报价"""
    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data and data.get('c', 0) > 0:
            return data
    except Exception as e:
        print(f"  Finnhub 失败 {ticker}: {e}")
    return None

def get_hk_quotes_sina(ticker_codes):
    """新浪财经港股实时报价（备用）"""
    symbols = ','.join(f'hk{code}' for code in ticker_codes)
    url = f'https://hq.sinajs.cn/list={symbols}'
    hdrs = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'}
    result = {}
    try:
        resp = requests.get(url, headers=hdrs, timeout=10)
        resp.encoding = 'gbk'
        for line in resp.text.strip().split('\n'):
            if '=' not in line or '"' not in line:
                continue
            key = line.split('=')[0].split('_')[-1]  # e.g. hk03033
            code = key.replace('hk', '')
            val = line.split('"')[1]
            f = val.split(',')
            if len(f) < 9 or not f[2]:
                continue
            current = float(f[2]) if f[2] else 0
            prev_close = float(f[3]) if f[3] else 0
            open_p = float(f[4]) if f[4] else 0
            day_high = float(f[5]) if f[5] else 0
            day_low = float(f[6]) if f[6] else 0
            chg_pct = ((current - prev_close) / prev_close * 100) if prev_close > 0 else 0
            if current > 0:
                result[code] = {
                    'c': current, 'pc': prev_close, 'o': open_p,
                    'h': day_high, 'l': day_low, 'change_pct': chg_pct,
                }
    except Exception as e:
        print(f"  新浪财经失败: {e}")
    return result

def get_hk_quotes_tencent(ticker_codes):
    """
    从腾讯财经批量获取港股实时报价
    ticker_codes: list of str, 如 ['03033', '07709']
    返回 dict: {ticker: quote_dict}
    """
    symbols = ','.join(f'r_hk{code}' for code in ticker_codes)
    url = f'https://qt.gtimg.cn/q={symbols}'
    hdrs = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com/'}
    result = {}
    try:
        resp = requests.get(url, headers=hdrs, timeout=10)
        for line in resp.text.strip().split('\n'):
            if '=' not in line or '"' not in line:
                continue
            val = line.split('"')[1]
            fields = val.split('~')
            if len(fields) < 33:
                continue
            code = fields[2]
            current = float(fields[3]) if fields[3] else 0
            prev_close = float(fields[4]) if fields[4] else 0
            open_p = float(fields[5]) if fields[5] else 0
            change_pct = float(fields[32]) if fields[32] else 0
            day_high = 0
            day_low = 0
            # 尝试解析日高日低（字段位置可能变化）
            try:
                day_high = float(fields[33]) if len(fields) > 33 and fields[33] else current
                day_low = float(fields[34]) if len(fields) > 34 and fields[34] else current
            except:
                day_high = current
                day_low = current
            if current > 0:
                result[code] = {
                    'c': current,
                    'pc': prev_close,
                    'o': open_p,
                    'h': day_high if day_high > 0 else current,
                    'l': day_low if day_low > 0 else current,
                    'change_pct': change_pct,
                }
    except Exception as e:
        print(f"  腾讯财经失败: {e}")
    return result

def get_quote_alphavantage(ticker, api_key):
    """从 Alpha Vantage 获取报价（备用）"""
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        gq = data.get('Global Quote', {})
        if gq and gq.get('05. price'):
            return {
                'c': float(gq['05. price']),
                'h': float(gq['03. high']),
                'l': float(gq['04. low']),
                'o': float(gq['02. open']),
                'pc': float(gq['08. previous close'])
            }
    except Exception as e:
        print(f"  AlphaVantage 失败 {ticker}: {e}")
    return None

def get_quote(ticker, keys):
    """获取美股报价，自动 fallback"""
    q = get_quote_finnhub(ticker, keys['FINNHUB_API_KEY'])
    if q:
        return q
    q = get_quote_alphavantage(ticker, keys['ALPHA_VANTAGE_API_KEY'])
    return q

def can_alert(state, ticker, alert_type):
    """检查是否在冷却期内"""
    key = f"{ticker}_{alert_type}"
    last_time = state["alerts_sent"].get(key)
    if last_time is None:
        return True
    elapsed = time.time() - last_time
    # 极端下跌/跌破成本：3小时内不重复
    if alert_type in ("extreme_dip", "below_cost"):
        return elapsed >= EXTREME_DIP_COOLDOWN_MINUTES * 60
    return elapsed >= ALERT_COOLDOWN_MINUTES * 60

def mark_alerted(state, ticker, alert_type):
    key = f"{ticker}_{alert_type}"
    state["alerts_sent"][key] = time.time()

def analyze_us_stock(ticker, holding, quote, state):
    """分析美股持仓，返回告警列表"""
    alerts = []
    current = quote['c']
    prev_close = quote.get('pc', current)
    day_high = quote.get('h', current)
    day_low = quote.get('l', current)
    cost = holding['cost_basis']
    shares = holding['shares']

    # 计算各种变化
    intraday_change_pct = ((current - prev_close) / prev_close) * 100 if prev_close > 0 else 0
    from_cost_pct = ((current - cost) / cost) * 100
    from_low_pct = ((current - day_low) / day_low) * 100 if day_low > 0 else 0

    print(f"  {ticker}: ${current:.2f} | 日内: {intraday_change_pct:+.1f}% | 成本: {from_cost_pct:+.1f}% | 从低反弹: {from_low_pct:+.1f}%")

    pnl = shares * (current - cost)

    # 1. 极端下跌
    if intraday_change_pct <= EXTREME_DIP_THRESHOLD and can_alert(state, ticker, "extreme_dip"):
        e1 = round(current * 0.99, 2)
        stop = round(current * 0.95, 2)
        alerts.append({
            "type": "extreme_dip",
            "body": (
                f"<b>🆘 {ticker} 极端下跌 {intraday_change_pct:.1f}%</b>\n"
                f"现价 <b>${current:.2f}</b>  昨收 ${prev_close:.2f}\n"
                f"成本偏离 {from_cost_pct:+.1f}%  盈亏 ${pnl:+.0f}\n"
                f"─────────────────\n"
                f"🎯 操作：极端超卖，可小仓位试探\n"
                f"   挂单 ≤${e1:.2f}，止损 ${stop:.2f}"
            )
        })
        mark_alerted(state, ticker, "extreme_dip")

    elif intraday_change_pct <= INTRADAY_DIP_THRESHOLD and can_alert(state, ticker, "dip"):
        e1 = round(current * 0.995, 2)
        e2 = round(current * 0.985, 2)
        alerts.append({
            "type": "dip",
            "body": (
                f"<b>📉 {ticker} 当日下跌 {intraday_change_pct:.1f}%</b>\n"
                f"现价 <b>${current:.2f}</b>  昨收 ${prev_close:.2f}\n"
                f"区间 ${day_low:.2f}~${day_high:.2f}  成本偏离 {from_cost_pct:+.1f}%\n"
                f"─────────────────\n"
                f"🎯 操作：分两批买入\n"
                f"   第1批 ≤${e1:.2f}  第2批 ≤${e2:.2f}\n"
                f"   止损：跌破 ${round(day_low*0.99,2):.2f}"
            )
        })
        mark_alerted(state, ticker, "dip")

    # V型反弹
    if (from_low_pct >= BOUNCE_FROM_LOW_THRESHOLD and
        intraday_change_pct < -2.0 and
        can_alert(state, ticker, "bounce")):
        entry = round(current * 1.005, 2)
        stop  = round(day_low * 0.98, 2)
        alerts.append({
            "type": "bounce",
            "body": (
                f"<b>🚀 {ticker} V型反弹 +{from_low_pct:.1f}%！</b>\n"
                f"现价 <b>${current:.2f}</b>  从低点 ${day_low:.2f} 反弹\n"
                f"今日 {intraday_change_pct:+.1f}%  成本偏离 {from_cost_pct:+.1f}%\n"
                f"─────────────────\n"
                f"🎯 操作：可追入，限价 ≤${entry:.2f}\n"
                f"   止损：跌回 ${stop:.2f} 以下离场"
            )
        })
        mark_alerted(state, ticker, "bounce")

    # 深度跌破成本
    if from_cost_pct <= BELOW_COST_THRESHOLD and can_alert(state, ticker, "below_cost"):
        e1 = round(current * 0.99, 2)
        alerts.append({
            "type": "below_cost",
            "body": (
                f"<b>💡 {ticker} 跌破成本 {from_cost_pct:.1f}%</b>\n"
                f"现价 <b>${current:.2f}</b>  成本 ${cost:.2f}  盈亏 ${pnl:+.0f}\n"
                f"─────────────────\n"
                f"🎯 操作：可加仓摊平\n"
                f"   挂单 ≤${e1:.2f}，止损 ${round(current*0.93,2):.2f}"
            )
        })
        mark_alerted(state, ticker, "below_cost")

    return alerts

def get_action_advice(ticker, name, current, cost, intraday_change_pct, from_cost_pct, from_open_pct, alert_type):
    """
    只在趋势明确时给出挂单建议，否则仅观察提示。
    核心原则：
    - bounce：从低点明显反弹 + 开盘后由负转正 → 可挂单
    - extreme_dip/dip：开盘后仍在跌 → 只通知，不挂单
    - below_cost：结合开盘后方向决定
    """
    is_leveraged = ticker in ('07226', '07709', '07747')
    lot = LOT_SIZES.get(ticker, 100)

    def fmt_order(price, lots, label=""):
        cost_total = round(price * lots * lot)
        tag = f"  {label}" if label else ""
        return f"≤{price:.3f}  {lots}手({lots*lot}股)  ~HKD{cost_total:,}{tag}"

    # ── 反弹信号：只有开盘后已经由负转正 or 跌幅收窄至-3%以内才给挂单 ──
    if alert_type == "bounce":
        if from_open_pct >= -3.0:
            # 趋势较好，可以追
            entry = round(current * 1.005, 3)
            stop  = round(current * 0.97,  3)
            lots  = 1
            return (f"✅ 趋势转好，可挂单\n"
                    f"   {fmt_order(entry, lots)}\n"
                    f"   止损：跌破 {stop:.3f}")
        else:
            # 反弹但开盘后仍大幅下跌，只是技术性反弹
            watch = round(current * 1.03, 3)
            return (f"👀 反弹中但开盘后仍跌 {from_open_pct:+.1f}%，暂观察\n"
                    f"   等开盘后跌幅收窄至 -3% 以内再考虑入场\n"
                    f"   关注位：{watch:.3f}")

    # ── 极端下跌 / 普通下跌：看开盘后方向 ──
    if alert_type in ("extreme_dip", "dip"):
        if from_open_pct >= 1.0:
            # 今日跌但开盘后在涨，说明有承接力
            e1 = round(current * 0.995, 3)
            lots = 1
            return (f"📌 今日大跌但开盘后回升 {from_open_pct:+.1f}%，有承接\n"
                    f"   可小仓位试探：{fmt_order(e1, lots)}\n"
                    f"   止损：跌破今日开盘价")
        elif from_open_pct <= -5.0:
            # 开盘后还在大跌，坚决不动
            return (f"🚫 开盘后仍跌 {from_open_pct:+.1f}%，趋势未止\n"
                    f"   继续观察，不挂单")
        else:
            # 开盘后小幅波动，等待
            return (f"⏳ 开盘后 {from_open_pct:+.1f}%，方向未明\n"
                    f"   等企稳信号再操作")

    # ── 跌破成本：只在开盘后止跌或回升时建议摊平 ──
    if alert_type == "below_cost":
        if from_open_pct >= 0:
            e1 = round(current * 0.995, 3)
            lots = 1
            new_avg = round((cost * 0.6 + current * 0.4), 3)  # 估算新均价
            return (f"💡 开盘后回升，可考虑摊平\n"
                    f"   {fmt_order(e1, lots)}\n"
                    f"   止损：跌破 {round(current * 0.95, 3):.3f}")
        else:
            return (f"⏳ 仍跌破成本且开盘后 {from_open_pct:+.1f}%\n"
                    f"   暂不摊平，等企稳")

    return "📌 持续观察"


def analyze_hk_stock(holding, quote, state):
    """分析港股持仓"""
    alerts = []
    ticker = holding['ticker']
    name = holding.get('name', ticker)
    current = quote['c']
    prev_close = quote.get('pc', current)
    day_high = quote.get('h', current)
    day_low = quote.get('l', current)
    open_p = quote.get('o', current)
    cost = holding['cost_basis']
    shares = holding['shares']

    if 'change_pct' in quote and quote['change_pct'] != 0:
        intraday_change_pct = quote['change_pct']
    else:
        intraday_change_pct = ((current - prev_close) / prev_close) * 100 if prev_close > 0 else 0
    from_cost_pct = ((current - cost) / cost) * 100
    from_low_pct  = ((current - day_low) / day_low) * 100 if day_low > 0 else 0
    from_open_pct = ((current - open_p) / open_p) * 100 if open_p > 0 else 0

    print(f"  {ticker} {name}: HKD {current:.3f} | 日内: {intraday_change_pct:+.1f}% | 开盘后: {from_open_pct:+.1f}% | 成本: {from_cost_pct:+.1f}%")

    pnl = shares * (current - cost)

    # 极端下跌
    if intraday_change_pct <= EXTREME_DIP_THRESHOLD and can_alert(state, ticker, "extreme_dip"):
        advice = get_action_advice(ticker, name, current, cost, intraday_change_pct, from_cost_pct, from_open_pct, "extreme_dip")
        alerts.append({
            "type": "extreme_dip",
            "body": (
                f"<b>🆘 {ticker} {name}  极端下跌 {intraday_change_pct:.1f}%</b>\n"
                f"现价 <b>HKD {current:.3f}</b>  昨收 {prev_close:.3f}\n"
                f"开盘后 {from_open_pct:+.1f}%  成本偏离 {from_cost_pct:+.1f}%  盈亏 HKD{pnl:+.0f}\n"
                f"─────────────────\n"
                f"{advice}"
            )
        })
        mark_alerted(state, ticker, "extreme_dip")

    elif intraday_change_pct <= INTRADAY_DIP_THRESHOLD and can_alert(state, ticker, "dip"):
        advice = get_action_advice(ticker, name, current, cost, intraday_change_pct, from_cost_pct, from_open_pct, "dip")
        alerts.append({
            "type": "dip",
            "body": (
                f"<b>📉 {ticker} {name}  当日下跌 {intraday_change_pct:.1f}%</b>\n"
                f"现价 <b>HKD {current:.3f}</b>  昨收 {prev_close:.3f}\n"
                f"开盘后 {from_open_pct:+.1f}%  成本偏离 {from_cost_pct:+.1f}%\n"
                f"─────────────────\n"
                f"{advice}"
            )
        })
        mark_alerted(state, ticker, "dip")

    # V型反弹
    if (from_low_pct >= BOUNCE_FROM_LOW_THRESHOLD and
        intraday_change_pct < -2.0 and
        can_alert(state, ticker, "bounce")):
        advice = get_action_advice(ticker, name, current, cost, intraday_change_pct, from_cost_pct, from_open_pct, "bounce")
        alerts.append({
            "type": "bounce",
            "body": (
                f"<b>🚀 {ticker} {name}  V型反弹 +{from_low_pct:.1f}%！</b>\n"
                f"现价 <b>HKD {current:.3f}</b>  从低点 {day_low:.3f} 反弹\n"
                f"今日 {intraday_change_pct:+.1f}%  开盘后 {from_open_pct:+.1f}%\n"
                f"─────────────────\n"
                f"{advice}"
            )
        })
        mark_alerted(state, ticker, "bounce")

    # 跌破成本
    if from_cost_pct <= BELOW_COST_THRESHOLD and can_alert(state, ticker, "below_cost"):
        advice = get_action_advice(ticker, name, current, cost, intraday_change_pct, from_cost_pct, from_open_pct, "below_cost")
        alerts.append({
            "type": "below_cost",
            "body": (
                f"<b>💡 {ticker} {name}  深度跌破成本 {from_cost_pct:.1f}%</b>\n"
                f"现价 <b>HKD {current:.3f}</b>  成本 {cost:.3f}  盈亏 HKD{pnl:+.0f}\n"
                f"─────────────────\n"
                f"{advice}"
            )
        })
        mark_alerted(state, ticker, "below_cost")

    return alerts

def is_hk_market_open():
    """判断港股是否在交易时间（北京时间 9:30-12:00, 13:00-16:00）"""
    tz_beijing = timezone(timedelta(hours=8))
    now = datetime.now(tz_beijing)
    # 周末不交易
    if now.weekday() >= 5:
        return False
    h, m = now.hour, now.minute
    time_val = h * 60 + m
    morning = 9 * 60 + 30 <= time_val <= 12 * 60
    afternoon = 13 * 60 <= time_val <= 16 * 60
    return morning or afternoon

def is_us_market_open():
    """判断美股是否在交易时间（北京时间 21:30 - 次日 04:00，夏令时 20:30-03:00）"""
    tz_beijing = timezone(timedelta(hours=8))
    now = datetime.now(tz_beijing)
    if now.weekday() >= 5:  # 周末
        return False
    # 周五美股收盘后（周六北京时间）不算
    h, m = now.hour, now.minute
    time_val = h * 60 + m
    # 夏令时 EDT: 20:30-03:00 北京时间
    # 冬令时 EST: 21:30-04:00 北京时间
    # 3月第二个周日开始夏令时（2026年3月8日开始），此时已是夏令时
    # 用 21:30-04:00 作为保守区间（兼容两种情况）
    # 深夜跨天：21:30+ 或 0:00-04:00
    is_evening = time_val >= 21 * 60 + 30
    is_early_morning = time_val <= 4 * 60
    # 周五收盘后到周六凌晨：美股周五收盘是北京时间周六 04:00
    # 周六的凌晨仍然属于周五美股收盘前
    if now.weekday() == 5 and is_early_morning:  # 周六凌晨
        return True
    if now.weekday() < 5 and (is_evening or is_early_morning):
        return True
    return False

def main():
    print(f"\n{'='*60}")
    print(f"📊 持仓监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    keys = load_api_keys()
    portfolio = load_portfolio()
    state = load_state()

    all_alerts = []
    hk_open = is_hk_market_open()
    us_open = is_us_market_open()

    print(f"港股市场: {'🟢 交易中' if hk_open else '🔴 休市'}")
    print(f"美股市场: {'🟢 交易中' if us_open else '🔴 休市'}")

    if not hk_open and not us_open:
        print("当前两市均休市，退出监控。")
        return

    # 港股监控（腾讯财经实时 → 新浪财经备用）
    if hk_open:
        print("\n--- 港股 ---")
        hk_holdings = portfolio['portfolios']['hk_stocks']['holdings']
        ticker_codes = [h['ticker'] for h in hk_holdings]
        hk_quotes = get_hk_quotes_tencent(ticker_codes)
        if len(hk_quotes) < len(ticker_codes) // 2:
            print("  腾讯财经数据不足，切换新浪财经...")
            hk_quotes = get_hk_quotes_sina(ticker_codes)
        for holding in hk_holdings:
            ticker_code = holding['ticker']
            quote = hk_quotes.get(ticker_code)
            if quote:
                alerts = analyze_hk_stock(holding, quote, state)
                all_alerts.extend(alerts)

    # 美股监控
    if us_open:
        print("\n--- 美股 ---")
        us_holdings = portfolio['portfolios']['us_stocks']['holdings']
        for holding in us_holdings:
            ticker = holding['ticker']
            quote = get_quote(ticker, keys)
            if quote:
                alerts = analyze_us_stock(ticker, holding, quote, state)
                all_alerts.extend(alerts)
            time.sleep(0.5)

    # 发送告警
    if all_alerts:
        print(f"\n🔔 发现 {len(all_alerts)} 个信号，发送 Telegram...")
        now_str = datetime.now().strftime('%m/%d %H:%M')
        header = f"⚡️ <b>持仓监控 [{now_str}]</b>\n{'─'*30}\n"
        bodies = [a['body'] for a in all_alerts]
        full_msg = header + "\n\n".join(bodies)
        send_telegram(full_msg)
    else:
        print("\n✅ 暂无触发信号，持仓平稳。")

    # 保存状态
    save_state(state)
    print(f"\n监控完成。")

if __name__ == '__main__':
    main()
