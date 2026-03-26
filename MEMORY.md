# MEMORY.md - Rick's Long-Term Memory

## 用户偏好

### 持仓分析风格
- **每次直接分析当前持仓**：用 portfolio.json 里的成本价 vs 实时价格计算盈亏
- **不用追踪历史交易记录**：忽略 trades 字段里的历史操作，focus 当前仓位
- 简洁明了，不需要交代背景或之前发生过什么

### ⚠️ 数据获取规则（重要）
- **每次被问到持仓/股价，必须先获取最新实时数据，再回复，不得使用 portfolio.json 中的缓存旧价格**
- **每次获取股价必须走自动 fallback 链，逐个尝试，失败了立即换下一个，直到成功为止**
- 港股 fallback 链（按顺序逐个试）：
  1. 腾讯财经 `qt.gtimg.cn/q=r_hkXXXXX` — 境外可用，实时，首选 ✅
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
