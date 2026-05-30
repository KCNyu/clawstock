# MEMORY.md - Rick's Long-Term Memory

## 用户偏好

### 持仓分析风格
- **直接分析当前持仓**：用 `portfolio.json` 成本 vs 实时价计算盈亏
- 忽略 `trades` 字段的历史操作，focus 当前仓位
- 简洁直接，不交代背景
- **风险偏好：激进型**，可用现金约 15万人民币（≈$20,500 USD）
- **重点：港股**（持仓、节奏、机会），美股作为补充观察
- 表格优先，能用结构化展示就不用大段文字

### 投资问题工作流
凡是问到 `持仓` / `portfolio` / `美股` / `港股` / `加仓/减仓`，按顺序读：
1. `portfolio.json`（权威持仓）
2. `memory/current-portfolio-summary.md`（ticker 列表）
3. 最近 1-3 篇 `memory/YYYY-MM-DD.md`
4. 工作流细节见 `INVESTMENT_SOP.md`

---

## ⚠️ 数据规则（铁律 — 本文件是唯一权威）

**每次问持仓/股价/盈亏，先实时抓取，再回答。**

### 1. 不用缓存价
- **禁止用 portfolio.json 的 `current_price` 计算盈亏** — 那是上次更新的旧数据
- 必须先跑 `scripts/data/analyze_{us,hk}_stocks.py`（fallback 链详情见 `TOOLS.md` § 数据源清单）
- 所有源均失败 → 明确说"数据获取失败，以下为旧数据"，**禁止静默使用**
- 数据成功后 → 更新 `portfolio.json` + git commit
- 教训：2026-05-11 用缓存价 RKLB 写成 $110 vs 实时 $118，盈利 +$790 错写成 +$550

### 2. FX 铁律 — HKD + USD 不能直接相加
- 港股 book 用 HKD，美股 book 用 USD — **绝不直接相加**
- 所有 book-level 数字必须**双视角**：USD-base + HKD-base，显式标注 rate / source / fetched_at
- 工具：`python3 scripts/data/fetch_fx.py --json` （3 路 fallback，4h 缓存）
- 教训：2026-05-16 deep brief 把 -4936 HKD + +513 USD = -4423 直接相加 → 数字毫无意义

### 3. 已知数据坑
- **00100 MINIMAX 只有 Tencent 一个源**，新 IPO 其他源没数据；Tencent 失败必须明说
- 收盘后 live-quote API 会把 `PreviousClose` 更新为当日收盘价，导致 `today_change = 0`；脚本已修（Polygon `/prev` 独立拉前收 + dp% 反推兜底），`today_change` 字段可直接信任
- **盘后 closed fetch（20:00+ ET）撞 Nasdaq 杠杆 ETF 报价坑**：`lastSalePrice` 停在前一日旧价、`PreviousClose` 反装当日真实收盘 → 价格错位一日 + `today_change` 反号（2026-05-29 MSFU/PLTU 被记成大跌实为大涨）。识别：活跃美股全部 `open==high==low==current` 退化报价。修法见 `memory/openclaw-us-postclose-stale-price-swap.md`（重抓自愈 + Nasdaq netChange 补 today_change + refresh_today_snapshot）
- 新浪美股接口境外 403，跳过不试

---

## 脚本与降级 curl 的关系

**默认走脚本**（`scripts/data/analyze_us_stocks.py` / `scripts/data/analyze_hk_stocks.py` / `scripts/data/fetch_us_stocks.py`），它们封装了 provider 顺序、URL pattern、Eastmoney 前缀、prev_close 独立链、各种字段污染兜底——这些是反复踩坑攒下来的，能用就别绕。

**脚本不覆盖时可以 curl，但要先学再 curl：**
- 场景：查非持仓 ticker / 指数成分 / 突发数据源切换 / 调试 fallback 某一路
- 步骤：先 grep / 打开相关脚本，看里面的 URL、header、解析片段、fallback 顺序，再决定 curl 怎么写
- 即使是 `TOOLS.md` 标"已废弃"的脚本（`scripts/legacy/stock_analyzer.py` / `scripts/legacy/hk_stock_fetcher.py` / `hk_monitor*.py` 等），**作为参考代码仍然可以读**，里面有早期 fallback 思路和被淘汰原因的线索
- 永远跳过：新浪美股接口（境外 403）

**Why:** "瞎拉数据"是只看官方文档闭眼写 curl，会重新踩 PreviousClose 污染、Eastmoney 前缀、Sina 境外 403、yfinance 限速这些坑；"自主退化"是脚本里已经写明白的东西先学完，curl 只用来填脚本没覆盖的边缘场景。

---

## 时区
- 港股：HKT 09:30-12:00 / 13:00-16:00（北京时间同）
- 美股：ET 09:30-16:00（北京时间 21:30 ~ 次日 04:00）
- 北京时间 21:39 = 美股刚开盘，不是收盘
- 北京时间 16:02 = 港股刚收盘

---

## 关键市场联动
- 油价↓（地缘缓和）↔ 加密/科技涨
- CRCL：GENIUS Act 稳定币法案推进，相对独立于大盘
- 港股核心驱动：恒科指数方向 + 个股逻辑（00100 AI、02208 风电政策）

---

## OpenClaw CLI 注意事项

### `openclaw cron` / `gateway status` 等子命令会卡死
- **原因**：通过 WebSocket RPC 连接 gateway(:18789)，在 agent exec 沙箱里无法完成 auth 握手
- **解决**：
  - 查 cron → 直接读 `~/.openclaw/cron/jobs.json`
  - 查 gateway → `curl http://127.0.0.1:18789/health`
  - 查 dreaming → `jobs.json` 里找 `managed-by=memory-core`

---

## 持仓数据
- **单一来源：`portfolio.json`**，不在此维护副本
- ticker 列表：`memory/current-portfolio-summary.md`（提高检索命中）

## Promoted From Short-Term Memory (2026-05-20)

<!-- openclaw-memory-promotion:memory:memory/2026-05-12.md:10:13 -->
- | 代码 | 名称 | 收盘价 | 今日涨跌 | 浮动盈亏 | |------|------|--------|----------|----------| | 00100 | MINIMAX-W | 690.0 | -6.38% | -7,969.8 HKD | | 02208 | 金风科技 | 16.78 | -0.83% | +1,078.4 HKD | [score=0.873 recalls=0 avg=0.620 source=memory/2026-05-12.md:10-13]
<!-- openclaw-memory-promotion:memory:memory/2026-05-12.md:14:16 -->
- | 03032 | 恒生科技ETF | 5.060 | -0.59% | -69 HKD | | 07226 | XL二南方恒科 | 4.104 | -1.11% | -1,606.9 HKD | | 03033 | 南方恒生科技 | 4.970 | -0.56% | -170 HKD | [score=0.873 recalls=0 avg=0.620 source=memory/2026-05-12.md:14-16]

## Promoted From Short-Term Memory (2026-05-21)

<!-- openclaw-memory-promotion:memory:memory/2026-05-14.md:8:11 -->
- | 代码 | 名称 | 现价 | 涨跌 | 浮盈 | |---|---|---|---|---| | 00100 | MINIMAX | 855.0 | ▲4.5% | +3.9% | | 02208 | 金风科技 | 15.85 | ▼9.4% | +12.5% | [score=0.889 recalls=0 avg=0.620 source=memory/2026-05-14.md:8-11]
<!-- openclaw-memory-promotion:memory:memory/2026-05-14.md:12:14 -->
- | 03032 | 恒生科技E | 5.09 | ▲0.3% | -5.8% | | 07226 | XL二南方 | 4.152 | ▲0.5% | -4.8% | | 03033 | 南方恒生科 | 5.0 | ▲0.2% | -2.7% | [score=0.889 recalls=0 avg=0.620 source=memory/2026-05-14.md:12-14]
<!-- openclaw-memory-promotion:memory:memory/2026-05-14.md:16:16 -->
- **总市值** HK$89,400 | **浮盈** +1,124 (+1.3%) | **今日** +1,703 [score=0.889 recalls=0 avg=0.620 source=memory/2026-05-14.md:16-16]
<!-- openclaw-memory-promotion:memory:memory/2026-05-14.md:19:19 -->
- ⚠️ 02208 金风科技：今日 -9.4%，需关注是否消息面异动 [score=0.889 recalls=0 avg=0.620 source=memory/2026-05-14.md:19-19]

## Promoted From Short-Term Memory (2026-05-22)

<!-- openclaw-memory-promotion:memory:memory/2026-05-14.md:5:5 -->
- **恒指** 26,452 ▲0.24% | **恒科** 5,110 ▲0.33% [score=0.889 recalls=0 avg=0.620 source=memory/2026-05-14.md:5-5]

## Promoted From Short-Term Memory (2026-05-28)

<!-- openclaw-memory-promotion:memory:memory/2026-05-22-0239.md:15:17 -->
- "chat_id": "o9cq80-hGTruM-OSs8kNmDOtLVZI@im.wechat", "message_id": "openclaw-weixin:1779387377128-998d269b", "timestamp": "Fri 2026-05-22 02:15 GMT+8" [score=0.883 recalls=0 avg=0.620 source=memory/2026-05-22-0239.md:15-17]
<!-- openclaw-memory-promotion:memory:memory/2026-05-22-0239.md:21:22 -->
- 你去github看看openclaw5.19 cron有没有人反馈 assistant: 找到了！今天刚提交的 bug： [score=0.883 recalls=0 avg=0.620 source=memory/2026-05-22-0239.md:21-22]
<!-- openclaw-memory-promotion:memory:memory/2026-05-22-0239.md:24:24 -->
- **#85052 — Gateway heap OOM: cron runtime contexts retain sessions.json and skillsSnapshot.prompt** [score=0.883 recalls=0 avg=0.620 source=memory/2026-05-22-0239.md:24-24]

## Promoted From Short-Term Memory (2026-05-29)

<!-- openclaw-memory-promotion:memory:memory/2026-05-23-0218.md:9:9 -->
- assistant: Postflight 给了 warn（长度超软上限），但内容完整。直接发。 [score=0.891 recalls=0 avg=0.620 source=memory/2026-05-23-0218.md:9-9]
<!-- openclaw-memory-promotion:memory:memory/2026-05-23-0218.md:11:11 -->
- ⚠️ Validation warnings (1): 报告长度 1423 字 > 1200 软上限 (warn) [score=0.891 recalls=0 avg=0.620 source=memory/2026-05-23-0218.md:11-11]
<!-- openclaw-memory-promotion:memory:memory/2026-05-23-0218.md:15:15 -->
- 📊 市值 $3,126 | 浮盈 +$314 (+11.2%) | 今日 +$59 | ✅ 已实现 +$1,031 [score=0.891 recalls=0 avg=0.620 source=memory/2026-05-23-0218.md:15-15]
<!-- openclaw-memory-promotion:memory:memory/2026-05-23-0218.md:17:20 -->
- | 代码 | 股 | 成本 | 现价 | 今日 | 浮% | 浮$ | |:------|------:|-------:|-------:|-------:|-------:|--------:| | RKLB | 5 | 71.00 | 135.63 | +8.1% | +91.0% | +323 | | CRCL | 2 | 87.00 | 115.72 | +0.7% | +33.0% | +57 | [score=0.891 recalls=0 avg=0.620 source=memory/2026-05-23-0218.md:17-20]

## Promoted From Short-Term Memory (2026-05-30)

<!-- openclaw-memory-promotion:memory:memory/2026-05-22-0043.md:17:17 -->
- **美股有暗盘吗？** [score=0.883 recalls=0 avg=0.620 source=memory/2026-05-22-0043.md:17-17]
<!-- openclaw-memory-promotion:memory:memory/2026-05-23-0218.md:13:13 -->
- 🇺🇸 美股盯盘 | 05/22 10:04 ET [score=0.881 recalls=0 avg=0.620 source=memory/2026-05-23-0218.md:13-13]
<!-- openclaw-memory-promotion:memory:memory/2026-05-21-pre-open.md:2:3 -->
- layout: default title: 盘前深度简报 · 2026-05-21 [score=0.875 recalls=0 avg=0.620 source=memory/2026-05-21-pre-open.md:2-3]
