#!/usr/bin/env python3
"""
CN Finance Fetcher — 腾讯财经 + 新浪财经 数据抓取模块
支持港股 / 美股 / A股，无需 API Key
作为 Finnhub / Alpha Vantage 的免费备用数据源

数据源优先级:
  1. 腾讯财经 qt.gtimg.cn  (最稳定，结构化)
  2. 新浪财经 hq.sinajs.cn (覆盖更多标的)
  3. 新浪财经 网页慢爬     (最后备选，带 UA 模拟浏览器)
"""

import re
import time
import random
import json
import requests
from datetime import datetime
from typing import Optional, Dict, Any

# ---------------------------------------------------------------------------
# 公共 HTTP Session（模拟浏览器 UA）
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "*/*",
    "Referer": "https://finance.qq.com/",
}

_SINA_HEADERS = {
    **_HEADERS,
    "Referer": "https://finance.sina.com.cn/",
}

SESSION = requests.Session()
SESSION.headers.update(_HEADERS)


# ---------------------------------------------------------------------------
# 代码格式化工具
# ---------------------------------------------------------------------------

def _tencent_code(ticker: str, market: str = "hk") -> str:
    """
    将标的代码转换为腾讯财经格式
    HK:  02208  -> hk02208
    US:  NVDA   -> usNVDA
    A股: 000001 -> sh000001 / sz000001
    """
    if market == "hk":
        return f"hk{ticker.zfill(5)}"
    elif market == "us":
        return f"us{ticker.upper()}"
    elif market == "sh":
        return f"sh{ticker}"
    elif market == "sz":
        return f"sz{ticker}"
    return ticker


def _sina_code(ticker: str, market: str = "hk") -> str:
    """
    将标的代码转换为新浪财经格式
    HK:  02208  -> hk02208
    US:  NVDA   -> gb_nvda  (新浪用 gb_ 前缀)
    """
    if market == "hk":
        return f"hk{ticker.zfill(5)}"
    elif market == "us":
        return f"gb_{ticker.lower()}"
    elif market in ("sh", "sz"):
        return f"{market}{ticker}"
    return ticker


# ---------------------------------------------------------------------------
# 1. 腾讯财经 API  (qt.gtimg.cn)
# ---------------------------------------------------------------------------

def _parse_tencent_response(raw: str, market: str) -> Optional[Dict[str, Any]]:
    """解析腾讯 qtimg 返回的 ~ 分隔字符串"""
    match = re.search(r'"([^"]+)"', raw)
    if not match:
        return None
    parts = match.group(1).split("~")

    try:
        if market == "hk":
            # HK 格式: 100~名称~代码~现价~昨收~开盘~成交量~...~最高~最低~...
            if len(parts) < 35:
                return None
            name         = parts[1]
            current      = float(parts[3])
            prev_close   = float(parts[4])
            open_price   = float(parts[5])
            volume       = int(float(parts[6]))
            high         = float(parts[33])
            low          = float(parts[34])
        elif market == "us":
            # US 格式略有不同
            if len(parts) < 45:
                return None
            name         = parts[1]
            current      = float(parts[3])
            prev_close   = float(parts[4])
            open_price   = float(parts[5])
            volume       = int(float(parts[6])) if parts[6] else 0
            high         = float(parts[41]) if len(parts) > 41 and parts[41] else current
            low          = float(parts[42]) if len(parts) > 42 and parts[42] else current
        else:
            # A股
            if len(parts) < 30:
                return None
            name         = parts[1]
            current      = float(parts[3])
            prev_close   = float(parts[4])
            open_price   = float(parts[5])
            volume       = int(float(parts[6])) if parts[6] else 0
            high         = float(parts[33]) if len(parts) > 33 else current
            low          = float(parts[34]) if len(parts) > 34 else current

        change         = current - prev_close
        change_pct     = (change / prev_close * 100) if prev_close else 0

        return {
            "name":          name,
            "current_price": current,
            "open":          open_price,
            "high":          high,
            "low":           low,
            "prev_close":    prev_close,
            "change":        round(change, 4),
            "change_pct":    round(change_pct, 4),
            "volume":        volume,
            "source":        "腾讯财经",
            "fetched_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except (IndexError, ValueError):
        return None


def fetch_tencent(ticker: str, market: str = "hk") -> Optional[Dict[str, Any]]:
    """从腾讯财经拉取行情"""
    code = _tencent_code(ticker, market)
    url  = f"https://qt.gtimg.cn/q={code}"
    try:
        resp = SESSION.get(url, timeout=8)
        resp.encoding = "gbk"
        data = _parse_tencent_response(resp.text, market)
        if data:
            data["ticker"] = ticker
        return data
    except Exception as e:
        print(f"  [腾讯] {ticker} 失败: {e}")
        return None


# ---------------------------------------------------------------------------
# 2. 新浪财经 API  (hq.sinajs.cn)
# ---------------------------------------------------------------------------

def _parse_sina_response(raw: str, market: str) -> Optional[Dict[str, Any]]:
    """解析新浪 hq 返回的逗号分隔字符串"""
    match = re.search(r'"([^"]+)"', raw)
    if not match:
        return None
    parts = match.group(1).split(",")

    try:
        if market == "hk":
            # HK: 名称,今开,昨收,现价,最高,最低,...
            if len(parts) < 10:
                return None
            name       = parts[0]
            open_price = float(parts[1])
            prev_close = float(parts[2])
            current    = float(parts[3])
            high       = float(parts[4])
            low        = float(parts[5])
            volume     = int(float(parts[12])) if len(parts) > 12 and parts[12] else 0
        elif market == "us":
            # US (gb_ prefix): 名称,现价,涨跌额,涨跌%,昨收,今开,最高,最低,成交量,...
            if len(parts) < 9:
                return None
            name       = parts[0]
            current    = float(parts[1])
            prev_close = float(parts[4])
            open_price = float(parts[5])
            high       = float(parts[6])
            low        = float(parts[7])
            volume     = int(float(parts[8])) if parts[8] else 0
        else:
            return None

        change     = current - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "name":          name,
            "current_price": current,
            "open":          open_price,
            "high":          high,
            "low":           low,
            "prev_close":    prev_close,
            "change":        round(change, 4),
            "change_pct":    round(change_pct, 4),
            "volume":        volume,
            "source":        "新浪财经",
            "fetched_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except (IndexError, ValueError):
        return None


def fetch_sina(ticker: str, market: str = "hk") -> Optional[Dict[str, Any]]:
    """从新浪财经拉取行情（API 模式）"""
    code = _sina_code(ticker, market)
    url  = f"https://hq.sinajs.cn/list={code}"
    try:
        resp = SESSION.get(url, timeout=8, headers=_SINA_HEADERS)
        resp.encoding = "gbk"
        data = _parse_sina_response(resp.text, market)
        if data:
            data["ticker"] = ticker
        return data
    except Exception as e:
        print(f"  [新浪API] {ticker} 失败: {e}")
        return None


# ---------------------------------------------------------------------------
# 3. 新浪财经 网页慢爬（最后备选，带随机延迟）
# ---------------------------------------------------------------------------

def fetch_sina_web(ticker: str, market: str = "hk") -> Optional[Dict[str, Any]]:
    """
    慢爬新浪财经行情页面（最后 fallback）
    解析页面 JSON 嵌入数据，加随机延迟避免封禁
    """
    if market == "hk":
        url = f"https://finance.sina.com.cn/realstock/company/{_sina_code(ticker, 'hk')}/nc.shtml"
    elif market == "us":
        url = f"https://finance.sina.com.cn/stock/usstock/{ticker.lower()}.shtml"
    else:
        return None

    # 随机延迟 1~3 秒，模拟人类行为
    delay = random.uniform(1.0, 3.0)
    print(f"  [新浪网页] 等待 {delay:.1f}s 后爬取 {url}")
    time.sleep(delay)

    try:
        headers = {
            **_SINA_HEADERS,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"

        # 从页面提取嵌入的行情 JSON
        # 新浪页面通常有 hq_str_hk02208="..." 或 var quote = {...} 格式
        text = resp.text

        # 尝试提取 hq_str_ 格式
        m = re.search(r'hq_str_[^=]+=\s*"([^"]+)"', text)
        if m:
            raw_fake = f'var x="{m.group(1)}"'
            data = _parse_sina_response(raw_fake, market)
            if data:
                data["ticker"] = ticker
                data["source"] = "新浪网页(慢爬)"
                return data

        # 尝试提取 JSON 格式
        m2 = re.search(r'"price"\s*:\s*"?([\d.]+)"?', text)
        if m2:
            current = float(m2.group(1))
            name_m  = re.search(r'"name"\s*:\s*"([^"]+)"', text)
            return {
                "ticker":        ticker,
                "name":          name_m.group(1) if name_m else ticker,
                "current_price": current,
                "source":        "新浪网页(慢爬/简化)",
                "fetched_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        print(f"  [新浪网页] 无法解析 {ticker} 页面结构")
        return None

    except Exception as e:
        print(f"  [新浪网页] {ticker} 失败: {e}")
        return None


# ---------------------------------------------------------------------------
# 主入口：多源 Fallback
# ---------------------------------------------------------------------------

def get_quote(ticker: str, market: str = "hk", slow_web: bool = False) -> Optional[Dict[str, Any]]:
    """
    统一行情接口，按优先级 fallback:
      腾讯财经 -> 新浪财经 API -> 新浪网页慢爬(可选)

    Args:
        ticker:   股票代码，如 "02208" / "NVDA"
        market:   "hk" / "us" / "sh" / "sz"
        slow_web: 是否启用网页慢爬作为最后手段

    Returns:
        行情字典 或 None
    """
    print(f"  [行情] 获取 {ticker} ({market.upper()})")

    # 1. 腾讯财经
    data = fetch_tencent(ticker, market)
    if data and data.get("current_price", 0) > 0:
        print(f"  ✅ 腾讯财经: {data['name']} = {data['current_price']}")
        return data

    # 2. 新浪财经 API
    print(f"  → 腾讯失败，尝试新浪财经...")
    data = fetch_sina(ticker, market)
    if data and data.get("current_price", 0) > 0:
        print(f"  ✅ 新浪财经: {data['name']} = {data['current_price']}")
        return data

    # 3. 新浪网页慢爬（可选）
    if slow_web:
        print(f"  → 新浪API失败，尝试网页慢爬...")
        data = fetch_sina_web(ticker, market)
        if data and data.get("current_price", 0) > 0:
            print(f"  ✅ 新浪网页: {data.get('name', ticker)} = {data['current_price']}")
            return data

    print(f"  ❌ 所有数据源均失败: {ticker}")
    return None


def batch_quotes(holdings: list, market: str = "hk",
                 slow_web: bool = False, delay: float = 0.5) -> Dict[str, Any]:
    """
    批量获取行情，加间隔避免频控
    holdings: [{"ticker": "02208", ...}, ...]
    """
    results = {}
    for i, h in enumerate(holdings):
        ticker = h.get("ticker", "")
        if not ticker:
            continue
        if i > 0:
            time.sleep(delay)
        results[ticker] = get_quote(ticker, market, slow_web)
    return results


# ---------------------------------------------------------------------------
# 与 portfolio.json 集成
# ---------------------------------------------------------------------------

def update_portfolio_cn(portfolio_path: str = "portfolio.json",
                        slow_web: bool = False) -> dict:
    """
    用腾讯/新浪数据更新 portfolio.json 中的港股持仓
    作为 Finnhub 的备选
    """
    with open(portfolio_path, "r") as f:
        portfolio = json.load(f)

    hk = portfolio["portfolios"]["hk_stocks"]
    holdings = hk["holdings"]

    print("=" * 60)
    print("📡 CN Finance Fetcher — 港股行情更新")
    print("=" * 60)

    updated = 0
    for holding in holdings:
        ticker = holding["ticker"]
        data   = get_quote(ticker, "hk", slow_web)
        if not data:
            continue

        old_price             = holding["current_price"]
        new_price             = data["current_price"]
        holding["current_price"] = new_price
        holding["current_value"]  = round(new_price * holding["shares"], 2)
        holding["today_change"]   = round(data.get("change", 0) * holding["shares"], 2)
        holding["pnl_percent"]    = round(
            (new_price - holding["cost_basis"]) / holding["cost_basis"] * 100, 2
        )
        holding["data_source"]    = data["source"]

        print(f"  {holding.get('name', ticker):12s}  "
              f"{old_price:.3f} → {new_price:.3f}  "
              f"({data['change_pct']:+.2f}%)")
        updated += 1

    # 更新汇总
    hk["total_current_value"]  = round(sum(h["current_value"] for h in holdings), 2)
    hk["today_total_change"]   = round(sum(h.get("today_change", 0) for h in holdings), 2)
    hk["total_pnl"]            = round(hk["total_current_value"] - hk["total_cost"], 2)
    hk["total_pnl_percent"]    = round(hk["total_pnl"] / hk["total_cost"] * 100, 2)

    portfolio["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(portfolio_path, "w") as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print(f"✅ 更新完成: {updated}/{len(holdings)} 只港股")
    print(f"   总市值: HKD {hk['total_current_value']:,.2f}")
    print(f"   今日盈亏: HKD {hk['today_total_change']:+,.2f}")
    print(f"   总盈亏: HKD {hk['total_pnl']:+,.2f} ({hk['total_pnl_percent']:+.2f}%)")
    return portfolio


# ---------------------------------------------------------------------------
# US 股票也可用（新浪 gb_ 前缀）
# ---------------------------------------------------------------------------

def get_us_quote_cn(ticker: str) -> Optional[Dict[str, Any]]:
    """
    用新浪财经获取美股行情（腾讯对美股覆盖较弱）
    ticker: "NVDA" / "AAPL" 等
    """
    return get_quote(ticker, market="us", slow_web=False)


# ---------------------------------------------------------------------------
# CLI 独立运行
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--us":
        # 测试美股
        for sym in ["NVDA", "RKLB", "QQQ"]:
            d = get_us_quote_cn(sym)
            if d:
                print(f"{sym}: ${d['current_price']}  {d['change_pct']:+.2f}%  [{d['source']}]")
    else:
        # 默认更新港股组合
        slow = "--slow" in sys.argv
        update_portfolio_cn(slow_web=slow)
