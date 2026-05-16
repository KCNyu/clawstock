#!/usr/bin/env python3
"""
港股监控脚本 - 后台运行，触发条件时发 Telegram 通知
"""
import time, re, subprocess, sys
import urllib.request

CHAT_ID = "2033937852"

# 监控条件
ALERTS = {
    "07709": {
        "name": "海力士2x",
        "cost": 31.691,
        "rules": [
            {"type": "below", "price": 32.0,  "msg": "⚠️ 07709 海力士2x 跌破 32.0（HKD {price}），安全垫剩余不多，考虑减仓100股锁利润", "triggered": False},
            {"type": "below", "price": 31.7,  "msg": "🚨 07709 海力士2x 跌破成本线 31.7（HKD {price}），建议立即止损！", "triggered": False},
            {"type": "above", "price": 34.5,  "msg": "📈 07709 海力士2x 反弹到 34.5（HKD {price}），可以考虑分批止盈", "triggered": False},
        ]
    },
    "01810": {
        "name": "小米",
        "rules": [
            {"type": "above", "price": 37.5,  "msg": "⚡ 小米冲上 37.5（HKD {price}），高位量价背离，注意见顶风险", "triggered": False},
            {"type": "below", "price": 35.2,  "msg": "📉 小米回调到 35.2（HKD {price}），接近支撑区间，可关注买入机会", "triggered": False},
            {"type": "below", "price": 34.8,  "msg": "💡 小米回调到 34.8（HKD {price}），35.0-34.5 区间，可考虑小仓位试探", "triggered": False},
        ]
    },
    "07226": {
        "name": "南方2x恒科",
        "cost": 4.497,
        "rules": [
            {"type": "below", "price": 3.9,   "msg": "🚨 07226 南方2x恒科 跌破 3.9（HKD {price}），亏损扩大到 -13%+，需要决策", "triggered": False},
            {"type": "above", "price": 4.3,   "msg": "📈 07226 南方2x恒科 反弹到 4.3（HKD {price}），可考虑减仓降低持仓风险", "triggered": False},
        ]
    },
}

# 收盘提醒（15:55）
CLOSE_ALERT_SENT = False

def fetch_prices():
    codes = ",".join([f"r_hk0{c}" if len(c)==4 else f"r_hk{c}" for c in ALERTS.keys()])
    # 实际codes
    code_str = "r_hk07709,r_hk01810,r_hk07226"
    url = f"https://qt.gtimg.cn/q={code_str}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode('gbk', errors='replace')
        result = {}
        items = re.findall(r'v_r_hk(\w+)="([^"]+)"', raw)
        for code, val in items:
            parts = val.split('~')
            try:
                result[code] = {
                    "price": float(parts[3]),
                    "pct": float(parts[32]),
                    "time": parts[30],
                }
            except:
                pass
        return result
    except Exception as e:
        return {}

def send_alert(msg):
    """通过 openclaw message 发送 Telegram 消息"""
    try:
        subprocess.run(
            ["openclaw", "message", "send", "--channel", "telegram", 
             "--target", CHAT_ID, "--message", msg],
            timeout=15, capture_output=True
        )
    except Exception as e:
        print(f"发送失败: {e}", flush=True)

def check_close_time(current_time_str):
    """判断是否接近收盘"""
    global CLOSE_ALERT_SENT
    if CLOSE_ALERT_SENT:
        return
    try:
        t = current_time_str.split(" ")[1]  # HH:MM:SS
        h, m = int(t.split(":")[0]), int(t.split(":")[1])
        if h == 15 and m >= 50:
            prices = fetch_prices()
            p07709 = prices.get("07709", {}).get("price", 0)
            pct07709 = prices.get("07709", {}).get("pct", 0)
            msg = f"🔔 港股尾盘提醒（15:50）\n\n07709 海力士2x: HKD {p07709} ({pct07709:+.2f}%)\n成本: 31.69，今日盈亏请决策：\n• 继续持有过夜？\n• 减仓锁利润？\n\n距收盘约10分钟"
            send_alert(msg)
            CLOSE_ALERT_SENT = True
    except:
        pass

def main():
    print("🚀 港股监控启动", flush=True)
    send_alert("📡 港股监控已启动\n\n监控标的：\n• 07709 海力士2x（触发线：32.0 / 31.7 / 34.5）\n• 01810 小米（触发线：37.5 / 35.2 / 34.8）\n• 07226 南方2x恒科（触发线：3.9 / 4.3）\n\n将在触发条件或尾盘(15:50)时提醒你 📲")

    while True:
        prices = fetch_prices()
        if not prices:
            time.sleep(30)
            continue

        for code, info in ALERTS.items():
            # 腾讯股票代码格式处理
            lookup_code = code.lstrip("0") or "0"
            # 直接用完整 code
            data = prices.get(code, {})
            if not data:
                continue
            current_price = data["price"]
            current_time = data.get("time", "")

            for rule in info["rules"]:
                if rule["triggered"]:
                    continue
                triggered = False
                if rule["type"] == "below" and current_price <= rule["price"]:
                    triggered = True
                elif rule["type"] == "above" and current_price >= rule["price"]:
                    triggered = True

                if triggered:
                    msg = rule["msg"].format(price=current_price)
                    send_alert(f"{msg}\n\n⏰ {current_time}")
                    rule["triggered"] = True
                    print(f"触发: {code} {rule['msg'][:40]}", flush=True)

            # 检查收盘时间
            if current_time:
                check_close_time(current_time)

        time.sleep(300)  # 每5分钟检查一次

if __name__ == "__main__":
    main()
