# BOOTSTRAP.md — openclaw injects this into every agent session

> openclaw 在 `agent:bootstrap` 事件时把本文件强制加进 prompt context，
> 任何 LLM 进 session 前都会看到这些规则。**这是硬约束，不是建议。**

---

## 🔒 必须遵守（hard rules）

### A. 数据规则

1. **绝不**用 `portfolio.json` 的 `current_price` 计算盈亏 — 它是旧缓存。先跑
   `scripts/data/analyze_{us,hk}_stocks.py` 刷价，再回答。
2. **绝不**把 HKD 和 USD 相加。Book total 必须双视角（USD-base + HKD-base），
   显式标 FX rate + source + timestamp。换算工具 `scripts/data/fetch_fx.py --json`。
3. **绝不**对 `00100 MINIMAX` 在 Tencent 失败时假装拿到数据 —
   它是唯一源，挂了必须明说 "实时价获取失败"。
4. **绝不**用旧版 `analyze_us_stocks.py` / `analyze_hk_stocks.py` 路径
   （`/root/.openclaw/workspace/analyze_*.py`）— 全在 `scripts/data/` 下。

### B. Harness 流程（cron 触发的所有股票 job）

不论是哪个 LLM 在跑（MiniMax / Xiaomi / GLM / Claude / GPT），都按 **4 步**：

1. **Preflight**：`python3 scripts/harness/{brief|report|intraday}_preflight.py [args]`
   - 把所有确定性活（刷价 / FX / HHI / 信号 / 异动）下放给 Python
   - 输出 `memory/.tmp/{type}-context-{date}.json`
2. **读 context.json**：
   - 数字（FX rate / book total / concentration / anomalies）**只从 JSON 取**
   - `raw_wechat_block` 字段必须 **verbatim 拷贝**到输出开头，不改时间戳/数字
3. **LLM 合成**（你这一步）：
   - 按对应 SKILL.md 的 Mode 模板写 markdown 报告
   - daily-deep-brief 还要写 `memory/{date}-plan.json`（schema 在 SKILL.md 里）
   - 报告里**必须**至少提一个 `anomalies` 字段里的异动票
   - 若 `needs_risk_section=true`，必须有 ▎风险提示 段
4. **Postflight**：`python3 scripts/harness/{brief|report|intraday}_postflight.py [args]`
   - 校验 → pass / warn 自动 commit；fail 加红 banner

### C+. 自进化机制（daily-deep-brief）

context.json 现在多了两个字段，**必须用上**：

1. **`peer_scan`** — 每个持仓的同题材竞品（listed + private + ETF proxy）
   - 必须输出 ▎同行扫描 段（表格）
   - 出现 `divergence_signal` 字段 → Judge 必须考虑 rotation trigger
   - 不许说 "考虑减仓"，要说 "减 X 股 → 加 Y 股"

2. **`self_calibration`** — 过去 30 天你（这个 brief）的 confidence 准确率
   - 如果 `samples ≥ 5`：必须输出 ▎Confidence 校准 段
   - 给 action 的 confidence 字段前，参考过去类似情境实际胜率
   - 如果 `brier_30d > 0.30` (模型过自信)：本次所有 confidence 自动 -10pp

### C. 输出约束

- **段标记必须用全角竖线**：`▎情绪面` `▎技术面` `▎操作建议` `▎风险提示` `▎我的看法`
- 报告长度：Mode 6 ≤ 800 字 / Mode 7 ≤ 600 字 / brief 无上限但段要齐
- **禁止敷衍词**：`数据待获取`、`等待数据`、`TODO`、`TBD` — postflight 会拦截
- **禁止 hedging 免责声明**：跳过 `this is not investment advice` 之类，铁律已注册
- 持仓回答**默认表格**（≥3 数据点必须表格化）

### D. 写入规则

| 触发 | 写哪个文件 |
|---|---|
| 跑了刷价脚本 | `portfolio.json` 已被脚本写，不要手改 |
| daily-deep-brief 完成 | `memory/{date}-pre-open.md` + `memory/{date}-plan.json` |
| Mode 6 报告 | 不写新文件；postflight 自动 commit portfolio.json + dashboard.json |
| Mode 7 盯盘 | **不写文件**，不 commit（高频，避免 commit log 刷屏） |
| 手动复盘 | `memory/{date}.md`（用户手写的，agent 别擅自填） |
| 新仓位 / 平仓 | `update_portfolio.py` 后由 postflight commit |

---

## 🚫 永远不做

- 编造数据；fallback 链全挂了就明说"数据获取失败"
- 从 chat / Telegram 触发的 session 不要直接 `git push` — 先问用户。harness postflight 跑完会自动 push（带 rebase+retry），不用 LLM 操心
- 改 `~/.openclaw/cron/jobs.json` 或 `~/.openclaw/openclaw.json` 不备份（先 `cp -p X X.bak.$(date +%Y%m%d-%H%M)`）— 自动化 LLM 也要遵守
- 跑 `scripts/legacy/` 下任何脚本当主路径（仅供参考阅读）
- 在 group chat / WeChat 简报里加 emoji 烟花（标题 1 个 emoji 上限）

---

## 📚 读完这个之后

按 `CLAUDE.md` 的 required reads 顺序补全上下文：
SOUL.md · USER.md · MEMORY.md · TOOLS.md · INVESTMENT_SOP.md · portfolio.json

Cron 触发的 session：直接按 SKILL.md 的 Mode 模板跑 4 步。
Topic / chat 触发的 session：先读相关 memory/YYYY-MM-DD.md，再回答。

---

_本文件由 openclaw `bootstrap-extra-files`/`BOOTSTRAP.md` 自动注入。改这里 = 改所有 session 的约束。_
