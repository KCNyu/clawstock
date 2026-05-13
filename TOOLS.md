# Rick's Stock Analysis Tools

## 当前结构总览
- 权威持仓：`portfolio.json`
- 长期规则与偏好：`MEMORY.md`
- 投资工作流：`INVESTMENT_SOP.md`
- 当前持仓摘要：`memory/current-portfolio-summary.md`
- 每日复盘/交易日志：`memory/YYYY-MM-DD.md`
- 美股完整分析：`analyze_us_stocks.py`
- 港股完整分析：`analyze_hk_stocks.py`
- 快速查看：`check_portfolio.sh`

## 推荐工作流

### 1. 回答投资问题
按顺序读取：
1. `MEMORY.md`
2. `portfolio.json`
3. `memory/current-portfolio-summary.md`
4. 需要时再读最近 `memory/YYYY-MM-DD.md`
5. 拉最新价格后再分析

### 2. 更新价格
```bash
python3 analyze_us_stocks.py   # 美股
python3 analyze_hk_stocks.py   # 港股
```

### 3. 快速查看持仓
```bash
bash check_portfolio.sh
```

---

## 数据源清单（当前约定）

### 港股 fallback 链（脚本实现，2026-05-13 修正）
1. **腾讯财经** `qt.gtimg.cn/q=r_hkXXXXX` — 主源，覆盖最全
2. **stooq.com** CSV — 同日 OHLCV，**注意**：新 IPO（如 00100 MINIMAX）无覆盖；prev_close 用 open 近似
3. **yfinance** — 经常被限速，最后兜底

⚠️ **东方财富 `push2.eastmoney.com` 从此服务器 502 不可达，已从链路移除**
⚠️ **00100 MINIMAX 没有可用 fallback** — Tencent 是唯一来源，必须保持工作

### 美股 & 港股脚本（推荐用法）

```bash
# 美股（含 RSI/MA/新闻/信号）
python3 analyze_us_stocks.py             # 完整分析（默认带新闻）
python3 analyze_us_stocks.py --no-news   # 跳过新闻（省 Finnhub 配额）
python3 analyze_us_stocks.py --no-fetch  # 用缓存价，只跑分析
python3 fetch_us_stocks.py               # 仅刷价格

# 港股（含恒指/恒科/P&L/Finnhub新闻/信号）
python3 analyze_hk_stocks.py             # 完整分析
python3 analyze_hk_stocks.py --no-fetch  # 用缓存价
python3 analyze_hk_stocks.py --no-news   # 跳过新闻
python3 analyze_hk_stocks.py --dry-run   # 不写文件
```

### 美股 fallback 链

**脚本内部 provider 顺序：**
1. **Nasdaq API** `api.nasdaq.com/api/quote/{TICKER}/info?assetclass=stocks|etf` — 无需 key，JSON，覆盖股票和 ETF ✅
2. **东方财富** `push2.eastmoney.com` — 批量 JSON，无需 key，`105.{TICKER}`（NASDAQ）/ `106.{TICKER}`（NYSE）
3. **Finnhub** — 需 `FINNHUB_API_KEY`
4. **Yahoo v8 API** `query1.finance.yahoo.com/v8/finance/chart/{TICKER}` — 无需 key，偶有限速
5. **yfinance** 库 — 无需 key，偶有限速
6. **Alpha Vantage** — 需 `ALPHA_VANTAGE_API_KEY`，慢（免费 25次/天）
7. **Polygon** — 需 `POLYGON_API_KEY`，返回前一日收盘价

**Claude 直接 web_fetch 时的顺序：**
1. CNBC `cnbc.com/quotes/{TICKER}` — 网页，快速可靠
2. 东方财富、Finnhub、Yahoo Finance

### 说明
- 分析持仓前，必须先获取最新价格，**不得直接使用 `portfolio.json` 的缓存价**
- 如果全部失败，必须明确说明是旧数据
- ⚠️ **2026-05-11 教训：曾用缓存价（RKLB $110 vs 实时 $118，RKLX $59 vs $73）导致盈利从 +$790 错写成 +$550**
- ⚠️ **2026-05-12 教训：live-quote API 的 `PreviousClose` 字段在收盘后会被更新成当日收盘价，导致 `prev_close == current_price`，`today_change = 0`，无法回答"今天亏多少"**
  - 修复：脚本现在额外调用 Polygon `/prev` 历史接口获取带日期戳的前收，回退链：Polygon历史 → API pc字段 → 保留现有（3天内） → 从dp%反推
  - `prev_close_date` 字段同步写入 portfolio.json，可验证前收来自哪个交易日
  - 脚本跑完后 `today_change` 字段即可直接使用，无需额外换算
- 新浪美股接口境外 403，跳过不试

---

## 当前持仓

**Single source of truth：`portfolio.json`**（不在此重复，避免漂移）

### 持仓结构特征（相对稳定）
- 风格激进，波动容忍度较高
- 港股风险集中在 `00100` MiniMax 和 `07226` 两倍恒科
- `03032/03033` 属于相对更稳的科技敞口
- 美股偏高弹性成长 + 杠杆短线仓
- 韩股已完全清仓（07709/07747/000660/005930 不追踪）

---

## 现有脚本梳理

### 核心（当前在用）
- **`fetch_us_stocks.py`**：美股多 provider 抓取（7 路 fallback），自动写回 portfolio.json；prev_close 由 Polygon `/prev` 独立获取（带日期戳）
- **`analyze_us_stocks.py`**：美股完整分析 = 刷价格 + RSI-14/MA20/50 + Finnhub 新闻 + 信号
- **`analyze_hk_stocks.py`**：港股完整分析 = Tencent→stooq→yfinance fallback + 恒指/恒科 + Finnhub 新闻 + 信号
- `check_portfolio.sh`：快速查看持仓

### 辅助
- **Scrapling**：自适应爬虫框架，绕过反爬（Cloudflare 等），支持 JS 渲染。`pip3 install scrapling --break-system-packages`。详见 `skills/scrapling/SKILL.md`
- `price_alert_monitor.py`：价格提醒
- `portfolio_monitor.py`：组合监控
- `portfolio_table.py` / `portfolio_visualization.py`：可视化

### 已废弃（请勿使用）
- `stock_analyzer.py` — 被 `analyze_us_stocks.py` + `analyze_hk_stocks.py` 取代
- `hk_stock_fetcher.py` — 已被 `analyze_hk_stocks.py` 内联
- `hk_monitor.py` / `hk_open_monitor.py` / `hk_ai_monitor.py` — 为已清仓的韩股链（07709/07747）写的，无现役作用
- `final_analysis.py` / `deep_analysis.py` / `find_opportunities.py` / `monday_signal.py` — 实验性脚本，未集成进定时任务
- `multi_agent_stock_analysis.py` / `TradingAgents/` — 实验目录

---

## 维护建议
- 交易发生后：更新 `portfolio.json` + 当天 `memory/YYYY-MM-DD.md`
- 规则变化后：更新 `MEMORY.md`
- 持仓结构明显变化后：更新 `memory/current-portfolio-summary.md`
- 脚本数据源变化后：同步更新 `TOOLS.md` 与 `MEMORY.md`
