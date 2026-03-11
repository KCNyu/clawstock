# Rick's Stock Analysis Tools

## Portfolio Analyzer

我为 kcn 创建了一个专属的股票分析系统。

### API Keys (已配置)
- **Finnhub**: d6m1kj9r01qu3p05oh6gd6m1kj9r01qu3p05oh70
- **Alpha Vantage**: KTEYFLXLT8BQFDY7
- **Polygon.io**: iodnjUhI4gX9im0Hg8SPbY2kzhtIHlPf

### 文件说明
- `portfolio.json` - kcn 的持仓数据
- `stock_analyzer.py` - 主分析脚本
- `.api_keys` - API 密钥（不要提交到 git）
- `check_portfolio.sh` - 快速查看脚本

### 使用方法

**快速查看持仓：**
```bash
./check_portfolio.sh
```

**或直接运行：**
```bash
python3 stock_analyzer.py
```

### 功能
- ✅ 实时股价更新（Finnhub）
- ✅ 公司信息和市值
- ✅ 最新新闻（过去3天）
- ✅ 盈亏计算
- ✅ 持仓报告生成

### 当前持仓
| 股票 | 股数 | 成本 | 当前 | 盈亏 |
| ---- | --- | --- | ------ | ---------- |
| NVDA | 3 | $187 | $177.83 | -4.90% |
| RKLB | 5 | $71 | $70.12 | -1.24% |
| CRCL | 5 | $87 | ~$115 | +32% 🎉（已卖出5股锁利） |
| QQQ | 1 | $622 | $599.76 | -3.58% |

**总计：** $2,408 → $2,503 (+$95, +3.95%)

### 下一步
- 可以添加技术指标分析（RSI、MACD等）
- 可以设置价格提醒
- 可以添加自动化日报
- 可以集成 TradingAgents 的多智能体分析

---

_Last updated: 2026-03-08_
