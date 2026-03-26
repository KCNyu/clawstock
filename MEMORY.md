# MEMORY.md - Rick's Long-Term Memory

## 用户偏好

### 持仓分析风格
- **每次直接分析当前持仓**：用 portfolio.json 里的成本价 vs 实时价格计算盈亏
- **不用追踪历史交易记录**：忽略 trades 字段里的历史操作，focus 当前仓位
- 简洁明了，不需要交代背景或之前发生过什么
- 风险偏好：**激进型**，可用现金约 15万人民币（≈$20,500 USD），不排斥高波动标的

### ⚠️ 数据获取规则（重要）
- **每次被问到持仓/股价，必须先获取最新实时数据，再回复，不得使用 portfolio.json 中的缓存旧价格**
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
- 新浪/腾讯美股接口境外 403，跳过不试
- 如所有数据源均失败，必须明确告知用户"数据获取失败，以下为旧数据"，不能静默使用旧数据
- 获取到最新数据后，更新 portfolio.json 并 git commit

---

## 持仓数据
- **单一来源：`portfolio.json`** — 每次问持仓直接读这个文件，不在 MEMORY.md 里维护副本
- 读法：`python3 -c "import json; d=json.load(open('portfolio.json')); ..."`
- 更新后记得 git commit

---

## 已知问题 & 待办

### ❌ Telegram 通知失败（2026-03-19 起）
- Heartbeat 推送失败，原因：chat ID 可能已变更
- **待办：kcn 需要确认当前 Telegram chat ID**，更新 openclaw 配置

### 📝 日志断档
- memory/ 最后记录：2026-03-19
- 3/23、3/25 有真实交易，无日志记录
- **下次交易后记得补记日志**

---

## 关键市场联动关系
- 美股存储（MU/WDC）→ 韩股（海力士/三星）→ 港股杠杆ETF（07709/07747）
- 油价↓（地缘缓和）↔ 加密/科技涨
- CRCL 逻辑：GENIUS Act 稳定币法案推进（与大盘相对独立）
- OKLO 逻辑：核能 + Sam Altman 背书，长期看好，但当前套牢

---
