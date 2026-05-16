# 股票查询 API 与 Skills 整理（分享版）

这份文档整理了 kcn workspace 里查询股票、更新持仓、分析组合的主要数据源、脚本、skill 和工作流。设计为**可独立分享**——别人按本文搭一套类似 setup 就能跑。

最后更新：2026-05-16。Workspace 本身仍是单一事实来源；本文是面向外部的快照。

---

## 0. 一分钟概览

```
持仓 (portfolio.json)
   ↓
脚本 (analyze_us_stocks.py / analyze_hk_stocks.py)
   ↓ 7-route fallback (US) / 3-route fallback (HK)
   ↓ 写回 portfolio.json
   ↓
Skill (us-stock-analysis / hk-stock-analysis / portfolio-risk-review / portfolio-swarm-review)
   ↓ 包装分析逻辑（Mode 1-7）
   ↓
WeChat / 对话 (cron 触发 Mode 6/7 推送；用户对话走 Mode 1-5)
```

**核心约定**：
- 永远走脚本，不允许 raw curl / WebFetch / yfinance 当主源
- 永远先实时取价，不用 `portfolio.json` 里的缓存价回答盈亏
- 失败必须明说，禁止静默用旧数据

---

## 1. 当前核心文件

| 文件 | 角色 |
|---|---|
| `portfolio.json` | 权威持仓数据源（含 cost / shares / current_price / today_change / prev_close_date 等） |
| `analyze_us_stocks.py` | 美股全套分析（价格 + RSI/MA + Finnhub 新闻 + 信号） |
| `analyze_hk_stocks.py` | 港股全套分析（价格 + 恒指/恒科基准 + 新闻 + 信号） |
| `fetch_us_stocks.py` | 美股仅刷价格（不带分析），可指定 ticker |
| `MEMORY.md` | 长期规则、铁律、用户偏好、已知陷阱 |
| `TOOLS.md` | 数据链 / skill 路由 / 情绪面源 / cron 路由的总入口 |
| `AGENTS.md` | agent 启动时必读，每次 session 入口 |
| `INVESTMENT_SOP.md` | 投资类问题的标准启动顺序 |
| `memory/current-portfolio-summary.md` | 当前活跃 ticker 摘要（不替代 portfolio.json） |
| `memory/YYYY-MM-DD.md` | 每日交易/复盘日志 |
| `memory/_TEMPLATE.md` | daily memory 模板 |

---

## 2. 推荐工作流

### 用户问个股 / 持仓 / 加减仓 / 美股港股
1. 读 `MEMORY.md` 拿铁律
2. 读 `portfolio.json` 拿持仓
3. 读 `memory/current-portfolio-summary.md` 拿活跃 ticker
4. 必要时读最近 1-3 篇 `memory/YYYY-MM-DD.md`
5. **跑脚本**取最新价：`analyze_us_stocks.py` / `analyze_hk_stocks.py`
6. 按 skill Mode 1-5 输出分析（见 §5）
7. 重要操作后更新 `portfolio.json` + 当天 `memory/YYYY-MM-DD.md` + git commit

### 仅刷价格
```bash
python3 analyze_us_stocks.py --no-news  # US 全持仓刷价 + 跳过新闻
python3 fetch_us_stocks.py RKLB SOXL    # US 指定 ticker
python3 analyze_hk_stocks.py --no-news  # HK 全持仓
```

### 微信简报（cron 自动触发）
8 个 cron job 自动跑：港股开/午/午后/收 + 盘中盯盘 + 美股开/盘中/收。详见 §6。

---

## 3. 数据源与 fallback 规则

### A. 港股（HK）— 3 路 fallback

脚本内部顺序（`analyze_hk_stocks.py` / 内置）：

1. **腾讯财经 Tencent**（实时，首选，覆盖最全）
   - 接口：`https://qt.gtimg.cn/q=r_hkXXXXX`，例：`r_hk00100`
   - 编码：`gbk`
   - **00100 MINIMAX 等新 IPO 只能用此源**，没有兜底

2. **stooq.com**（CSV，同日 OHLCV）
   - 接口：`https://stooq.com/q/d/l/?s=XXXX.hk&i=d`
   - **caveat**：新 IPO 无覆盖；`prev_close` 用 `open` 近似

3. **yfinance**（最后兜底）
   - 代码：`XXXX.HK`
   - 经常被限速

**❌ 已从链路移除**：
- **东方财富** `push2.eastmoney.com` — 从这台服务器 502 不可达（旧文档 / 旧脚本仍提及，请忽略）
- **AAStocks / 富途网页** — 反爬严重，不值得维护

### B. 美股（US）— 7 路 fallback

脚本内部顺序（`fetch_us_stocks.py`）：

1. **Nasdaq API** ✅ 首选 — `api.nasdaq.com/api/quote/{TICKER}/info?assetclass=stocks|etf`
   - 无 key、自动识别股票/ETF、2026-05 全持仓 7/7 验证通过
2. **东方财富** `push2.eastmoney.com`（美股可达）— `105.{T}`(NASDAQ) / `106.{T}`(NYSE/ARCA)
3. **Finnhub**（需 `FINNHUB_API_KEY`）
4. **Yahoo v8 API** `query1.finance.yahoo.com/v8/finance/chart/{T}`
5. **yfinance** 库
6. **Alpha Vantage**（需 key，免费 25/天）
7. **Polygon**（需 key，返回前一日收盘价兜底）

**prev_close 独立链**（2026-05-12 新增解决收盘后 `PreviousClose` 污染）：
- Polygon `/v2/aggs/ticker/{T}/prev` 拿带交易日日期戳的前收
- → API 的 pc 字段 → 保留现有 prev_close（3 天内）→ 从 dp% 反推 → 最终兜底 pc=c

**❌ 已永久跳过**：新浪美股接口（境外 403）

### C. 韩股（KR）— 已清仓不追踪

`07709 / 07747 / 000660 / 005930` 全部清仓（2026-05-05），脚本里的 KR 代码可作为参考但不在现役持仓。

---

## 4. API Keys 需求

`.api_keys` 文件（**不入 git**）：

```
FINNHUB_API_KEY=...
ALPHA_VANTAGE_API_KEY=...
POLYGON_API_KEY=...
```

- 没 key 也能跑：Nasdaq + Eastmoney + Yahoo + yfinance 都不需要 key
- 加 key 后多 3 路兜底 + 新闻

---

## 5. Skills（按场景路由）

| 场景 | Skill | Mode |
|---|---|---|
| "分析 AAPL" / 美股个股 | `us-stock-analysis` | 1-5（Quick / Technical / Fundamental / Full / Sentiment） |
| "分析 00100" / 港股个股 | `hk-stock-analysis` | 1-5（含港股专属 Mode 4 Sector + Mode 5 雪球/富途） |
| 持仓快速复盘 | `portfolio-risk-review` | 4-lens 单 pass |
| 持仓深度调仓前 | `portfolio-swarm-review` | TradingAgents 3-tier（regime → 4 analyst → bull/bear → risk debate → judge） |
| WeChat 简报（开/午/收） | `{us,hk}-stock-analysis` | Mode 6 |
| WeChat 盘中盯盘（30 分一次） | `{us,hk}-stock-analysis` | Mode 7 |
| 教育性问题 | `trading`（第三方） | guardrails 重，不给具体买卖判断 |

---

## 6. Cron 自动化（WeChat 推送）

8 个 stock-related cron job：

| 时段 | Schedule | Skill Mode |
|---|---|---|
| 港股开盘 | 09:30 HKT 工作日 | hk Mode 6 |
| 港股午盘 | 12:00 HKT 工作日 | hk Mode 6 |
| 港股午后 | 13:30 HKT 工作日 | hk Mode 6 |
| 港股收盘 | 16:00 HKT 工作日 | hk Mode 6 |
| HK 盘中盯盘 | 9-15 每 30 分 HKT | hk Mode 7 |
| 美股开盘 | 09:30 ET 工作日 | us Mode 6 |
| 美股盘中盯盘 | 9-15 每 30 分 ET | us Mode 7 |
| 美股收盘 | 16:00 ET 工作日 | us Mode 6 |

cron prompt 全部精简成"按 skill Mode N 执行"+ 自包含 fallback。改格式只需改 SKILL.md 里的 Mode 段，不动 jobs.json。

推送通道：`openclaw-weixin`。

---

## 7. 情绪面数据源（Mode 5 调用顺序）

### 美股
1. Finnhub news（脚本内置） — 主英文媒体 + 关键词打分
2. Tavily（`skills/tavily-search/scripts/search.mjs "{TICKER} sentiment" --topic news --days 3`）
3. Reddit JSON（免 auth）：
   ```bash
   curl -sH "User-Agent: openclaw/1.0" \
     "https://www.reddit.com/r/wallstreetbets/search.json?q={T}&restrict_sr=1&sort=new&limit=25"
   ```
4. Scrapling 兜底深度抓取

### 港股
1. Finnhub news（覆盖稀疏但有 Reuters/Bloomberg/SCMP）
2. Tavily 中文搜索
3. **雪球 HK 评论区**（核心，scrapling StealthyFetcher）：`https://xueqiu.com/S/HK{TICKER}`
4. **富途牛牛社区**（scrapling）：`https://www.futunn.com/stock/{TICKER}-HK`
5. 南向资金（Tavily 搜当日数据）

---

## 8. 工具栈

| 工具 | 用途 |
|---|---|
| Scrapling | 反爬绕过、JS 渲染、雪球/富途/Reddit 深页抓取 |
| Tavily | AI 优化的 web 搜索（新闻 / X / 中文社区 / 政策） |
| Finnhub | 公司新闻、英文媒体（已集成进脚本） |
| TradingAgents | TauricResearch 多 agent 框架（已 clone，swarm-review 借其角色设计） |

---

## 9. 别人想自己搭一套的最小步骤

1. clone workspace（去掉 `.api_keys` / `*.bak` / `.openclaw/`）
2. 准备 `.api_keys` 三个 key（可选）
3. 装 deps：`pip3 install scrapling --break-system-packages`，节点：`npm i -g @fly-ai/flyai-cli`（如需 Tavily 这里其实是 tavily-search skill）
4. 改 `portfolio.json` 为自己持仓
5. 跑一次 `analyze_us_stocks.py` / `analyze_hk_stocks.py` 验证
6. 装 openclaw + 配 cron jobs（按本文 §6 时间表）
7. AGENTS.md / SOUL.md / USER.md / IDENTITY.md 改成自己身份

---

## 10. 已废弃（不要再用）

| 脚本 / 文件 | 为什么 |
|---|---|
| `stock_analyzer.py` | 被 `analyze_us_stocks.py` + `analyze_hk_stocks.py` 取代 |
| `hk_stock_fetcher.py` / `hk_monitor*.py` | 已并入新脚本 / 为已清仓韩股链写的 |
| `price_alert_monitor.py` | 上一代轮询，2026-03 后停摆 |
| `final_analysis.py` / `deep_analysis.py` / `find_opportunities.py` / `monday_signal.py` | 实验脚本未集成 |
| `multi_agent_stock_analysis.py` | 实验，被 portfolio-swarm-review skill 替代 |
| 东方财富港股接口 | 此服务器 502 |
| 新浪美股接口 | 境外 403 |

这些文件**作为参考代码可读**（旧 fallback 思路），但不要当主路径调起来。
