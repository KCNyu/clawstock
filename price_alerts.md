# 价格提醒系统说明

## 当前在用的系统（2026-05 起）

价格提醒**已迁移到 cron-driven WeChat report**，不再由 `price_alert_monitor.py` 持续轮询。

触发链路：
1. **3 个港股 cron** (`港股开盘/午盘/收盘报告`) + 1 个**美股开盘 cron** — 见 `~/.openclaw/cron/jobs.json`
2. 每次触发跑 `analyze_{hk,us}_stocks.py --wechat`
3. 脚本在 wechat 输出里直接打 STOP / TRIM / BUY / WATCH 信号
4. 信号 ≥ 2 个时 cron job 自动在 WeChat 简报追加 `▎风险提示` 段
5. 推送到 `openclaw-weixin` 频道

**入口 skill**：`hk-stock-analysis` / `us-stock-analysis` **Mode 6 — WeChat Briefing**

## 想加自定义提醒怎么做

不要再去改 `price_alert_monitor.py`。两个推荐路径：

### A. 临时盯单只股（一次性）
直接跟 Rick 说："盯下 RKLB，到 73 提醒我"。Rick 会用 Mode 1/2 + 后续 check-in 跟进。

### B. 持续提醒（多日）
1. 在 `portfolio.json` 对应 ticker 加 `alert_above` / `alert_below` 字段
2. 扩展 `analyze_{hk,us}_stocks.py` 在 wechat report 里读这些字段并打信号
3. 不重新启用 `price_alert_monitor.py` — 那是上一代轮询架构，不符合现在 cron+脚本的设计

## 已废弃

- `price_alert_monitor.py` — 2 个月没运行（monitor_state 最后更新 2026-03-19，无 cron）。代码里硬编码了 NVDA/QQQ 等已清仓 ticker，重新启用前必须清理
- `monitor_state.json` — 上一代状态文件，停摆同一天
- `monitor.log` — 同上，停摆于 2026-03-19

## 历史

2026-03 之前用 `price_alert_monitor.py` 每分钟轮询 + Telegram 通知。
2026-05-05 用户清理了 07709/07747 持仓，price_alert_monitor.py 同时移除两条提醒，但脚本本身没启动新进程。
2026-05 起统一走 cron + wechat 简报路径，本文件留作历史指引。
