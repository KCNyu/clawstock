# 当前持仓摘要（openclaw workspace / 投资记忆 / portfolio）

## 用途
这个文件不是权威持仓来源。

它的作用是：
- 帮助 `memory_search` 更容易命中投资上下文
- 给新会话一个快速入口
- 提醒任何模型：真正的当前持仓请读取 `portfolio.json`

## 权威入口
- 当前持仓：`portfolio.json`
- 长期规则：`MEMORY.md`
- 工作流：`INVESTMENT_SOP.md`

## 当前持仓 ticker 列表（具体股数/成本以 `portfolio.json` 为准）

### 美股活跃 ticker
RKLB, CRCL, PLTU, SOXL, RKLX, ROBN, MSFU

### 港股活跃 ticker
- `00100` MiniMax-W
- `02208` 金风科技
- `03032` 恒生科技ETF
- `07226` 南方2x恒科
- `03033` 南方恒生科技

### 已清仓（不再追踪）
- 美股：`NVDA`、`OKLO`、`QQQ`、`TCOM`、`TQQQ`、`HOOD`
- 港股：`07709`、`07747`
- 韩股：`000660`（SK海力士）、`005930`（三星电子）

## 持仓特征
- 风格偏激进
- 港股当前最大市值与波动源是 `00100` MiniMax-W，其次是 `07226` 两倍恒科
- 美股当前偏高弹性成长 + 杠杆短线仓
- 韩链条已断开，不再追踪韩股映射

## 查询提示
如果用户问：
- 当前持仓
- 美股港股分析
- 节后操作建议
- 哪些该减仓/加仓

请不要只依赖语义检索结果，直接读取：
1. `MEMORY.md`
2. `portfolio.json`
3. 再拉最新价格
