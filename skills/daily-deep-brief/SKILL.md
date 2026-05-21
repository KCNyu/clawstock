---
name: daily-deep-brief
description: kcn 每个工作日 08:00 HKT 跑一次的盘前全 swarm 深度分析。harness 化：`scripts/harness/brief_preflight.py` 跑所有确定性步骤（刷价 / FX / snapshot / HHI / SEC EDGAR / retrospective），LLM 只做 swarm 创造性（Tier 1/2/3/Judge），`scripts/harness/brief_postflight.py` 验证 + commit。**输出**：完整 markdown 落盘 `memory/{date}-pre-open.md` + 结构化 `memory/{date}-plan.json` + 完整版发 WeChat（plugin 16KB 单 chunk 够装；顶部 ≤150 字 TL;DR 给手机第一屏）。**只在每日 8 点 cron 触发时使用；手动深度分析仍走 portfolio-swarm-review。**
---

# Daily Deep Brief (08:00 HKT, weekday)

8 点这个时点：HK 开盘前 ~90 分钟，US 已收盘 ~4 小时。盘前是 deep think 最好的窗口 —
有完整夜间消息面，没有盘中执行压力。

## Harness 架构（不可越权）

```
┌────────────────────┐     ┌───────────────┐     ┌────────────────────┐
│ scripts/harness/brief_preflight.py │ ──► │ LLM (你 / Rick)│ ──► │ brief_postflight.py│
│  (确定性 + 幂等)   │     │  (Tier 1/2/3) │     │   (验证 + commit)  │
└────────────────────┘     └───────────────┘     └────────────────────┘
   刷价/FX/snapshot/         读 context.json        校验 markdown +
   HHI/EDGAR/retro           写 markdown +          plan.json schema
                             plan.json
```

**为什么这样分**：之前完全交给 LLM，模型可能漏快照、漏 HHI、漏 FX、漏 retrospective。
确定性步骤交给脚本（一定执行，无遗漏）；LLM 只做"分析综合"这个不能脚本化的部分。

## 6-step 流程（严格按顺序）

### Step 1: 跑 preflight（一行命令搞定所有确定性活）

```bash
python3 /root/.openclaw/workspace/scripts/harness/brief_preflight.py
```

这一步内部做了：

1. `scripts/data/analyze_us_stocks.py` — US 价格刷新（7-route fallback + RSI/MA）
2. `scripts/data/analyze_hk_stocks.py` — HK 价格刷新（Tencent → stooq → yfinance + 恒指 + 信号）
3. `scripts/data/fetch_fx.py --json` — USDHKD 实时汇率（Frankfurter → exchangerate.host → Yahoo）
4. `cp portfolio.json memory/snapshots/{date}.json` — 每日快照（longitudinal 基础设施）
   - **为什么**：`portfolio.json` 是滚动覆盖的 ground truth，每次刷价就丢前一刻状态。
     有 snapshot 历史才能做 Rolling P&L 曲线 / Alpha vs benchmark / Drawdown 分析 / Position 变化追溯。
   - ⚠️ **不可补做** — 每过一天少一份永远拿不回来的数据。
5. **HHI / Top2 集中度算法**（HK + US leg 分开）
6. **SEC EDGAR fundamentals** — 对每个 `is_leveraged_etf=false` 的 US 单股跑 `scripts/data/fetch_us_filings.py`
   - 杠杆 ETF 检测启发式（name 关键词）：'倍', 'Direxion', 'T-Rex', 'Defiance', 'ProShares',
     '2X Long', '3X Long', 'Daily Target'
   - 当前实际跑 EDGAR 的票：RKLB / CRCL（其他 5 个 US 持仓都是杠杆 ETF）
7. **Retrospective**：读 prior `memory/*-plan.json`（日期 < 今天的最新），对每个 action 算
   trigger 是否触发 + 模拟 P&L + confidence calibration

输出：`memory/.tmp/brief-context-{date}.json` —— 所有数据准备好的单一 JSON。

### Step 2: 读 context.json

```bash
cat /root/.openclaw/workspace/memory/.tmp/brief-context-$(date +%Y-%m-%d).json
```

context.json 关键字段：
- `prices_refreshed_at` / `fx`（`rate`, `source`, `fetched_at`）
- `book` — `usd_total_pnl`, `hkd_total_pnl`, `hk_leg_hkd`, `us_leg_usd`（FX 已换算）
- `concentration` — `{hk: {hhi, top2_pct, weights, verdict}, us: {...}}`
- `edgar_summaries` — 单股最新 quarter 财报关键数字
- `retrospective` — 上次 plan.json 每个 action 的触发结果 + 模拟 P&L

### Step 3: Swarm 分析（你的创造性工作）

按下面这个 3-tier 流程做分析。所有数字**只能从 context.json 取**，不要凭空造。

#### Required reads (delta vs `AGENTS.md` baseline)

`AGENTS.md` 已要求每个 session 都读 SOUL.md / USER.md / MEMORY.md / TOOLS.md / 当日 daily memory，**这里不重复**。仅追加：

1. `portfolio.json` — 持仓 ground truth（preflight 已刷过价）
2. `memory/{昨天 YYYY-MM-DD}-pre-open.md` 如果存在 — 上次 thesis 和 next-session plan
3. `memory/{昨天 YYYY-MM-DD}.md` 如果存在 — 用户手写笔记
4. `INVESTMENT_SOP.md` — 启动顺序参考

#### Regime detection（先跑，定调）

| Regime | 触发 | sizing 含义 |
|---|---|---|
| Trending up | 指数 ADX > 25, MA20 > MA50, RSI 50-70 | 杠杆可持，反弹时只看过热点（RSI > 75）减 |
| Trending down | 指数 ADX > 25, MA20 < MA50, 连续低低 | 杠杆 decay 加速，preferred cash，不加 |
| Range-bound | ADX < 20, RSI 在 50 附近震荡 | T-only，fade extremes |
| Volatile / regime change | 高方差，MA 矛盾，sentiment 混乱 | 缩规模、放宽止损、等清晰 |

**两个市场分开判**（kcn book 是港股 + 美股 mismatch 是常态）：
- US: 用 QQQ / SOX 走势
- HK: 用 ^HSTECH / 恒指

#### Tier 1 — 4 个分析师角度（独立思考、合并成一张大表）

| 票 | Market | Fundamentals | Sentiment | Cross-Market |
|---|---|---|---|---|
| {ticker} | 距成本 / RSI / MA stance / 1 行评级 | EDGAR latest period 或 ETF underlying | 散户温度 / news 异动 | 跟随 / 背离 |

- Fundamentals 优先用 EDGAR（preflight 已抓），其次 web search peer/历史 P/E
- Sentiment：US 看 r/wallstreetbets + Tavily；HK 看雪球 + 富途 + 南向资金
- Cross-Market：纳指→恒科链路当日是否工作；US 隔夜 vs HK 即将开盘

#### Tier 2 — Bull vs Bear（必须有真分歧）

两段，各 80-120 字。Bull 用 Tier 1 数据组装"持有 + 加仓"案；Bear 用 Tier 1 数据组装"减仓 + 砍仓"案。**至少在 1 个仓位上观点不同** — 完全一致说明辩论失败。

引用：每方至少引 2 个具体 Tier 1 数据点（不是 vibes）。

#### Tier 3 — 3 个 Risk Voice + Judge

| Voice | 立场 | 必须做的 |
|---|---|---|
| Aggressive | 抓 upside | 引用 Bull 最强点；指出 Conservative 错过了什么 |
| Conservative | 保本 derisk | 引用 Bear 最强点；指出 Aggressive 低估的尾部 |
| Neutral | 拍中线 | **对每个争议票必须拍一边**，"看情况"是失败答 |

**Judge** 权重规则：
- kcn 风险偏好 = **激进**（USER.md），Aggressive 默认略多权重
- **但** trending down regime 启动时 Conservative 权重 +1 档
- 数据 stale 任何一段 → 涉及票 confidence -10pp

输出 **5 个 action bucket**（也是 plan.json 的 `bucket` 字段）：

| bucket | 含义 |
|---|---|
| `cut` | thesis 破，挂卖单 |
| `trim_on_rebound` | thesis 弱化，等强势 |
| `hold_and_watch` | thesis 完好，无操作 |
| `t_only` | 不留隔夜信念，fade 极值 |
| `add_only_on_trigger` | 明确触发条件后加仓 |

每个 bucket 内：ticker + 1 行具体理由 + 1 行触发价/条件。

#### Strategy frame menu — Judge 段必须显式选 1-3 个 per action

让 Judge 明示哪个 strategy frame 在驱动每个 action（traceability，错了能反推），从下面 8 个里选：

| Frame | 触发条件举例 |
|---|---|
| `momentum` | MA 多头排列 / 量价齐升 / 新高 + 成交放量 |
| `mean_reversion` | RSI > 75 / < 25 / 偏离布林带 +2σ |
| `breakout` | 突破前高 / 关键阻力位 + 放量确认 |
| `relative_strength` | 跑赢/输 benchmark > 3pp（peer 涨自己跌也归此） |
| `earnings_setup` | 财报前后 5d / 预期 vs 实际 surprise |
| `sentiment_shift` | F&G 拐点 / 新闻情绪 5d 翻转 / 异常 short interest |
| `technical_breakdown` | 跌破 200MA / 跳空缺口 / 头肩顶 |
| `sector_rotation` | 同板块 peer 强自己弱（或反之） |

格式：

```
▎Judge — strategy frames

| Ticker | Action | Frame | Detail |
|---|---|---|---|
| SOXL | trim_on_rebound | technical_breakdown + relative_strength | 跌破 200MA + 跑输 NVDA -8pp |
| 00100 | hold_and_watch | sentiment_shift | F&G 从 fear 转 neutral |
| RKLB | cut | mean_reversion | RSI 78 + 浮+82% |
```

**禁止**：模糊"综合判断"/"基本面看好"。每个 action 必须落到具体 frame + 数值。

#### Confidence calls

每个主要 action 给 0-100% 信心 + 1 行简单理由：

| 区间 | 校准 |
|---|---|
| 80-100% | 4 个 analyst 全部同向，Bull/Bear 强点收敛，数据新鲜，regime 清晰 |
| 60-79% | 大部分同向，1 个 analyst 异议，regime 清晰 |
| 40-59% | analyst 分裂，regime 混乱，或 1 段数据 stale |
| 20-39% | 信号冲突，疑似 regime change，多段数据 stale |
| < 20% | 不要按这个 read 行动；等清晰 |

#### Retrospective markdown 模板

把 context.json 的 `retrospective` 字段渲染成下面这段，**插在 brief 顶部**（TL;DR 之后，Header 之前）：

```
▎昨日 plan 兑现度（{上次 plan 日期}）

| Action | Plan | 实际 | 模拟 ±$ | 评 |
|---|---|---|---|---|
| Cut 50% ROBN @开盘 | 砍 20股 | 砍 N股 @${px} | ±$X vs hold | ✓/✗/⊘ |
| Trim 30% 07226 @4.10 | 减1860股 | 未触发 (high 4.05) | -HK$Y (机会成本) | ✗ trigger 过紧 |

▎Confidence calibration (累计)
- conf 80%+: N/M 触发 (X%)
- conf 60-79%: ...
- conf <60%: ...

▎Lesson (1-2 行)
{什么 trigger 设过紧/松；什么 thesis 站住/破；哪个 confidence 区间过自信}
```

评符号：✓=执行准、✗=未触发或反向、⊘=trigger 设了但 plan 本身就是中性。
机会成本可能为正（trigger 未触发 = 错过 alpha）或负（trigger 未触发 = 躲过损失）。

#### ▎同行扫描 (REQUIRED — postflight 校验)

**preflight 给了 `peer_scan` 字段**，每个持仓有 listed_peers（带 pct_1d / pct_5d）+ private_peers（待 IPO 名单）。

格式：

```
▎同行扫描

| 持仓 | 主题 | 今日 self | 最强同行 | 差距 | 判断 |
|---|---|---|---|---|---|
| 00100 MINIMAX | HK AI 大模型 | -6.6% | 02273 智云健康 -0.2% | +6.4pp | ⚠️ 题材弱但同行更强 — 个股 alpha 在掉 |
| 07226 2x恒科 | HSTECH 杠杆 | -5.2% | 00700 腾讯 +0.3% | +5.5pp | ⚠️ 杠杆放大 underlying 弱势 — 减仓换 1x |
| ... | | | | | |

私域同行追踪（仅信息层）：
- 智谱 Zhipu D 轮估值 220 亿
- 月之暗面 Kimi 用户数 ...
```

**判断模板**（必给一个）：
- 题材+ 自己+ → "alpha 抓住了"
- 题材+ 自己- → "考虑切换：peer 比我强"
- 题材- 自己- → "持有合理，等题材轮回"
- 题材- 自己+ → "稀有，珍惜"

**如果出现 ⚠️ 切换信号 → Tier 3 Judge 给 rotation trigger**（例："00100 反弹至 800 减 20 股，换入 0020 商汤")。

#### ▎Confidence 自校准 (REQUIRED if `self_calibration.samples >= 5`)

context.json 有 `self_calibration` 字段含 Brier 30d + 每个 bucket 实际胜率 + 信心分桶实际率。

格式：
```
▎Confidence 校准

过去 30 天 Brier = X.XXX (good/marginal/poor)
- cut bucket: N 次, win rate Y%, 平均报 confidence Z% → 校准差距 +/- Wpp
- ...

本次报 confidence 时考虑:
- 你过去 70-80% 信心实际只赢 X% → 这次类似情境的我会调到 Y%
```

如果 self_calibration.samples < 5，这段写 "校准窗口未填满（N/5），跳过"。

**注意**：calibration 只计 `followed=true` 的 plan actions（kcn 真按 plan 执行了的）。`followed=unknown`（默认）或 `false`（看到 plan 但忽略）的 row 不进 brier 计算。
kcn 标记方式：`python3 scripts/data/mark_followed.py YYYY-MM-DD TICKER BUCKET [--no]`

#### Next-Session Plan（可交易，不是观察清单）

格式：
```
1. {时点 + 时区}: {具体观察 / 触发}
2. {时点 + 时区}: ...
```

包含：
- HK 开盘前 09:00 HKT 查什么消息
- HK 开盘后 09:30 HKT 关注哪个票什么价位
- US 盘前 16:00 HKT 之前查什么
- US 开盘后 21:30 HKT 关注什么
- Book-level metric 红线（例：港股浮亏到 X% 触发 forced derisk）

### Step 4: 写两份输出文件

#### A. Markdown 报告 → `memory/{YYYY-MM-DD}-pre-open.md`

结构（**postflight 会校验这些段标记**，缺哪个 fail）：

- `# Header`（regime US/HK 分开 + FX rate + book USD/HKD 双视角）
- `## ▎仓位明细` —— HK + US 各一张 7 列 markdown 表 `代码 | 股 | 成本 | 现价 | 今日 | 浮% | 浮$`（与 Mode 6/7 cron 完全一致；数据从 context.json 的 `portfolio.portfolios.{hk,us}_stocks.holdings` 直接取，**只列 shares>0 的**。2026-05-21 起的 visual-width-aware 渲染推荐 import `scripts.data._wechat_table.render_holdings_table`，省得手算 CJK 对齐）
- `## Retrospective`（来自 context.json 的 retrospective）
- `## Tier 1` 大表
- `## Tier 2` Bull vs Bear
- `## Tier 3` Aggressive/Conservative/Neutral + Judge
- `## ▎同行扫描` peer rotation matrix (uses `peer_scan` from context)
- `## Confidence` 表
- `## ▎Confidence 校准` self-calibration (uses `self_calibration` from context, if samples ≥ 5)
- `## Next-Session` plan

必须包含的内容关键词（postflight 检查）：
- "HHI" — 集中度段
- "USDHKD" 或 "FX" 或 "汇率" — FX 段
- 不能出现 "合计 -4423" / "合计 -4,423" 这种 HKD+USD 直接相加的历史 bug

#### B. 结构化 plan → `memory/{YYYY-MM-DD}-plan.json`

postflight 严格 schema 校验：

```json
{
  "date": "2026-05-18",
  "fx_rate_usdhkd": 7.8315,
  "fx_source": "Frankfurter",
  "regime": {"us": "trending-up", "hk": "trending-down"},
  "book": {
    "usd_total_pnl": -117.0,
    "hkd_total_pnl": -918.0,
    "hk_leg_hkd": -4936.0,
    "us_leg_usd": 513.0
  },
  "actions": [
    {
      "ticker": "ROBN",
      "bucket": "cut",
      "size_pct": 50,
      "size_shares": 20,
      "trigger_type": "open",
      "trigger_price": null,
      "trigger_condition": "周一开盘任意价",
      "confidence": 0.82,
      "rationale": "HOOD Q1 26 earnings miss + crypto rev -47%"
    }
  ],
  "watch_levels": {
    "hstech_breakdown": 4800,
    "soxl_breakdown_pct": -4,
    "book_force_derisk_usd": -300
  }
}
```

合法 enum：
- `bucket` ∈ {`cut`, `trim_on_rebound`, `hold_and_watch`, `t_only`, `add_only_on_trigger`}
- `trigger_type` ∈ {`open`, `price_above`, `price_below`, `index_breakdown`, `event`, `manual`}
- `confidence` ∈ [0.0, 1.0]

**trigger_type 详解**（决定 retrospective 怎么算触发）：

| 值 | 含义 | 模拟触发逻辑 |
|---|---|---|
| `open` | 开盘任意价 | 永远触发（trigger_price 一般 null） |
| `price_above` | 价格突破上方 | `day_high >= trigger_price` |
| `price_below` | 价格跌破下方 | `day_low <= trigger_price` |
| `index_breakdown` | 指数破位 | trigger_condition 字段说明哪个指数 + 哪个值 |
| `event` | 事件型（财报/公告） | 手动判断，不进 calibration 统计 |
| `manual` | 完全靠人判断 | 不参与 calibration |

### Step 5: 跑 postflight（验证 + commit）

```bash
python3 /root/.openclaw/workspace/scripts/harness/brief_postflight.py
```

输出 JSON：
```json
{
  "status": "pass|warn|fail",
  "issues": [...],
  "wechat_prefix": "...",
  "commit_ok": true,
  "commit_msg": "committed"
}
```

- `pass` — 全部 OK，已 `git commit`
- `warn` — 有非 critical 问题（≤4 个），已 commit 但标 `(validation warnings)`
- `fail` — 缺文件/JSON 解析错/critical 字段缺失，**不 commit**

### Step 6: 发 WeChat

把 postflight 输出的 `wechat_prefix`（warn/fail 时是警告 banner，pass 时是空串）拼到完整 brief 前面，发到 WeChat。

```
{wechat_prefix}{完整 markdown，第一段是 ≤150 字 TL;DR}
```

**TL;DR 段格式**（手机第一屏 actionable，仅 WeChat 版有，落盘版没有）：

```
📊 盘前深度简报｜{日期 周X} 08:00 HKT  (USDHKD={rate})

▎TL;DR
Book: USD${total} ({pct}%) | HK leg {hk}HKD | US leg {us}USD
今日 3 个动作：
1. {ticker} {action} {trigger} (conf {%})
2. ...
↓ 完整报告 ↓
```

WeChat plugin (`@tencent-weixin/openclaw-weixin`) 单 chunk 16,384 bytes (16KB)；完整 brief ~12KB **一次发完整版完全够装**，不需要 compact 压缩。

## Style rules

- 表格优先（3+ 数据点必表格化）
- ⚠️ stale 任何数据必前置标注
- 没有"小心地"、"建议关注"这种废话 — 拍 buckets，拍价位
- 每个 claim 钉到具体 ticker + 数字，没有泛论
- Bull/Bear/Aggressive/Conservative 必须真的不同观点
- Judge 不重复 Bull/Bear，是合成不是复述
- **FX 换算永远显式标注 source + timestamp**（context.json 里已有）

## 集中度阈值表（解读 context.json `concentration` 字段）

### 算法（preflight 已经算了，这里只是参考）

对每个 leg（HK / US 分开）：
1. weight = `current_value / leg_total_current_value`
2. **HHI** = Σ weight² （0-1，越高越集中）
3. **Top 2 concentration** = 最大两仓 weight 之和

### 阈值

| HHI | Top 2 | 状态 |
|---|---|---|
| < 0.15 | < 40% | 健康 ✅ |
| 0.15-0.25 | 40-60% | 偏集中，可接受 |
| 0.25-0.40 | 60-75% | 集中风险 ⚠️ |
| > 0.40 | > 75% | 危险集中，单一事件可炸 book 🔴 |

### 输出格式（加在 book 段后，必填）

```
▎集中度风险 (2026-05-16 实测)
HK: HHI 0.418 🔴 危险 | 00100 57.2% + 07226 28.8% = Top2 86.0%
   → 单一事件风险高（00100 财报雷 / 07226 流动性问题）
   → 若 00100 或 07226 单日 -15%，HK book 立即 -8.5% 到 -12.9%
US: HHI 0.171 偏集中 | SOXL 22.2% + ROBN 21.1% = Top2 43.3%
   → 多仓分散但 SOXL 3x 杠杆 + ROBN 2x 杠杆双高仓需注意
```

历史教训：港股 book 双仓集中 86% 是 2026-05-16 之前 brief **漏报的盲点** — preflight 现在
强制算这个，brief 必须显式引用 `concentration.{hk,us}.verdict`。

## ⚠️ 货币铁律（context.json 已换算，但你输出时仍要双视角）

港币 + 美元 **不能直接相加**。book 段必须**两个 view 都给**：

```
真实总浮盈亏: USD${book.usd_total_pnl}  ≈  HKD${book.hkd_total_pnl}
   (USDHKD = {fx.rate}, 来源 {fx.source}, 抓取于 {fx.fetched_at})
  ├─ HK 段：HKD${book.hk_leg_hkd}  ≈  USD${book.hk_leg_hkd / fx.rate}
  └─ US 段：USD${book.us_leg_usd}  ≈  HKD${book.us_leg_usd * fx.rate}
```

历史教训：2026-05-16 那次"合计 -4,423"直接把 -4936 HKD 和 +513 USD 相加 → 毫无意义。kcn 当场指出。
