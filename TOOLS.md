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

### 美股基本面 / SEC filings（脚本，2026-05-16 加入）

**`fetch_us_filings.py`** — 直接对接 SEC EDGAR，**全免费、无需 API key**（仅需 User-Agent 标识身份）。覆盖 Financial Datasets 付费档才有的内容：

| 数据 | endpoint | 用法 |
|---|---|---|
| 最近 filings (10-K/10-Q/8-K) | submissions API | `python3 fetch_us_filings.py RKLB` |
| 指定表型 | submissions filter | `python3 fetch_us_filings.py RKLB --filings 10-K,10-Q` |
| XBRL 关键财务概念（营收/净利/现金/EPS 等 13 项）| companyfacts API | `python3 fetch_us_filings.py RKLB --financials` |
| Insider Form 4 | submissions filter | `python3 fetch_us_filings.py RKLB --form4` |
| 13F-HR（基金持仓） | submissions filter | `python3 fetch_us_filings.py BRK-A --13f` |
| 机器可读 JSON | 任一模式加 `--json` | `python3 fetch_us_filings.py RKLB --json` |

**注意**：
- 速率限制 **10 req/sec**（脚本默认 8/sec 留余量）；超量 SEC 会 403
- `SEC_USER_AGENT` 可放进 `.api_keys`（格式 `Name email@domain`），默认用 openclaw 标识
- ticker→CIK 映射本地缓存 7 天，免重复抓
- 非美股票（如港股 09988）无数据 → 返回 "CIK not found"
- 不替代 `fetch_us_stocks.py` 抓价格 — 这是**纯基本面/filings 补充**

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
- **`fetch_us_filings.py`**：SEC EDGAR 对接 — 10-K/10-Q/8-K filings、XBRL 财务概念、Form 4 insider、13F-HR；无需 API key；Mode 3 fundamental 深挖时用
- **`analyze_hk_stocks.py`**：港股完整分析 = Tencent→stooq→yfinance fallback + 恒指/恒科 + Finnhub 新闻 + 信号
- `check_portfolio.sh`：快速查看持仓

### 辅助
- **Scrapling**：自适应爬虫框架，绕过反爬（Cloudflare 等），支持 JS 渲染。`pip3 install scrapling --break-system-packages`。详见 `skills/scrapling/SKILL.md`
- `portfolio_monitor.py`：组合监控
- `portfolio_table.py` / `portfolio_visualization.py`：可视化

### 价格提醒 / 监控
**当前在用**：cron-driven WeChat report（不是常驻轮询）

**8 个 stock cron job** (位于 `~/.openclaw/cron/jobs.json`)：

| Job 名 | Schedule | 入口 |
|---|---|---|
| 港股开盘报告 | 09:30 HKT 工作日 | `hk-stock-analysis` Mode 6 |
| 港股午盘报告 | 12:00 HKT 工作日 | `hk-stock-analysis` Mode 6 |
| 港股午后快报 | 13:30 HKT 工作日 | `hk-stock-analysis` Mode 6 |
| 港股收盘报告 | 16:00 HKT 工作日 | `hk-stock-analysis` Mode 6 |
| 盘中盯盘 | 9-15 每 30 分 HKT 工作日 | `hk-stock-analysis` Mode 7 |
| 美股开盘报告 | 09:30 ET 工作日 | `us-stock-analysis` Mode 6 |
| 美股盘中盯盘 | 9-15 每 30 分 ET 工作日 | `us-stock-analysis` Mode 7 |
| 美股收盘报告 | 16:00 ET 工作日 | `us-stock-analysis` Mode 6 |

每个 cron prompt 已精简成"按 skill Mode 6/7 执行"+ 自包含 fallback 指令，改格式时**只改 SKILL.md 里的 Mode 段**，不动 jobs.json。

**改 cron prompt 的步骤**（如果真要改）：
```bash
cp ~/.openclaw/cron/jobs.json ~/.openclaw/cron/jobs.json.bak-$(date +%Y%m%d_%H%M%S)
python3 -c "import json; d=json.load(open('/root/.openclaw/cron/jobs.json')); ..."
```
不要手编辑 jobs.json — JSON 错误会让全部 9 个 job 停摆（包括 Memory Dreaming）。

**已停摆**（2026-03-19 后无运行）：
- `price_alert_monitor.py` — 上一代轮询架构，无 cron，代码里硬编码 NVDA/QQQ 等已清仓 ticker
- `monitor_state.json` / `monitor.log` — 同上

**已停摆**（2026-03-19 后无运行）：
- `price_alert_monitor.py` — 上一代轮询架构，无 cron，代码里硬编码 NVDA/QQQ 等已清仓 ticker
- `monitor_state.json` / `monitor.log` — 同上

### 已废弃（不作为调用入口，但作为参考代码可读）
> 这些脚本**不要直接调起来跑**当主路径，但里面的 URL、header、fallback 思路、解析片段在调试或场景超出现役脚本时仍有参考价值。
- `stock_analyzer.py` — 被 `analyze_us_stocks.py` + `analyze_hk_stocks.py` 取代；早期 fallback 顺序的来源
- `hk_stock_fetcher.py` — 已被 `analyze_hk_stocks.py` 内联；Tencent 解析参考
- `hk_monitor.py` / `hk_open_monitor.py` / `hk_ai_monitor.py` — 为已清仓的韩股链（07709/07747）写的，无现役作用；监控循环写法参考
- `final_analysis.py` / `deep_analysis.py` / `find_opportunities.py` / `monday_signal.py` — 实验性脚本，未集成进定时任务
- `multi_agent_stock_analysis.py` — 实验脚本

### TradingAgents/ — 已 clone 的 TauricResearch 多 agent 框架
**不当主路径，但 swarm-review skill 直接借用其 agent 角色设计。**
关键参考路径：
- `TradingAgents/tradingagents/agents/analysts/` — market / fundamentals / news / social_media 4 个 analyst 的 prompt 设计
- `TradingAgents/tradingagents/agents/researchers/` — bull / bear 对辩
- `TradingAgents/tradingagents/agents/risk_mgmt/` — aggressive / conservative / neutral debator
- `TradingAgents/tradingagents/dataflows/` — alpha_vantage 套件 + yfinance_news 实现参考（脚本里的 fallback 思路可对照）

需要重 LLM 编排的深度分析时可启动 `python main.py`（需 API key），日常用 swarm-review skill 走同样框架就够了。

---

## Skill 安装顺序（重要）

见 `skills-store-policy.md`。**先 `skillhub`（cn-optimized）再 `clawhub`（公开 registry）兜底**：

```bash
skillhub search <kw>         # 第一选择
skillhub install <slug>      # cn-optimized 源
# 不可用 / 无匹配 / 限流时 →
clawhub search <kw>
clawhub install <slug>
```

安装前列出 source / version / risk signal 给用户确认。

## Skill 路由表（什么场景用哪个）

| 场景 | 入口 skill | 备注 |
|---|---|---|
| "分析 RKLB" / "compare AAPL vs MSFT" / 美股个股问题 | `us-stock-analysis` | 4 模式（quick/technical/fundamental/full）+ sentiment mode 5 |
| "分析 00100" / "07226 怎么样" / "恒科今天" / 港股问题 | `hk-stock-analysis` | 4 模式 + 港股专属 sentiment（雪球/富途）+ 南向资金 |
| "看下持仓 / 节后操作 / 持仓有什么风险" | `portfolio-risk-review` | 单 pass、4 lens、快速可行动 |
| "深度复盘 / 持仓全面诊断 / 大幅调仓前" | `portfolio-swarm-review` | 3 tier（analyst→bull/bear→risk debate）+ confidence 评分，重，慢 |
| 教育性问题（"什么是 MACD"、"position sizing 怎么算"） | `trading`（clawhub 装的） | guardrails 重、不给具体买卖判断；具体判断走上面 4 个 |
| 抓需 JS 渲染 / 反爬的页面（雪球评论 / Futu 社区 / Reddit 深页） | `scrapling` | 配合上面的 stock-analysis Mode 5 调用 |
| Web 搜索（新闻 / X / 中文社区 / 政策） | `tavily-search` | 不要让模型自己改用 Yahoo/Google 临时拼搜索 |
| openclaw 升级后健康检查 / 磁盘膨胀 | `openclaw-tune` | 不动股票 |

⚠️ **不要做的 routing 错误**：
- `trading` skill 默认禁止"直接买卖建议" → 用户问"应该买不买" 时不走它，走 `us/hk-stock-analysis`（用户偏好已写在 MEMORY.md）
- 持仓问题不要走 `us-stock-analysis` 的 Full Report → 走 `portfolio-risk-review`（持仓视角）
- 单只股的分析也不要走 `portfolio-swarm-review`（杀鸡用牛刀）→ 走 `us/hk-stock-analysis` Mode 4

## 情绪面数据源速查

按市场和重要性顺序：

### 美股
1. **Finnhub news** —— `analyze_us_stocks.py` 默认拉取，主英文媒体 + 关键词情绪打分
2. **Tavily** —— 新闻 + X/Twitter trending（`node skills/tavily-search/scripts/search.mjs "{TICKER} sentiment" --topic news`）
3. **Reddit JSON**（无需 auth）—— r/wallstreetbets（散户动量）+ r/stocks（理性）：
   ```bash
   curl -sH "User-Agent: openclaw/1.0" "https://www.reddit.com/r/wallstreetbets/search.json?q={TICKER}&restrict_sr=1&sort=new&limit=25"
   ```
4. **scrapling** —— 上述源失败或要评论级深度

### 港股
1. **Finnhub news** —— 港股覆盖稀疏但能拿到 Reuters/Bloomberg/SCMP
2. **Tavily 中文搜索** —— 主要中文媒体 + 政策
3. **雪球 HK 评论区**（scrapling StealthyFetcher）—— `https://xueqiu.com/S/HK{TICKER}`，港股散户情绪核心
4. **富途牛牛社区**（scrapling）—— `https://www.futunn.com/stock/{TICKER}-HK`
5. **南向资金 净流入**（Tavily 搜当日）—— 港股大盘情绪锚

### 跨市场宏观情绪
- VIX（美股恐慌指数）—— Tavily 搜或脚本扩展
- HIBOR（港元流动性）—— Tavily 搜，HIBOR 升 = 港股估值压力
- 美债收益率 —— 影响成长股估值

---

## 维护建议
- 交易发生后：更新 `portfolio.json` + 当天 `memory/YYYY-MM-DD.md`
- 规则变化后：更新 `MEMORY.md`
- 持仓结构明显变化后：更新 `memory/current-portfolio-summary.md`
- 脚本数据源变化后：同步更新 `TOOLS.md` 与 `MEMORY.md`
