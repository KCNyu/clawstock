# MEMORY.md - Rick's Long-Term Memory

## 用户偏好

### 持仓分析风格
- **每次直接分析当前持仓**：用 `portfolio.json` 里的成本价 vs 最新价格计算盈亏
- **不用追踪历史交易记录**：忽略 `trades` 字段里的历史操作，focus 当前仓位
- 简洁明了，不需要交代背景或之前发生过什么
- 风险偏好：**激进型**，可用现金约 15万人民币（≈$20,500 USD），不排斥高波动标的
- 关注重点以**港股为主**，尤其重视港股持仓、节奏和交易机会，美股作为重要补充观察

### openclaw workspace 投资入口（重要）
- 凡是用户问到：`持仓`、`portfolio`、`美股`、`港股`、`节后操作`、`加仓/减仓`
- **不要只依赖 `memory_search`**
- 必须按顺序读取：
  1. `MEMORY.md`
  2. `portfolio.json`
  3. `memory/current-portfolio-summary.md`
  4. 必要时读取最近 `memory/YYYY-MM-DD.md`
- 工作流文档：`INVESTMENT_SOP.md`

### ⚠️ 数据获取规则（重要）
- **每次被问到持仓/股价，必须先获取最新实时数据，再回复，不得使用 `portfolio.json` 中的缓存旧价格**
- **每次获取股价必须走自动 fallback 链，逐个尝试，失败了立即换下一个，直到成功为止**
- 港股 fallback 链（按顺序逐个试）：
  1. 腾讯财经 `qt.gtimg.cn/q=r_hkXXXXX` — 境外可用，实时，**已验证 ✅**（2026-03-26 noon 成功）
  2. 东方财富批量 API `push2.eastmoney.com` — `116.XXXXXX`（6位补零）
  3. stooq.com `curl stooq.com/q/d/l/?s=XXXX.hk&i=d` — 收盘价，非实时
  4. yfinance `2208.HK` — 限速慎用，最后备选
- 美股 fallback 链（按顺序逐个试）：
  1. 东方财富 `push2.eastmoney.com` — `105.NVDA`
  2. Finnhub API（需 key）
  3. yfinance — 限速慎用
  4. Alpha Vantage（需 key，慢）
- 韩股 fallback 链：已移除（2026-05-05，07709/07747 均已清仓，不再追踪韩股）
- 新浪/腾讯美股接口境外 403，跳过不试
- 如所有数据源均失败，必须明确告知用户“数据获取失败，以下为旧数据”，不能静默使用旧数据
- 获取到最新数据后，更新 `portfolio.json` 并 git commit

---

## 持仓数据
- **单一来源：`portfolio.json`** — 每次问持仓直接读这个文件，不在 `MEMORY.md` 里维护副本
- 为提高检索命中率，可先看 `memory/current-portfolio-summary.md`，但它不是权威来源
- 更新后记得 git commit

---

## OpenClaw CLI 操作注意事项（2026-04-07 记录）

### ⚠️ `openclaw cron` / `openclaw gateway status` 等子命令会卡死
- **原因**：这些命令通过 WebSocket RPC 连接 gateway（端口 18789），在 agent exec 沙箱环境里无法完成 auth 握手，会一直 pending 直到被 SIGKILL
- **影响范围**：所有需要 gateway RPC 的子命令，包括 `cron list/add/delete`、`gateway status`、`cron --help` 等
- **解决方案**：
  - 查 cron 任务 → 直接读 `~/.openclaw/cron/jobs.json`
  - 查 gateway 状态 → `systemctl --user status openclaw-gateway` 或 `curl http://127.0.0.1:18789/health`
  - 查 dreaming 状态 → 在 `jobs.json` 里找 `managed-by=memory-core` 的任务
- **不是 bug**：设计如此，这些 CLI 命令原本只在宿主机 shell 里直接运行

---

## 已知问题 & 待办

### ❌ Telegram 通知失败（2026-03-19 起）
- Heartbeat 推送失败，原因：chat ID 可能已变更
- **待办：kcn 需要确认当前 Telegram chat ID**，更新 openclaw 配置

### 📝 日志断档
- 3/23、3/25 有真实交易，无日志记录
- 后续每次重要交易或分析结论，更新当天 `memory/YYYY-MM-DD.md`

### 🧠 检索稳定性
- 仅依赖语义检索时，可能漏掉 `portfolio.json` 这类结构化数据
- 已新增：`INVESTMENT_SOP.md` 和 `memory/current-portfolio-summary.md`
- 后续投资问题统一走固定入口，而不是只赌检索命中

---

## 关键市场联动关系
- 油价↓（地缘缓和）↔ 加密/科技涨
- CRCL 逻辑：GENIUS Act 稳定币法案推进（与大盘相对独立）
- 港股核心驱动：恒科指数方向 + 个股独立逻辑（00100 AI概念、02208 风电政策）

## Promoted From Short-Term Memory (2026-04-09)

<!-- openclaw-memory-promotion:memory:memory/2026-03-11.md:1:32 -->
- ## 2026-03-10 交易日复盘 ### 市场背景 - 催化剂：特朗普"伊朗停战"发言 → 地缘风险降低 → KOSPI +6%，港股全线走强 - SK海力士收盘 +12.2%（938,000 KRW），三星 +9.22%（189,500 KRW） - 美股存储板块：MU +6%，WDC +6.8%，STX +4.1%（全部在日内高位收盘） ### kcn 持仓状态（收盘） **港股** - 07709 XL海力士(2x)：28.90 +22%，累计亏损 -1,884 HKD，距回本 +10.9% - 07747 XL三星(2x)：72.20 +14%，累计亏损 -1,930 HKD，距回本 +13.4% - 07226 XL恒科(2x)：4.158 +5.16%，亏 -1,764 HKD - 03032 恒生科技ETF：5.035 +2.5%，亏 -74 HKD - 03033 南方恒科：4.946 +2.57%，亏 -194 HKD，距回本仅 3.9% ⭐ - 02208 金风科技：14.57 +0.48%，已回本 +292 HKD ✅ - 港股今日回血：+HKD 6,329；总亏损从 -11,884 收窄至 -5,555（-7.54%） **美股** - CRCL：收盘约 $118，今日 +5.8%，持仓盈利 +$298（+34%），成本 $87 x10股 - NVDA：$184.75 +1.15%，持仓小亏 -$7 - RKLB：$71.75 +0.4%，持仓微盈 - QQQ：$607~610，持仓小亏 ### CRCL 分析 - 公司：Circle Internet Group（USDC稳定币发行商） - 催化剂：GENIUS Act（稳定币法案）推进 + Bernstein目标价 $200（+70%空间） - 历史高点：$298.99（2025-06-23），当前 ~$118，距高点 -60% - 58% 历史成交量在当前价格以上（套牢盘多） - 套牢压力位：$120~130 / $145~160 / $180~200 - 技术面：RSI 74.6（超买），量价背离，MACD趋平 [score=0.842 recalls=4 avg=0.656 source=memory/2026-03-11.md:1-32]

## Promoted From Short-Term Memory (2026-04-10)

<!-- openclaw-memory-promotion:memory:memory/2026-03-19.md:1:25 -->
- # 2026-03-19 Daily Notes ## 04:35 AM - 美光(MU)财报出炉 **MU Q2 FY2026 实际业绩**（截至2026年2月）: - 营收：$23.86B（同比 +196%，上季 $13.64B） - 净利润：$13.785B - 盘后股价：$454.82（-1.50%，-$6.91） - 收盘价：$461.73 **信号：业绩炸裂但盘后小跌** - 典型"buy the rumor sell the news" - MU 52周从 $61.54 涨到 $471，已涨7倍，可能消化了预期 - Bernstein 上调目标价 $330→$510（维持Buy，3/18/2026） - 分析师共识：Strong Buy，均价目标 $377.47（低于当前价） **持仓影响分析：** - 07709（海力士2x ETF）700股 @28.72：谨慎，等开盘观察 - 07747（三星2x ETF）200股 @72.20：谨慎，等开盘观察 建议：港股开盘前15-30分钟观察走势，若相关标的跌幅>3%考虑减仓 ## HEARTBEAT.md 任务状态 MU财报已出，检查完成。通知kcn（Telegram发送失败，需要更新chat ID） [score=0.878 recalls=4 avg=0.754 source=memory/2026-03-19.md:1-25]

## Promoted From Short-Term Memory (2026-04-16)

<!-- openclaw-memory-promotion:memory:memory/2026-04-09.md:87:96 -->
- - Candidate: Assistant: [[reply_to_current]] 可以，这个逻辑其实很清楚，我给你压缩成能直接用的版本。 ## 一、先看韩股，再映射港股 你这类票的链条是： - **美股存储/半导体情绪** - -> **韩股海力士、三星** - -> **港股 07709、07747** - 再叠加 **港股自己情绪、ETF杠杆损耗、开盘溢价** 所以你做港股，不是只看港股K线， 而是要先判断： **韩股今天是强趋势、弱趋势，还是震荡。** --- ## 二、今天韩股给出的信号 ### 海力士现在 - **99.9万** - **-3.29%** - 高 - confidence: 0.00 - evidence: memory/.dreams/session-corpus/2026-04-09.txt:58-58 - recalls: 0 - status: staged - Candidate: Possible Lasting Truths: ## 2026-03-10 交易日复盘 ### 市场背景 - 催化剂：特朗普"伊朗停战"发言 → 地缘风险降低 → KOSPI +6%，港股全线走强 - SK海力士收盘 +12.2%（938,000 KRW），三星 +9.22%（189,500 KRW） - 美股存储板块：MU +6%，WDC +6.8%，STX +4.1%（全部在日内高位收盘） ### kcn 持仓状态（收盘） **港股** - 07709 XL海力士(2x)：28.90 +22%，累计亏损 -1,884 HKD，距回本 +10.9% - confidence: 0.00 - evidence: memory/2026-04-09.md:324-326 - recalls: 0 - status: staged [score=0.852 recalls=3 avg=0.922 source=memory/2026-04-09.md:87-96]

## Promoted From Short-Term Memory (2026-04-17)

<!-- openclaw-memory-promotion:memory:memory/2026-04-10.md:83:89 -->
- - Candidate: Assistant: [[reply_to_current]] 对，你这个担心是对的。 如果单次 T 的价差太小，**很容易忙半天，最后全给手续费和滑点吃掉**。 像刚才那种 **30.28 -> 31.28** 看着有 1 块，其实才比较勉强成立； 如果你做的是 **几毛钱来回**，大概率不划算。 ## 直接说结论 你现在这票更适合： - **不做超短小T** - 只做 **大一点的波段T** - 目标至少拉到 **每股 0.8 到 1.2 HKD** 的空间，再动手 ## 对 07709 更实用的做法 你现在 700 股里： - **600股核心仓别 - confidence: 0.00 - evidence: memory/.dreams/session-corpus/2026-04-10.txt:76-76 - recalls: 0 - status: staged - Candidate: Assistant: [[reply_to_current]] 可以，这个思路**比现在 100 股小打小闹更像样**。 我同意你的方向： - **如果真要吃小波动** - 那就要靠 **更大的 T 仓** - 不然价差太薄，利润不够看 但我也得直接提醒一句： ## 核心问题 你现在 **总持仓才 700股**， 所以“下次 1000 股做T”这个想法，前提是你后面要把仓位重新加大，或者以后在别的类似票上这么做。 否则以你现在这只 07709 的真实仓位， 更现实的是： - **核心仓 500 到 700** - **T仓 200 到 400** - 而 - confidence: 0.00 [score=0.817 recalls=3 avg=1.000 source=memory/2026-04-10.md:83-89]
<!-- openclaw-memory-promotion:memory:memory/2026-04-11.md:173:179 -->
- - Candidate: Assistant: [[reply_to_current]] 对，你这个担心是对的。 如果单次 T 的价差太小，**很容易忙半天，最后全给手续费和滑点吃掉**。 像刚才那种 **30.28 -> 31.28** 看着有 1 块，其实才比较勉强成立； 如果你做的是 **几毛钱来回**，大概率不划算。 ## 直接说结论 你现在这票更适合： - **不做超短小T** - 只做 **大一点的波段T** - 目标至少拉到 **每股 0.8 到 1.2 HKD** 的空间，再动手 ## 对 07709 更实用的做法 你现在 700 股里： - **600股核心仓别 - confidence: 0.00 - evidence: memory/.dreams/session-corpus/2026-04-10.txt:76-76 - recalls: 0 - status: staged - Candidate: Assistant: [[reply_to_current]] 可以，这个思路**比现在 100 股小打小闹更像样**。 我同意你的方向： - **如果真要吃小波动** - 那就要靠 **更大的 T 仓** - 不然价差太薄，利润不够看 但我也得直接提醒一句： ## 核心问题 你现在 **总持仓才 700股**， 所以“下次 1000 股做T”这个想法，前提是你后面要把仓位重新加大，或者以后在别的类似票上这么做。 否则以你现在这只 07709 的真实仓位， 更现实的是： - **核心仓 500 到 700** - **T仓 200 到 400** - 而 - confidence: 0.00 [score=0.817 recalls=3 avg=1.000 source=memory/2026-04-11.md:173-179]
<!-- openclaw-memory-promotion:memory:memory/2026-04-12.md:198:204 -->
- - Candidate: Assistant: [[reply_to_current]] 对，你这个担心是对的。 如果单次 T 的价差太小，**很容易忙半天，最后全给手续费和滑点吃掉**。 像刚才那种 **30.28 -> 31.28** 看着有 1 块，其实才比较勉强成立； 如果你做的是 **几毛钱来回**，大概率不划算。 ## 直接说结论 你现在这票更适合： - **不做超短小T** - 只做 **大一点的波段T** - 目标至少拉到 **每股 0.8 到 1.2 HKD** 的空间，再动手 ## 对 07709 更实用的做法 你现在 700 股里： - **600股核心仓别 - confidence: 0.00 - evidence: memory/.dreams/session-corpus/2026-04-10.txt:76-76 - recalls: 0 - status: staged - Candidate: Assistant: [[reply_to_current]] 可以，这个思路**比现在 100 股小打小闹更像样**。 我同意你的方向： - **如果真要吃小波动** - 那就要靠 **更大的 T 仓** - 不然价差太薄，利润不够看 但我也得直接提醒一句： ## 核心问题 你现在 **总持仓才 700股**， 所以“下次 1000 股做T”这个想法，前提是你后面要把仓位重新加大，或者以后在别的类似票上这么做。 否则以你现在这只 07709 的真实仓位， 更现实的是： - **核心仓 500 到 700** - **T仓 200 到 400** - 而 - confidence: 0.00 [score=0.817 recalls=3 avg=1.000 source=memory/2026-04-12.md:198-204]

## Promoted From Short-Term Memory (2026-04-19)

<!-- openclaw-memory-promotion:memory:memory/2026-04-11.md:263:266 -->
- - Candidate: Reflections: Theme: `assistant` kept surfacing across 377 memories.; confidence: 1.00; evidence: memory/.dreams/session-corpus/2026-04-06.txt:2-2, memory/.dreams/session-corpus/2026-04-06.txt:3-3, memory/.dreams/session-corpus/2026-04-06.txt:5-5; note: reflection - confidence: 0.00 - evidence: memory/2026-04-11.md:263-266 - recalls: 0 [score=0.845 recalls=0 avg=0.620 source=memory/2026-04-11.md:3-6]
<!-- openclaw-memory-promotion:memory:memory/2026-04-11.md:269:271 -->
- - Candidate: Possible Lasting Truths: - 16:42 交易记录：07709 XL二南方海力士 30.50 买回 100 股，持仓回到 700 股，摊薄后成本约 29.6369。 - 今日盘中重点结论：海力士（07709）经历长时间回调后出现强修复，大阳线更像“反转候选信号”而非单纯超涨，但短线已进入高波动分歧区，适合保留核心仓并用 100-200 股做T，不宜高位追涨。 - 今日组合判断：港股最大风险源仍是 07226（南方2x恒科）和 07709（海力士）两只高弹性仓位，后续应优先做结构管理，思路是“保留强仓、滚动做T、逐步精简弱仓、为后续 - confidence: 0.00 - evidence: memory/2026-04-10.md:274-276 [score=0.845 recalls=0 avg=0.620 source=memory/2026-04-11.md:53-55]
<!-- openclaw-memory-promotion:memory:memory/2026-04-12.md:278:281 -->
- - Candidate: Reflections: Theme: `assistant` kept surfacing across 379 memories.; confidence: 1.00; evidence: memory/.dreams/session-corpus/2026-04-06.txt:2-2, memory/.dreams/session-corpus/2026-04-06.txt:3-3, memory/.dreams/session-corpus/2026-04-06.txt:5-5; note: reflection - confidence: 0.00 - evidence: memory/2026-04-12.md:278-281 - recalls: 0 [score=0.845 recalls=0 avg=0.620 source=memory/2026-04-12.md:3-6]
<!-- openclaw-memory-promotion:memory:memory/2026-04-12.md:284:286 -->
- - Candidate: Possible Lasting Truths: - 16:42 交易记录：07709 XL二南方海力士 30.50 买回 100 股，持仓回到 700 股，摊薄后成本约 29.6369。 - 今日盘中重点结论：海力士（07709）经历长时间回调后出现强修复，大阳线更像“反转候选信号”而非单纯超涨，但短线已进入高波动分歧区，适合保留核心仓并用 100-200 股做T，不宜高位追涨。 - 今日组合判断：港股最大风险源仍是 07226（南方2x恒科）和 07709（海力士）两只高弹性仓位，后续应优先做结构管理，思路是“保留强仓、滚动做T、逐步精简弱仓、为后续 - confidence: 0.00 - evidence: memory/2026-04-10.md:274-276 [score=0.845 recalls=0 avg=0.620 source=memory/2026-04-12.md:78-80]
<!-- openclaw-memory-promotion:memory:memory/2026-04-13.md:274:276 -->
- - Candidate: Possible Lasting Truths: - 16:42 交易记录：07709 XL二南方海力士 30.50 买回 100 股，持仓回到 700 股，摊薄后成本约 29.6369。 - 今日盘中重点结论：海力士（07709）经历长时间回调后出现强修复，大阳线更像“反转候选信号”而非单纯超涨，但短线已进入高波动分歧区，适合保留核心仓并用 100-200 股做T，不宜高位追涨。 - 今日组合判断：港股最大风险源仍是 07226（南方2x恒科）和 07709（海力士）两只高弹性仓位，后续应优先做结构管理，思路是“保留强仓、滚动做T、逐步精简弱仓、为后续 - confidence: 0.00 - evidence: memory/2026-04-10.md:274-276 [score=0.838 recalls=0 avg=0.620 source=memory/2026-04-13.md:53-55]
<!-- openclaw-memory-promotion:memory:memory/2026-03-26.md:1:27 -->
- # 2026-03-26 Daily Notes ## 13:34 - 自我诊断 & 记忆优化 ### 诊断发现 1. **MEMORY.md 偏瘦** - 只有数据规则，无持仓摘要/关键上下文 2. **TOOLS.md 持仓表过期** - 还在显示 3/11 数据，与 portfolio.json 不符 3. **数据源描述冲突** - TOOLS.md 说东财是#1，MEMORY.md 说腾讯是#1（腾讯已验证境外可用） 4. **HEARTBEAT.md 遗留问题** - 3/19 Telegram chat ID 失败，1周后仍未解决 5. **日志断档** - 3/19 之后无日志，但 3/23、3/25 有真实交易 6. **memory_search FTS 返回空** - 索引不可用，但 memory_get 正常 ### 修复措施 - ✅ MEMORY.md 大幅扩充：加入持仓摘要、关键交易历史、待办事项、市场联动关系 - ✅ 创建 2026-03-26 日志（本文） - ⚠️ TOOLS.md 持仓表仍旧（需要今天刷新持仓后更新） - ⚠️ Telegram chat ID 问题待 kcn 确认 ### 今日持仓状态（12:00 腾讯财经数据） - 港股今日大跌：07709 -10.55%，07747 -8.53% - 美股整体小幅亏损（未刷新，2026-03-26 12:00 数据） - 港股总亏损约 HKD -6994（-10.7%） ### 关键待办 - [ ] 确认 Telegram chat ID（HEARTBEAT 通知失败问题） - [ ] 今日港股走势（07709/07747 跌幅是否需要减仓） [score=0.801 recalls=3 avg=0.838 source=memory/2026-03-26.md:1-27]

## Promoted From Short-Term Memory (2026-04-20)

<!-- openclaw-memory-promotion:memory:memory/2026-04-14.md:273:276 -->
- 12:07 交易记录：07709 XL二南方海力士 36.00 卖出 100 股，按持仓成本 29.5348 计，本次实现盈利约 646.52 HKD；持仓降至 600 股。 13:06 交易记录：07709 XL二南方海力士 36.02 卖出 100 股，按持仓成本 29.5348 计，本次实现盈利约 648.52 HKD；持仓降至 500 股。 [score=0.843 recalls=0 avg=0.620 source=memory/2026-04-14.md:273-274]
<!-- openclaw-memory-promotion:memory:memory/2026-04-14.md:277:278 -->
- 今日盘中操作思路更新：由于用户明确担心 2x 杠杆磨损，下午策略从“保留 600 股核心仓 + 100 股做T”调整为更防守的“07709 降到 500 股左右”，核心逻辑是把高波动杠杆仓从方向赌注改成波动管理仓。 [score=0.843 recalls=0 avg=0.620 source=memory/2026-04-14.md:277-277]

## Promoted From Short-Term Memory (2026-04-21)

<!-- openclaw-memory-promotion:memory:memory/2026-04-15.md:1:1 -->
- 09:34 交易记录：07709 XL二南方海力士 38.70 卖出 100 股，按持仓成本 29.5348 计，本次实现盈利约 916.52 HKD；持仓降至 400 股。 [score=0.850 recalls=0 avg=0.620 source=memory/2026-04-15.md:1-1]
<!-- openclaw-memory-promotion:memory:memory/2026-04-15.md:276:278 -->
- ## Light Sleep <!-- openclaw:dreaming:light:start --> - Candidate: Reflections: Theme: `assistant` kept surfacing across 486 memories.; confidence: 1.00; evidence: memory/.dreams/session-corpus/2026-04-06.txt:2-2, memory/.dreams/session-corpus/2026-04-06.txt:3-3, memory/.dreams/session-corpus/2026-04-06.txt:5-5; note: reflection - confidence: 0.62 - evidence: memory/2026-04-14.md:263-266 - recalls: 0 - status: staged - Candidate: Possible Lasting Truths: - Candidate: Assistant: [[reply_to_current]] 那这个影响会很大，甚至可能比 system prompt cache 更大。 你现在的瓶颈很像是： - LLM 先决定调用 tool A - 你执行 tool A - 再把结果喂回去 - LLM 再决定 tool B - 再执行 - 最后再总结 这会导致每个 tool 都多出一整轮： **“一次模型调用 + 一次工具等待 + 一次上下文回填”** 如果一次分析要 3 到 5 个 tools，这个串行链路很容易就炸到几 [score=0.850 recalls=0 avg=0.620 source=memory/2026-04-15.md:282-289]
<!-- openclaw-memory-promotion:memory:memory/2026-04-15.md:280:280 -->
- 09:34 交易记录：07709 XL二南方海力士 38.70 卖出 100 股，按持仓成本 29.5348 计，本次实现盈利约 916.52 HKD；持仓降至 400 股。 [score=0.850 recalls=0 avg=0.620 source=memory/2026-04-15.md:280-280]
<!-- openclaw-memory-promotion:memory:memory/2026-04-15.md:555:557 -->
- - Candidate: Possible Lasting Truths: - Candidate: Assistant: [[reply_to_current]] 那这个影响会很大，甚至可能比 system prompt cache 更大。 你现在的瓶颈很像是： - LLM 先决定调用 tool A - 你执行 tool A - 再把结果喂回去 - LLM 再决定 tool B - 再执行 - 最后再总结 这会导致每个 tool 都多出一整轮： **“一次模型调用 + 一次工具等待 + 一次上下文回填”** 如果一次分析要 3 到 5 个 tools，这个串行链路很容易就炸到几 - confidence: 0.62 - evidence: memory/2026-04-14.md:269-271 [score=0.801 recalls=0 avg=0.620 source=memory/2026-04-15.md:289-291]

## Promoted From Short-Term Memory (2026-04-22)

<!-- openclaw-memory-promotion:memory:memory/2026-04-16.md:244:246 -->
- - recalls: 0 - status: staged - Candidate: Reflections: Theme: `assistant` kept surfacing across 545 memories.; confidence: 1.00; evidence: memory/.dreams/session-corpus/2026-04-06.txt:2-2, memory/.dreams/session-corpus/2026-04-06.txt:3-3, memory/.dreams/session-corpus/2026-04-06.txt:5-5; note: reflection - confidence: 0.62 - evidence: memory/2026-04-15.md:270-273 - recalls: 0 - status: staged - Candidate: Possible Lasting Truths: - Candidate: Assistant: [[reply_to_current]] 那这个影响会很大，甚至可能比 system prompt cache 更大。 你现在的瓶颈很像是： - LLM 先决定调用 tool A - 你执行 tool A - 再把结果喂回去 - LLM 再决定 tool B - 再执行 - 最后再总结 这会导致每个 tool 都多出一整轮： **“一次模型调用 + 一次工具等待 + 一次上下文回填”** 如果一次分析要 3 到 5 个 tools，这个串行链路很容易就炸到几 [score=0.841 recalls=0 avg=0.620 source=memory/2026-04-16.md:253-260]

## Promoted From Short-Term Memory (2026-04-28)

<!-- openclaw-memory-promotion:memory:memory/2026-04-22.md:1:4 -->
- 01:05 交易记录：RKLX（Defiance Daily Target 2X Long RKLB）46.70 美元买入 6 股，按用户截图记录，作为 RKLB 2x 杠杆短线仓；当前持仓新增 RKLX 6 股。 13:56 更正：刚才误记。用户主要关注**港股**，后续分析应默认先从港股持仓、节奏和机会展开，美股作为补充观察。 23:23 交易记录：OKLO 68.00 美元卖出 2 股，按持仓成本 62.83 计，本次实现盈利约 10.34 美元；OKLO 清仓。 23:28 交易记录：HOOD 88.36 美元卖出 5 股，按持仓成本 73.50 计，本次实现盈利约 74.30 美元；HOOD 清仓。 [score=0.843 recalls=0 avg=0.620 source=memory/2026-04-22.md:1-4]
<!-- openclaw-memory-promotion:memory:memory/2026-04-22.md:5:8 -->
- 23:37 交易记录：ROBN（T-REX 2X Long HOOD Daily Target ETF）26.68 美元买入 20 股，作为 HOOD 方向的 2x 杠杆替代仓。 23:49 持仓对齐：美股真实持仓更新为 RKLB / CRCL / TCOM / PLTU / SOXL / RKLX / ROBN；已清仓 OKLO、HOOD。 23:58 交易记录：TCOM 53.86 美元卖出 5 股，按持仓成本 52.74 计，本次实现盈利约 5.60 美元；TCOM 清仓。 00:13 再次对齐：美股真实持仓更新为 RKLB / CRCL / PLTU / SOXL / RKLX / ROBN；已清仓 OKLO、HOOD、TCOM。 [score=0.843 recalls=0 avg=0.620 source=memory/2026-04-22.md:5-8]

## Promoted From Short-Term Memory (2026-04-30)

<!-- openclaw-memory-promotion:memory:memory/2026-04-24.md:1:1 -->
- 09:31 交易记录：00100 MINIMAX-W 869.0 买入 20 股；持仓增至 40 股，摊薄后成本约 884.25 HKD。 [score=0.843 recalls=0 avg=0.620 source=memory/2026-04-24.md:1-1]

## Promoted From Short-Term Memory (2026-05-04)

<!-- openclaw-memory-promotion:memory:memory/2026-04-29.md:3:3 -->
- 16:02 港股收盘复盘：恒指 26106.98（+1.66%），恒科 4912.72（+1.77%）。kcn 港股持仓收盘市值 78,785.6 HKD，今日合计 +252.4 HKD，总浮亏 -9,490.64 HKD（-10.75%）。 [score=0.872 recalls=0 avg=0.620 source=memory/2026-04-29.md:3-3]
<!-- openclaw-memory-promotion:memory:memory/2026-04-29.md:5:5 -->
- 持仓：00100 MiniMax 709.5（-1.94%），今日拖累 -840 HKD，浮亏 -6,799.8 HKD；02208 金风科技 16.57（+3.43%），浮盈 +994.4 HKD，仍是港股最稳强仓；07226 2x恒科 3.838（+3.34%），今日贡献 +768.8 HKD，但尾盘从 3.86 回落，仍是组合主要杠杆风险；03032 4.89（+1.62%）；03033 4.814（+1.86%）。 [score=0.872 recalls=0 avg=0.620 source=memory/2026-04-29.md:5-5]
<!-- openclaw-memory-promotion:memory:memory/2026-04-29.md:7:7 -->
- 结论：指数强、恒科修复、07226 有效反弹但未强到可追，00100 明显弱于大盘且仍未站回 723/730，短线不补。后续若 07226 冲 3.90-4.00 可考虑减一点杠杆风险；02208 继续持有观察。 [score=0.822 recalls=0 avg=0.620 source=memory/2026-04-29.md:7-7]

## Promoted From Short-Term Memory (2026-05-08)

<!-- openclaw-memory-promotion:memory:memory/2026-05-03.md:3:3 -->
- 17:34 检查 OpenClaw GitHub changelog：v2026.5.2 已发布，重点包括外部插件/npm cutover、Gateway/session 性能优化、WebChat/Control UI 稳定性、WhatsApp/Telegram/Discord/Slack/Signal 等消息通道修复，以及 Heartbeats structured `heartbeat_respond`。 [score=0.870 recalls=0 avg=0.620 source=memory/2026-05-03.md:3-3]
<!-- openclaw-memory-promotion:memory:memory/2026-05-03.md:5:5 -->
- 17:34 检查最近 memory：workspace 最近的日记文件到 2026-04-29；2026-05-02 和 2026-05-03 当时不存在，说明近期日记有断档。 [score=0.870 recalls=0 avg=0.620 source=memory/2026-05-03.md:5-5]

## Promoted From Short-Term Memory (2026-05-09)

<!-- openclaw-memory-promotion:memory:memory/2026-05-04.md:11:14 -->
- | 代码 | 股数 | 成本 | 收盘 | 涨跌 | 市值 | 浮盈 | |------|------|------|------|------|------|------| | RKLB | 5 | $71.00 | $80.30 | +1.89% | $401.50 | +$46.50 | | CRCL | 2 | $87.00 | $119.57 | +19.92% | $239.13 | +$65.13 | [score=0.808 recalls=0 avg=0.620 source=memory/2026-05-04.md:11-14]
<!-- openclaw-memory-promotion:memory:memory/2026-05-04.md:15:18 -->
- | PLTU | 11 | $42.32 | $42.83 | +2.98% | $471.13 | +$5.61 | | SOXL | 5 | $91.87 | $127.55 | -2.19% | $637.75 | +$178.40 | | RKLX | 6 | $46.70 | $37.37 | +3.66% | $224.22 | -$55.98 | | ROBN | 30 | $24.34 | $19.50 | +7.62% | $585.00 | -$145.30 | [score=0.808 recalls=0 avg=0.620 source=memory/2026-05-04.md:15-18]
<!-- openclaw-memory-promotion:memory:memory/2026-05-04.md:19:19 -->
- | MSFU | 20 | $29.13 | $28.24 | -0.39% | $564.80 | -$17.80 | [score=0.808 recalls=0 avg=0.620 source=memory/2026-05-04.md:19-19]
<!-- openclaw-memory-promotion:memory:memory/2026-05-04.md:21:21 -->
- **总计：成本 $3,046.97 | 市值 $3,123.53 | 浮盈 +$76.56 (+2.51%) | 今日 +$93.69** [score=0.808 recalls=0 avg=0.620 source=memory/2026-05-04.md:21-21]

## Promoted From Short-Term Memory (2026-05-11)

<!-- openclaw-memory-promotion:memory:memory/2026-05-06.md:1:1 -->
- 22:56 交易记录：PLTU 35.96 美元买入 3 股，持仓从 11 股增至 14 股；按当前持仓加权成本从 42.32 降至约 40.9571。当前按最新价约 35.8657 计，PLTU 浮亏约 -71.28 美元（-12.43%）。 [score=0.857 recalls=0 avg=0.620 source=memory/2026-05-06.md:1-1]

## 时区问题记录（重要，2026-05-11补充）
- **美股交易时间**：美东 9:30-16:00 ET（北京时间 21:30-次日 04:00）
- **港股交易时间**：香港 9:30-12:00 / 13:00-16:00 HKT（北京时间同）
- 北京时间 21:39 = 美股刚开盘约10分钟，没有收盘价
- 北京时间 16:02 = 港股刚收盘
- **每次回答持仓问题前，先确认市场是否已收盘，避免把盘中价格当成收盘价**

## ⚠️ 数据准确性铁律（2026-05-11 补充）

**每次被问到持仓、盈亏、实时价格时，必须遵守以下规则：**

1. **不得使用 portfolio.json 中的缓存价格计算盈亏** — 该文件的 current_price 是上次更新时的旧数据，不代表当前实时价格
2. **必须先实时抓取最新价格，再回答任何持仓问题**
3. **使用 fallback 链路，不能在任何一个数据源失败时放弃**

### 美股实时价格 fallback 链路（按顺序）
1. CNBC web_fetch（最快最可靠）：`https://www.cnbc.com/quotes/{TICKER}`
2. 东方财富：`push2.eastmoney.com` 格式 `105.{TICKER}`
3. Finnhub（需 key）
4. Yahoo Finance：`finance.yahoo.com/quote/{TICKER}`
5. Alpha Vantage（需 key，慢）

### 港股实时价格 fallback 链路（按顺序）
1. 腾讯财经：`qt.gtimg.cn/q=r_hkXXXXX`（境外可用，已验证✅）
2. 东方财富：`push2.eastmoney.com` 格式 `116.XXXXXX`（6位补零）
3. stooq.com：`curl stooq.com/q/d/l/?s=XXXX.hk&i=d`（收盘价，非实时）
4. yfinance：`2208.HK` 等

### 验证规则
- 每次回答前，必须确认数据是从实时 API 获取的
- 如果所有 fallback 都失败，必须明确告知用户"数据获取失败，以下为旧数据"，不能静默使用旧数据
- **严禁在持仓分析中省略数据来源说明**

### 本次教训（2026-05-11）
- RKLB 盘中价格写成 $110，但实际 CNBC 实时价为 $118
- RKLX 盘中价格写成 $59，但实际 CNBC 实时价为 $73
- 导致累计盈利从真实的 +$790 错误写成约 +$550
- 原因：使用了 portfolio.json 中的旧数据，而非实时 API
