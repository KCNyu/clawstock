# Rick's Stock Analysis Tools

## 当前结构总览
- 权威持仓：`portfolio.json`
- 长期规则与偏好：`MEMORY.md`
- 投资工作流：`INVESTMENT_SOP.md`
- 当前持仓摘要：`memory/current-portfolio-summary.md`
- 每日复盘/交易日志：`memory/YYYY-MM-DD.md`
- 数据脚本（被 harness / 手动调用）：`scripts/data/`
- Harness 脚本（cron 调起）：`scripts/harness/`
- 历史/参考脚本：`scripts/legacy/`
- Dashboard 入口：`index.html` (落到 `kcnyu.github.io/clawock`)；数据 `assets/data/dashboard.json` 由 `scripts/data/build_dashboard.py` 聚合
- 快速查看：`check_portfolio.sh`

## 公共发布层（仓库 = `github.com/KCNyu/clawock`）

- Repo 是 **public**，含真实仓位（用户已知情授权）
- Dashboard live: https://kcnyu.github.io/clawock/ — 自动从 `assets/data/dashboard.json` 取数
- Briefs index: https://kcnyu.github.io/clawock/briefs.html — 自动列 `memory/*-pre-open.md`
- `_layouts/default.html` + `assets/dashboard.css` 给所有 markdown 页面统一样式；不要再加 jekyll-theme
- Pages 自动 build on push

### GitHub Actions 分工

| Workflow | 触发 | 写文件 | 备注 |
|---|---|---|---|
| `harness-regression.yml` | push to master | (read-only) | 每次 push 跑 schema/import 校验 |
| `weekly-health.yml` | 周日 23:00 UTC | (read-only) | 综合健康检查（含公网数据源活体） |
| `eod-archive.yml` | 周五 22:00 UTC | `memory/archive/eod-history.csv` | 每周持仓快照 audit trail |
| `sentiment-scan.yml` | 工作日 23:30 UTC | `assets/data/sentiment.json` | Reddit mention 统计 |

**没有 GH Action 写 `assets/data/dashboard.json`** — 那是 openclaw cron 的 postflight 独占。
其他 GH Action 只写各自专属文件，零冲突面。本地 cron 和 远端 Action 不会撞车。

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
python3 scripts/data/analyze_us_stocks.py   # 美股
python3 scripts/data/analyze_hk_stocks.py   # 港股
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
python3 scripts/data/analyze_us_stocks.py             # 完整分析（默认带新闻）
python3 scripts/data/analyze_us_stocks.py --no-news   # 跳过新闻（省 Finnhub 配额）
python3 scripts/data/analyze_us_stocks.py --no-fetch  # 用缓存价，只跑分析
python3 scripts/data/fetch_us_stocks.py               # 仅刷价格

# 港股（含恒指/恒科/P&L/Finnhub新闻/信号）
python3 scripts/data/analyze_hk_stocks.py             # 完整分析
python3 scripts/data/analyze_hk_stocks.py --no-fetch  # 用缓存价
python3 scripts/data/analyze_hk_stocks.py --no-news   # 跳过新闻
python3 scripts/data/analyze_hk_stocks.py --dry-run   # 不写文件
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

### 货币 / FX

铁律：**HKD + USD 不能直接相加** — 详见 `MEMORY.md § 数据规则 § 2`。

工具：
- `python3 scripts/data/fetch_fx.py --json` → `{"rate": 7.83, "source": "Frankfurter", ...}`
- 换算：`python3 scripts/data/fetch_fx.py --convert 10000 HKD USD`
- fallback：Frankfurter → exchangerate.host → Yahoo HKD=X；4h 本地缓存

### 美股基本面 / SEC filings（脚本，2026-05-16 加入）

**`scripts/data/fetch_us_filings.py`** — 直接对接 SEC EDGAR，**全免费、无需 API key**（仅需 User-Agent 标识身份）。覆盖 Financial Datasets 付费档才有的内容：

| 数据 | endpoint | 用法 |
|---|---|---|
| 最近 filings (10-K/10-Q/8-K) | submissions API | `python3 scripts/data/fetch_us_filings.py RKLB` |
| 指定表型 | submissions filter | `python3 scripts/data/fetch_us_filings.py RKLB --filings 10-K,10-Q` |
| XBRL 关键财务概念（营收/净利/现金/EPS 等 13 项）| companyfacts API | `python3 scripts/data/fetch_us_filings.py RKLB --financials` |
| Insider Form 4 | submissions filter | `python3 scripts/data/fetch_us_filings.py RKLB --form4` |
| 13F-HR（基金持仓） | submissions filter | `python3 scripts/data/fetch_us_filings.py BRK-A --13f` |
| 机器可读 JSON | 任一模式加 `--json` | `python3 scripts/data/fetch_us_filings.py RKLB --json` |

**注意**：
- 速率限制 **10 req/sec**（脚本默认 8/sec 留余量）；超量 SEC 会 403
- `SEC_USER_AGENT` 可放进 `.api_keys`（格式 `Name email@domain`），默认用 openclaw 标识
- ticker→CIK 映射本地缓存 7 天，免重复抓
- 非美股票（如港股 09988）无数据 → 返回 "CIK not found"
- 不替代 `scripts/data/fetch_us_stocks.py` 抓价格 — 这是**纯基本面/filings 补充**

### 说明

数据/缓存铁律 → 见 `MEMORY.md § 数据规则`。本节只补充 TOOLS-specific 实现细节：

- `prev_close` 由 Polygon `/prev` 历史接口独立获取（带日期戳）。回退链：Polygon历史 → API pc字段 → 保留现有（3天内） → 从dp%反推
- `prev_close_date` 字段同步写入 portfolio.json，可验证前收来自哪个交易日
- 脚本跑完后 `today_change` 字段即可直接信任，无需换算

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
- **`scripts/data/fetch_us_stocks.py`**：美股多 provider 抓取（7 路 fallback），自动写回 portfolio.json；prev_close 由 Polygon `/prev` 独立获取（带日期戳）
- **`scripts/data/analyze_us_stocks.py`**：美股完整分析 = 刷价格 + RSI-14/MA20/50 + Finnhub 新闻 + 信号
- **`scripts/data/fetch_us_filings.py`**：SEC EDGAR 对接 — 10-K/10-Q/8-K filings、XBRL 财务概念、Form 4 insider、13F-HR；无需 API key；Mode 3 fundamental 深挖时用
- **`scripts/data/fetch_fx.py`**：USDHKD 汇率（Frankfurter → exchangerate.host → Yahoo HKD=X 三路 fallback）；4h 本地缓存；`--convert AMT FROM TO` 直接换算。**HK + US 算 book total 必须先调它**
- **`scripts/data/analyze_hk_stocks.py`**：港股完整分析 = Tencent→stooq→yfinance fallback + 恒指/恒科 + Finnhub 新闻 + 信号
- `check_portfolio.sh`：快速查看持仓

### Cron harness 脚本（preflight + postflight 三明治）

所有 stock cron 都用同一套"preflight (确定性) → LLM (创造性) → postflight (校验)"模式。
确定性活强制脚本化执行；LLM 只做合成；postflight 自验证 + commit。

**Daily deep brief**（08:00 HKT cron）
- **`scripts/harness/brief_preflight.py`**：刷 US/HK 价 + FX + portfolio snapshot + HHI 算法 + SEC EDGAR (仅 `is_leveraged_etf=false`) + retrospective vs 上次 plan.json。输出 `memory/.tmp/brief-context-{date}.json`
- **`scripts/harness/brief_postflight.py`**：校验 `memory/{date}-pre-open.md` + `memory/{date}-plan.json`（段标记 / plan schema / HHI / FX / HKD+USD bug pattern）；pass/warn 自动 commit

**Mode 6 briefing**（HK 开/午/午后/收盘 + US 开/收盘 — 6 个 cron 共享）
- **`scripts/harness/report_preflight.py --market {hk|us} --phase {open|mid|pm|close}`**：跑 analyze_*.py + 抽信号 (WATCH/STOP/TRIM 计数) + 异动 (≥3% 涨跌) + 指数方向；输出 `memory/.tmp/report-context-{market}-{phase}-{date}.json`，含 `raw_wechat_block`（LLM verbatim 用）+ `title` + `needs_risk_section`
- **`scripts/harness/report_postflight.py --market {hk|us} --phase {phase}`**：校验三段标记 / 原始数据块 verbatim / 异动票必须被提及 / 长度 / 敷衍词；pass/warn 自动 commit portfolio.json

**Mode 7 intraday**（HK + US 盘中盯盘 — 2 个 cron 共享，每 30 分钟；HK 8 次/天，US 12 次/天，已错开阶段性报告）
- **`scripts/harness/intraday_preflight.py --market {hk|us}`**：跑 analyze_*.py + 异动检测 + `should_alert` 决策；输出 `memory/.tmp/intraday-context-{market}-latest.json`
- **`scripts/harness/intraday_postflight.py --market {hk|us}`**：校验 ▎我的看法 / 长度 / should_alert 触发时报告必须提异动票；**不 commit**（高频触发避免 commit log 刷屏）

**共通设计点**：
- preflight 输出 `raw_wechat_block` 字段，LLM **必须 verbatim 拷贝**（不改时间戳/数字），postflight 用首行匹配验证
- preflight 输出 `anomalies` 字段，LLM 必须在报告里至少提一个 anomaly 票
- postflight 输出 `wechat_prefix`（pass=空串，warn=黄 banner，fail=红 banner），LLM 拼到 WeChat 输出前
- 所有 context.json 都放 `memory/.tmp/`（gitignore 排除）

### 辅助
- **Scrapling**：自适应爬虫框架，绕过反爬（Cloudflare 等），支持 JS 渲染。`pip3 install scrapling --break-system-packages`。详见 `skills/scrapling/SKILL.md`
- **`scripts/data/build_dashboard.py`**：聚合 `portfolio.json` + `memory/snapshots/` + `memory/*-plan.json` → `assets/data/dashboard.json`。**brief/report postflight 自动调起**，手动也可以跑一次刷新 Pages 数据。
- **`scripts/data/update_portfolio.py`** / **`update_us_portfolio.js`**：手动调仓后写 portfolio.json 的辅助

### Cron map（**10 个 job 位于 `~/.openclaw/cron/jobs.json`**）

| Job 名 | Schedule | Mode | Preflight | Postflight |
|---|---|---|---|---|
| Memory Dreaming Promotion | 03:00 daily | (system) | — | — |
| 📊 盘前深度简报 | **08:00 HKT 工作日** | `daily-deep-brief` (全 swarm + FX + SEC EDGAR) | `brief_preflight.py` | `brief_postflight.py` |
| 港股开盘报告 | 09:30 HKT 工作日 | Mode 6 | `report_preflight.py --market hk --phase open` | `report_postflight.py --market hk --phase open` |
| 港股盘中盯盘 | 10-11,14-15 每 30 分 HKT 工作日（共 8 次，错开 09:30/12:00/13:30/16:00 报告） | Mode 7 | `intraday_preflight.py --market hk` | `intraday_postflight.py --market hk` |
| 港股午盘报告 | 12:00 HKT 工作日 | Mode 6 | `report_preflight.py --market hk --phase mid` | `report_postflight.py --market hk --phase mid` |
| 港股午后快报 | 13:30 HKT 工作日 | Mode 6 | `report_preflight.py --market hk --phase pm` | `report_postflight.py --market hk --phase pm` |
| 港股收盘报告 | 16:00 HKT 工作日 | Mode 6 | `report_preflight.py --market hk --phase close` | `report_postflight.py --market hk --phase close` |
| 美股开盘报告 | 09:30 ET 工作日 | Mode 6 | `report_preflight.py --market us --phase open` | `report_postflight.py --market us --phase open` |
| 美股盘中盯盘 | 10-15 每 30 分 ET 工作日（共 12 次，错开 09:30/16:00 报告） | Mode 7 | `intraday_preflight.py --market us` | `intraday_postflight.py --market us` |
| 美股收盘报告 | 16:00 ET 工作日 | Mode 6 | `report_preflight.py --market us --phase close` | `report_postflight.py --market us --phase close` |

所有 harness preflight/postflight 都在 `scripts/harness/`。Mode 6 / brief 的 postflight 会在 pass/warn 时
自动跑 `scripts/data/build_dashboard.py` 刷新 `assets/data/dashboard.json` 并一起 commit，保证 Pages 同步。

cron prompt 已精简成"按 skill 的 harness 4-step 跑"+ 自包含 fallback 指令，改格式时**只改 SKILL.md 里的 Mode 段**，不动 jobs.json。

**改 cron prompt 的安全步骤**：
```bash
cp ~/.openclaw/cron/jobs.json ~/.openclaw/cron/jobs.json.bak-$(date +%Y%m%d_%H%M%S)
python3 -c "import json; d=json.load(open('/root/.openclaw/cron/jobs.json')); ..."
```
不要手编辑 jobs.json — JSON 错误会让全部 10 个 job 停摆（包括 Memory Dreaming）。

### 已废弃（不作为调用入口，但作为参考代码可读）
> 这些脚本**不要直接调起来跑**当主路径，但里面的 URL、header、fallback 思路、解析片段在调试或场景超出现役脚本时仍有参考价值。
- `scripts/legacy/stock_analyzer.py` — 被 `scripts/data/analyze_us_stocks.py` + `analyze_hk_stocks.py` 取代；早期 fallback 顺序的来源
- `scripts/legacy/hk_stock_fetcher.py` — 已被 `analyze_hk_stocks.py` 内联；Tencent 解析参考
- `scripts/legacy/hk_monitor.py` / `hk_open_monitor.py` — 为已清仓的韩股链（07709/07747）写的，无现役作用；监控循环写法参考
- `scripts/legacy/portfolio_monitor.py` / `portfolio_table.py` / `portfolio_visualization.py` — 早期可视化/监控参考
- **完全删掉** (2026-05-16 大扫除)：`monday_signal.py` (含硬编码 key)、`api_retry_wrapper.py`、`baidu_search_wrapper.py`、`deep_analysis.py`、`final_analysis.py`、`find_opportunities.py`、`hk_ai_monitor.py`、`multi_agent_stock_analysis.py`、`price_alert_monitor.py`、`TradingAgents/` 整目录

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
1. **Finnhub news** —— `scripts/data/analyze_us_stocks.py` 默认拉取，主英文媒体 + 关键词情绪打分
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
