---
name: daily-deep-brief
description: kcn 每个工作日 08:00 HKT 跑一次的盘前全 swarm 深度分析。完整 TradingAgents 3-tier (regime → 4 analysts → Bull/Bear → 3 risk voices → Judge) + 信心评分 + next-session plan + FX 换算 + SEC EDGAR fundamentals + diff vs 上次。**输出**：完整 markdown 落盘到 `memory/{date}-pre-open.md` + 完整版直接发 WeChat（plugin 16KB 单 chunk 上限够装；顶部加 ≤150 字 TL;DR 给手机第一屏）。和 portfolio-swarm-review 同等深度，但为日常自动化优化。**只在每日 8 点 cron 触发时使用；手动深度分析仍走 portfolio-swarm-review。**
---

# Daily Deep Brief (08:00 HKT, weekday)

8 点这个时点：HK 开盘前 ~90 分钟，US 已收盘 ~4 小时。盘前是 deep think 最好的窗口 —
有完整夜间消息面，没有盘中执行压力。

## Required reads (delta vs `AGENTS.md` baseline)

`AGENTS.md` 已经要求每个 session 都读 SOUL.md / USER.md / MEMORY.md / TOOLS.md / 当日 daily memory，**这里不重复**。仅追加：

1. `portfolio.json` — 持仓 ground truth
2. `memory/{昨天 YYYY-MM-DD}-pre-open.md` 如果存在 — 上次的 thesis 和 next-session plan，今天必须 diff
3. `memory/{昨天 YYYY-MM-DD}.md` 如果存在 — 用户手写笔记
4. `INVESTMENT_SOP.md` — 启动顺序参考

## Fresh data block (并行跑)

```bash
python3 /root/.openclaw/workspace/analyze_us_stocks.py            # US 7-route fallback + RSI/MA
python3 /root/.openclaw/workspace/analyze_hk_stocks.py            # HK Tencent → stooq → yfinance + 恒指 + 新闻 + 信号
python3 /root/.openclaw/workspace/fetch_fx.py --json              # ⚠️ FX rate，必须在算 book total 之前抓
```

对每个 **US 单股**（is_leveraged_etf=false，目前 RKLB / CRCL）额外跑：

```bash
python3 /root/.openclaw/workspace/fetch_us_filings.py {TICKER} --financials --json
```

XBRL 数据用来对照价格 — 没有这一步 fundamental 分析全是嘴炮。

## ⚠️ 货币铁律（核心，不能漏）

港币 + 美元 **不能直接相加**。所有 book-level 数字必须二选一：

- **USD-base**（推荐）：把 HK 浮盈亏 HKD / rate 换算到 USD，加上 US USD 浮盈亏
- **HKD-base**：把 US 浮盈亏 USD × rate 换算到 HKD，加上 HK HKD 浮盈亏

输出时必须**两个 view 都给**：

```
真实总浮盈亏: USD$X  ≈  HKD$Y   (USDHKD = {rate}, 来源 {source}, 抓取于 {timestamp})
  ├─ HK 段：HKD${a}  ≈  USD${a/rate}
  └─ US 段：USD${b}  ≈  HKD${b*rate}
```

历史教训：2026-05-16 那次深度分析"合计 -4,423"直接把 -4936 HKD 和 +513 USD 相加 → 数字毫无意义。kcn 当场指出。

## Regime detection（先跑，定调）

| Regime | 触发 | sizing 含义 |
|---|---|---|
| Trending up | 指数 ADX > 25, MA20 > MA50, RSI 50-70 | 杠杆可持，反弹时只看过热点（RSI > 75）减 |
| Trending down | 指数 ADX > 25, MA20 < MA50, 连续低低 | 杠杆 decay 加速，preferred cash，不加 |
| Range-bound | ADX < 20, RSI 在 50 附近震荡 | T-only，fade extremes |
| Volatile / regime change | 高方差，MA 矛盾，sentiment 混乱 | 缩规模、放宽止损、等清晰 |

**两个市场分开判**（kcn book 是港股 + 美股 mismatch 是常态，必须独立打 regime tag）：
- US: 用 QQQ / SOX 走势
- HK: 用 ^HSTECH / 恒指

## Tier 1 — 4 个分析师角度（独立、并行思考）

输出形式：**一张大表**（票 × 角度），不是 4 个分散段。每个角度只给最重要的 1 行。

| 票 | Market | Fundamentals | Sentiment | Cross-Market |
|---|---|---|---|---|
| {ticker} | 距成本 / RSI / MA stance / 1 行评级 | XBRL latest period 或 ETF underlying 评级 | 短期情绪 / 散户温度 / news 异动 | 跟随 / 背离 / 断链 |

Fundamentals 数据**优先用 SEC EDGAR**（fetch_us_filings 已经跑过），其次 web search peer/历史 P/E。  
Sentiment：US 看 r/wallstreetbets + Tavily；HK 看雪球评论区 + 富途社区 + 南向资金。  
Cross-Market：纳指→恒科链路当日是否工作；US 隔夜 vs HK 即将开盘的链关系。

## Tier 2 — Bull vs Bear（必须有真分歧）

两段，各 80-120 字。Bull 用 Tier 1 给的数据组装"持有 + 加仓"案；Bear 用 Tier 1 数据组装"减仓 + 砍仓"案。**至少在 1 个仓位上观点不同** — 完全一致说明辩论失败，要重做。

引用：每方至少引 2 个具体 Tier 1 数据点（不是 vibes）。

## Tier 3 — 3 个 Risk Voice + Judge

| Voice | 立场 | 必须做的 |
|---|---|---|
| Aggressive | 抓 upside，conviction 名字满仓 | 引用 Bull 最强点；指出 Conservative 错过了什么 |
| Conservative | 保本 derisk | 引用 Bear 最强点；指出 Aggressive 低估的尾部 |
| Neutral | 拍中线 | **对每个争议票必须拍一边**，"看情况"是失败答 |

### Judge（最终合成）

权重规则：
- kcn 风险偏好 = **激进**（USER.md），Aggressive 默认略多权重
- **但** trending down regime 启动时 Conservative 权重 +1 档
- 数据 stale 任何一段 → 涉及票 confidence -10pp

输出 5 个 action bucket：

1. **Hold and watch** — thesis 完好，无操作
2. **Trim on rebound** — thesis 弱化，等强势
3. **T-only** — 不留隔夜信念，fade 极值
4. **Add only on trigger** — 明确触发条件
5. **Cut** — thesis 破，挂卖单（用得少）

每个 bucket 内：ticker + 1 行具体理由 + 1 行触发价/条件。

## Confidence calls

每个主要 action 给 0-100% 信心 + 1 行简单理由：

| 区间 | 校准 |
|---|---|
| 80-100% | 4 个 analyst 全部同向，Bull/Bear 强点收敛，数据新鲜，regime 清晰 |
| 60-79% | 大部分同向，1 个 analyst 异议，regime 清晰 |
| 40-59% | analyst 分裂，regime 混乱，或 1 段数据 stale |
| 20-39% | 信号冲突，疑似 regime change，多段数据 stale |
| < 20% | 不要按这个 read 行动；等清晰 |

## Next-Session Plan（一定要可交易，不是观察清单）

格式：
```
1. {时点 + 时区}: {具体观察 / 触发}
2. {时点 + 时区}: ...
```

包含：
- HK 开盘前 09:00 HKT 查什么消息
- HK 开盘后 09:30 HKT 关注哪个票的什么价位
- US 盘前 16:00 HKT 之前查什么
- US 开盘后 21:30 HKT 关注什么
- Book-level metric 红线（例：港股浮亏到 X% 触发 forced derisk）

## Retrospective vs 上次 plan（Detailed P&L 模拟）

**这是 skill 的核心学习闭环**。设计来自 TradingAgents v0.2.4 的 persistent decision memory — 让 daily brief 从"预测引擎"变成"学习引擎"。

### Step 1: 找上次 plan.json

寻找 `memory/{*-plan.json}` 中**日期 < 今天**的最新文件（cron 工作日运行，周二的 retrospective 是周一的 plan；周一的是上周五的 plan）。

```bash
ls /root/.openclaw/workspace/memory/*-plan.json | sort | awk -v today=$(date +%Y-%m-%d) '$0 < "/root/.openclaw/workspace/memory/"today"-plan.json"' | tail -1
```

### Step 2: 对每个 plan action 算结果

读 plan.json 的每个 action，对照今天的 portfolio.json（已经 by cron step 1 刷过价）：

| 字段 | 怎么算 |
|---|---|
| **触发** | 比较 trigger_type：`open` 永远触发；`price_above`/`price_below` 看 day_high/day_low 是否突破；`index_breakdown` 看 ^HSTECH / SOX index |
| **执行偏离** | portfolio.json 当前 shares vs 昨日（仓位增/减说明实际操作） |
| **模拟 P&L** | `(trigger_price - today_close) × planned_size` — 若 cut/trim 是正向；若 add 是反向 |
| **机会成本** | 未执行 trigger 的 simulated PnL = "如果听 plan 本可以 ±$X" |
| **conf 校准** | 高 conf 的 trigger 是否真的发生；累积一周看 calibration |

### Step 3: Retrospective 输出段

在 brief 顶部（TL;DR 之后，Header 之前）插入：

```
▎昨日 plan 兑现度（{上次 plan 日期}）

| Action | Plan | 实际 | 模拟 ±$ | 评 |
|---|---|---|---|---|
| Cut 50% ROBN @开盘 | 砍 20股 | 砍 N股 @${px} | ±$X vs hold | ✓/✗/⊘ |
| Trim 30% 07226 @4.10 | 减1860股 | 未触发 (high 4.05) | -HK$Y (机会成本) | ✗ trigger 过紧 |
| ... | | | | |

▎Confidence calibration (累计)
- conf 80%+: N/M 触发 (X%)
- conf 60-79%: ...
- conf <60%: ...

▎Lesson (1-2 行)
{什么 trigger 设过紧/松；什么 thesis 站住/破；哪个 confidence 区间过自信}
```

评符号：✓=执行准、✗=未触发或反向、⊘=trigger 设了但 plan 本身就是中性
机会成本可能为正（trigger 未触发 = 错过 alpha）或负（trigger 未触发 = 躲过损失）

### Step 4: 写 plan.json（给明天的 retrospective 用）

skill 每次跑完，**除了 markdown 报告**，还要写 `memory/{今日 YYYY-MM-DD}-plan.json`：

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
    },
    {
      "ticker": "07226",
      "bucket": "trim_on_rebound",
      "size_pct": 30,
      "size_shares": 1860,
      "trigger_type": "price_above",
      "trigger_price": 4.10,
      "trigger_condition": "反弹至 4.10 (+5%)",
      "confidence": 0.78,
      "rationale": "杠杆 decay + trending down + 28.8% 单点风险"
    }
  ],
  "watch_levels": {
    "hstech_breakdown": 4800,
    "soxl_breakdown_pct": -4,
    "book_force_derisk_usd": -300
  }
}
```

**trigger_type 取值**：
- `open` — 开盘任意价（实际等于一定触发）
- `price_above` — 价格突破上方（trigger_price 为目标价）；模拟用 day_high 判断
- `price_below` — 价格跌破下方；模拟用 day_low 判断
- `index_breakdown` — 指数破位（trigger_condition 说明哪个指数 + 哪个值）
- `event` — 事件型（财报/公告），需手动判断
- `manual` — 完全靠人判断，不参与 calibration

这一段是 skill 的自我学习机制，**缺这两步（读 + 写 plan.json）daily 价值减半**。

## 输出（完整版直接发 WeChat + 落盘）

**WeChat plugin 上限**：`@tencent-weixin/openclaw-weixin` 单 chunk 16,384 bytes (16KB)；超过会自动按 UTF-8 边界 split 成多 chunk **不会丢内容**。完整深度 brief 一般 ~12KB（中英混合 ~8K 字符），**一次发完整版完全够装**，不需要做 compact 压缩。

### 输出格式

第一段 **TL;DR ≤150 字**（手机第一屏 actionable）：

```
📊 盘前深度简报｜{日期 周X} 08:00 HKT  (USDHKD={rate})

▎TL;DR
Book: USD${total} ({pct}%) | HK leg {hk}HKD | US leg {us}USD
今日 3 个动作：
1. {ticker} {action} {trigger} (conf {%})
2. ...
↓ 完整报告 ↓
```

第二段开始是**完整 markdown**（与 `memory/{date}-pre-open.md` 同内容），按以下结构：

- Header（regime US/HK 分开 + FX rate + book USD/HKD 双视角）
- Tier 1 大表（4 analyst 角度合并）
- Tier 2 Bull vs Bear（2 段，必须真分歧）
- Tier 3 Aggressive/Conservative/Neutral 三段 + Judge 5 bucket
- Confidence calls 表
- Next-session plan（可交易触发）
- Diff vs 上次 reconciliation

### 落盘 + commit

完整 markdown 同步写到 `memory/{YYYY-MM-DD}-pre-open.md`（不带 TL;DR 段，因为 TL;DR 是为 WeChat 第一屏，落盘版用 markdown 自带的 # Header 结构）。

```bash
git -C /root/.openclaw/workspace add memory/{YYYY-MM-DD}-pre-open.md portfolio.json
git -C /root/.openclaw/workspace commit -m "memory: daily deep brief {YYYY-MM-DD}"
```

### 备注（旧版 compact 模式已废弃）

之前设计 600 字 compact 是基于"WeChat 字数有限"误判。实测 plugin 单 chunk 16KB / 完整版 ~12KB，无需压缩。手机端通过 TL;DR + 滚动看 detail。落盘版仍是 markdown journal 用途。

## Style rules

- 表格优先（3+ 数据点必表格化）
- ⚠️ stale 任何数据必前置标注
- 没有"小心地"、"建议关注"这种废话 — 拍 buckets，拍价位
- 每个 claim 钉到具体 ticker + 数字，没有泛论
- Bull/Bear/Aggressive/Conservative 必须真的不同观点
- Judge 不重复 Bull/Bear，是合成不是复述
- **FX 换算永远显式标注 source + timestamp**
- 微信版不能 > 700 字（手机能滚完）；完整版无字数限制但每段紧凑
