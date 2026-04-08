# 股票查询 API 与 Skills 整理（分享版）

这份文档整理了当前 workspace 里用于查询股票、更新持仓、分析组合的主要数据源、脚本和可复用工作流，方便分享给其他人直接照着搭。

---

## 1. 当前核心文件

- `portfolio.json`：权威持仓数据源
- `stock_analyzer.py`：主更新脚本，负责拉行情、更新价格、计算盈亏
- `MEMORY.md`：长期规则、fallback 约定、分析偏好
- `TOOLS.md`：工具总览和推荐工作流
- `memory/YYYY-MM-DD.md`：每日交易与分析日志

---

## 2. 推荐工作流

### 回答持仓/股价/组合问题时
按顺序读取：
1. `MEMORY.md`
2. `portfolio.json`
3. `memory/current-portfolio-summary.md`
4. 必要时读最近 `memory/YYYY-MM-DD.md`
5. **先拉最新价格，再分析**

### 更新价格
```bash
python3 stock_analyzer.py
```

### 快速查看持仓
```bash
bash check_portfolio.sh
```

---

## 3. 数据源与 fallback 规则

### A. 港股（HK）

#### 当前约定 fallback 链
1. **腾讯财经 Tencent Finance**，实时，当前首选
   - 接口：`https://qt.gtimg.cn/q=r_hkXXXXX`
   - 例子：`r_hk07709`
   - 备注：境外环境已验证可用

2. **东方财富 Eastmoney**，批量接口，适合一次拉多个标的
   - 接口：`https://push2.eastmoney.com/api/qt/ulist.np/get`
   - `secid` 规则：`116.XXXXXX`（6位补零）
   - 例子：`116.007709`

3. **stooq**，日线收盘备用
   - 接口：`https://stooq.com/q/d/l/?s=XXXX.hk&i=d`
   - 例子：`7709.hk`
   - 备注：非实时，更适合兜底

4. **Yahoo Finance / yfinance**，最后备选
   - 代码格式：`7709.HK`
   - 备注：有限流风险

#### 在 `stock_analyzer.py` 中的相关函数
- `get_quote_tencent_hk(code)`
- `get_hk_quotes_tencent_batch(codes)`
- `get_hk_quotes_eastmoney(codes)`
- `get_quote_stooq_hk(code)`
- `get_quote_yfinance(symbol)`
- `get_hk_quote(code)`（单票自动 fallback）
- `update_hk_portfolio_prices()`（组合批量更新）

---

### B. 美股（US）

#### 当前约定 fallback 链
1. **东方财富 Eastmoney**，批量接口，当前首选
   - 接口：`https://push2.eastmoney.com/api/qt/ulist.np/get`
   - `secid` 规则：
     - NASDAQ：`105.TICKER`
     - NYSE：`106.TICKER`
   - 例子：`105.NVDA`、`106.CRCL`

2. **Finnhub**
   - 接口：`https://finnhub.io/api/v1/quote?symbol={ticker}&token=...`
   - 用途：实时报价、公司资料、新闻

3. **Yahoo Finance / yfinance**
   - 用途：备用报价
   - 备注：易限流，不建议作为主线路

4. **Alpha Vantage**
   - 接口：`GLOBAL_QUOTE`
   - 备注：慢，适合兜底

5. **Polygon.io**
   - 代码里已接入，属于更后备的兜底路线

#### 特别说明
- 新浪/腾讯美股接口在境外环境常见 403 或不可用，当前策略里**不作为主线路**
- `stock_analyzer.py` 里虽然还有 `get_quote_sina_us()`，但工作流层面不建议依赖它

#### 在 `stock_analyzer.py` 中的相关函数
- `get_us_quotes_eastmoney(tickers)`
- `get_quote_finnhub(ticker)`
- `get_quote_alpha_vantage(ticker)`
- `get_quote_polygon(ticker)`
- `get_quote_yfinance(symbol)`
- `get_quote(ticker)`（单票 fallback）
- `update_us_portfolio_prices()`（组合批量更新）

---

### C. 韩股（KR）

当前规则主要记录在 `MEMORY.md`，适合做海力士/三星映射分析。

#### 当前约定 fallback 链
1. **Naver Finance polling API**，当前最稳
   - 接口：`https://polling.finance.naver.com/api/realtime/domestic/stock/<code>`
   - 例子：海力士 `000660`，三星 `005930`

2. **Naver Finance 页面解析**
   - 接口：`https://finance.naver.com/item/main.naver?code=<code>`

3. **Google Finance / MarketWatch / Investing 页面搜索**
   - 用于人工交叉验证

4. **Yahoo Finance / yfinance**
   - `000660.KS` / `005930.KS`
   - 最后备选

#### 备注
- 当前 workspace 主脚本还没有把韩股完全整合进 `stock_analyzer.py` 的统一更新流，但这套规则已经稳定可用，适合后续单独封装 skill 或脚本

---

## 4. API Keys 需求

`stock_analyzer.py` 会从 `.api_keys` 中读取：

- `FINNHUB_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `POLYGON_API_KEY`

说明：
- 港股查询很多场景下可以不依赖 key（Tencent / Eastmoney / stooq）
- 美股如果 Eastmoney 失效，Finnhub key 会非常有用
- Alpha Vantage / Polygon 属于兜底层

---

## 5. 当前脚本清单

### 核心
- `stock_analyzer.py`
  - 读取 `portfolio.json`
  - 拉取美股/港股最新价格
  - 更新当前价格、组合市值、浮盈亏
  - 输出持仓报告

- `hk_stock_fetcher.py`
  - 港股专项更新脚本

- `final_analysis.py`
  - 组合分析输出脚本

### 监控类
- `price_alert_monitor.py`
- `hk_monitor.py`
- `portfolio_monitor.py`
- `hk_open_monitor.py`
- `hk_ai_monitor.py`

### 展示类
- `portfolio_table.py`
- `portfolio_visualization.py`

### 研究/探索类
- `deep_analysis.py`
- `find_opportunities.py`
- `check_ai_stocks.py`
- `multi_agent_stock_analysis.py`
- `monday_signal.py`

---

## 6. 当前实际分析规则

### 必须遵守的规则
1. **每次问到持仓/股价，先拉最新数据，不直接用缓存旧价**
2. **必须走 fallback 链，失败立刻切下一个源**
3. **如果全部失败，要明确告诉用户“以下为旧数据”**
4. **获取到最新数据后，更新 `portfolio.json` 并 git commit**

### 持仓分析口径
- 直接分析**当前仓位**
- 用 `portfolio.json` 中的 `cost_basis` vs 最新价格算浮盈亏
- 一般**不追溯历史 trades** 做复杂流水分析
- 交易发生后，补记到 `memory/YYYY-MM-DD.md`

---

## 7. 适合分享给他人的 skill 方向

如果要给别人复用，我觉得最值得做成 skill 的有这几类：

### 1. `portfolio-price-refresh`
用途：
- 读取 `portfolio.json`
- 按市场自动调用 API fallback 更新价格
- 输出组合总览

核心能力：
- HK / US 多数据源 fallback
- 批量更新
- 自动写回 JSON

### 2. `hk-stock-quote`
用途：
- 查询港股单票或批量实时价
- 默认走 Tencent → Eastmoney → stooq → yfinance

适合：
- 港股投资者
- 做盘中 quick check

### 3. `us-stock-quote`
用途：
- 查询美股单票或批量价
- 默认走 Eastmoney → Finnhub → yfinance → Alpha Vantage

适合：
- 美股持仓分析
- 快速更新 watchlist

### 4. `cross-market-ai-chain`
用途：
- 分析美股存储链（MU/WDC）→ 韩股海力士/三星 → 港股映射 ETF
- 适合做 AI 硬件链联动分析

这类 skill 更像“研究工作流 skill”，不只是报价工具

---

## 8. 给别人复用时的最小落地方案

如果别人不想整套搬，只想快速搭一个能跑的版本，最低配置建议：

### 港股最小方案
- Tencent Finance
- Eastmoney
- stooq

### 美股最小方案
- Eastmoney
- Finnhub
- yfinance

### 文件结构最小方案
- `portfolio.json`
- `stock_analyzer.py`
- `.api_keys`

这样就足够做一个实用版持仓助手。

---

## 9. 实操建议

### 如果分享给普通投资者
重点强调：
- 先用 `portfolio.json` 管持仓
- 再用 `stock_analyzer.py` 更新价格
- 不要只依赖单一 API

### 如果分享给会折腾 OpenClaw / agent 的人
重点强调：
- 把 fallback 规则写进 skill
- 把 API key 读取集中在 `.api_keys`
- 把“更新价格 -> 写回持仓 -> 输出分析”做成统一工作流

---

## 10. 一句话总结

这套体系的关键不是某一个 API，而是：

**用 `portfolio.json` 做单一权威持仓源，用 `stock_analyzer.py` 做多数据源 fallback 更新，用固定工作流保证每次分析前都先拿到最新价格。**
