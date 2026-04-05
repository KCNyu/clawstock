# Rick's Stock Analysis Tools

## 当前结构总览
- 权威持仓：`portfolio.json`
- 长期规则与偏好：`MEMORY.md`
- 投资工作流：`INVESTMENT_SOP.md`
- 当前持仓摘要：`memory/current-portfolio-summary.md`
- 每日复盘/交易日志：`memory/YYYY-MM-DD.md`
- 主分析脚本：`stock_analyzer.py`
- 快速查看：`check_portfolio.sh`
- 监控/提醒：`price_alert_monitor.py`、`hk_monitor.py`、`portfolio_monitor.py`

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
python3 stock_analyzer.py
```

### 3. 快速查看持仓
```bash
bash check_portfolio.sh
```

---

## 数据源清单（当前约定）

### 港股 fallback 链
1. **腾讯财经** `qt.gtimg.cn/q=r_hkXXXXX`
2. **东方财富** `push2.eastmoney.com` 批量 API
3. **stooq** 日线收盘
4. **yfinance** 最后备选

### 美股 fallback 链
1. **东方财富** `push2.eastmoney.com`
2. **Finnhub**
3. **yfinance**
4. **Alpha Vantage**

### 说明
- 不要继续依赖旧版“境外一定拿不到腾讯港股”的结论，`MEMORY.md` 已记录 2026-03-26 实测可用
- 分析持仓前，必须先获取最新价格
- 如果全部失败，必须明确说明是旧数据

---

## 当前持仓梳理（基于 `portfolio.json` 最近记录）

### 美股
- `NVDA` 3股
- `RKLB` 5股
- `CRCL` 2股
- `OKLO` 2股
- `QQQ` 1股
- `TCOM` 5股
- `TQQQ` 8股
- `HOOD` 5股

### 港股
- `02208` 金风科技 600股
- `03032` 恒生科技ETF 200股
- `07226` 南方2x恒科 6200股
- `07709` XL二南方海力士 600股
- `07747` XL二南三星 100股
- `03033` 南方恒生科技 1000股

### 持仓特征
- 风格激进，波动容忍度较高
- 港股杠杆暴露偏高，风险集中在 `07226`、`07709`、`07747`
- 美股偏成长和高弹性，核心是 `NVDA`、`RKLB`、`CRCL`、`OKLO`、`TQQQ`、`HOOD`
- 关键联动：`MU/WDC -> 海力士/三星 -> 07709/07747`

---

## 现有脚本梳理

### 核心
- `stock_analyzer.py`：主更新与分析脚本，负责读取 `portfolio.json`、抓取行情、更新盈亏
- `hk_stock_fetcher.py`：港股更新脚本
- `final_analysis.py`：已有持仓分析输出脚本

### 监控类
- `price_alert_monitor.py`：价格提醒
- `hk_monitor.py`：港股监控
- `portfolio_monitor.py`：组合监控
- `hk_open_monitor.py`：港股开盘监控
- `hk_ai_monitor.py`：港股 AI 方向监控

### 展示类
- `portfolio_table.py`
- `portfolio_visualization.py`

### 研究/探索类
- `deep_analysis.py`
- `find_opportunities.py`
- `check_ai_stocks.py`
- `multi_agent_stock_analysis.py`
- `monday_signal.py`
- `TradingAgents/`

---

## 当前主要问题
- `MEMORY.md` 与 `portfolio.json` 分工已清晰，但过去缺少一个给检索友好的中间摘要层
- `TOOLS.md` 之前有过时持仓和旧数据源说明，现已统一
- 部分历史日志是“会话元信息”，不是投资复盘，后续应尽量把重要投资结论写入标准日记

---

## 维护建议
- 交易发生后：更新 `portfolio.json` + 当天 `memory/YYYY-MM-DD.md`
- 规则变化后：更新 `MEMORY.md`
- 持仓结构明显变化后：更新 `memory/current-portfolio-summary.md`
- 脚本数据源变化后：同步更新 `TOOLS.md` 与 `MEMORY.md`
