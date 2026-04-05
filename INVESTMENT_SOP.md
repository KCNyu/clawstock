# Investment Workspace SOP

## 目标
让任何模型（Claude / GPT / 其他）进入这个 workspace 后，都能稳定接上投资分析上下文，不依赖一次性的语义检索命中。

## 单一事实来源
- 当前持仓：`portfolio.json`
- 长期规则与偏好：`MEMORY.md`
- 近期会话/交易日志：`memory/YYYY-MM-DD.md`
- 当前持仓摘要（便于语义检索）：`memory/current-portfolio-summary.md`
- 工具与脚本说明：`TOOLS.md`

## 标准启动顺序（投资相关问题）
凡是用户问到以下主题，必须执行本顺序：
- 持仓分析
- 节后操作建议
- 个股盈亏
- 美股/港股仓位
- 是否加仓/减仓

执行顺序：
1. 读取 `MEMORY.md`
2. 读取 `portfolio.json`
3. 读取 `memory/current-portfolio-summary.md`
4. 如需近期上下文，再读 `memory/` 中最近 1-3 篇日志
5. 拉取最新实时/最近收盘价格（必须遵循 fallback 链）
6. 更新 `portfolio.json`
7. 如有重要结论，更新当天 `memory/YYYY-MM-DD.md`

## 写入规则
- 不在 `MEMORY.md` 维护详细持仓副本，避免重复和过期
- `MEMORY.md` 只保留：规则、偏好、长期结论、关键联动关系
- `portfolio.json` 只保留：当前持仓、成本、现价、已实现盈亏、必要注释
- `memory/current-portfolio-summary.md` 只保留：当前主要持仓摘要 + 查询入口提示
- `memory/YYYY-MM-DD.md` 记录：当天交易、分析结论、复盘、经验教训

## 检索优化规则
为了提升 memory_search 命中率，关键文件中应包含这些常用词：
- openclaw workspace
- 投资记忆
- portfolio
- 持仓
- 美股
- 港股
- 节后操作

## 输出规则
- 分析持仓时，默认简洁直接
- 以当前仓位和最新价格为准，不追溯无关历史交易
- 明确区分：实时数据 / 收盘数据 / 旧缓存数据
- 若实时数据失败，必须明确告知数据来源和时效

## 维护规则
每次发生以下情况后，应同步更新对应文件：
- 买卖成交：更新 `portfolio.json` + 当日 `memory/YYYY-MM-DD.md`
- 重要策略变化：更新 `MEMORY.md`
- 持仓结构明显变化：更新 `memory/current-portfolio-summary.md`
- 数据源优先级变化：更新 `MEMORY.md` 和 `TOOLS.md`
