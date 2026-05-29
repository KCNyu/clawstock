---
name: openclaw-us-postclose-stale-price-swap
description: US 盘后 closed fetch（20:00+ ET）撞 Nasdaq 杠杆 ETF 报价坑，价格错位一日 + today_change 反号
metadata:
  type: project
---

2026-05-29 实例：dashboard US 显示浮盈 +$291、当日 -$123，MSFU/PLTU 被记成大跌。
真相是 US 当日大涨（MSFU +6.8% / PLTU +16.2% / ROBN +22.5%），正确总值 $3042.61、浮盈 +$414.31、当日 +$286.66。

**根因**：`scripts/data/fetch_us_stocks.py` 在 20:01 ET 的 `closed` 段抓取时，撞上 Nasdaq
对杠杆 ETF 的报价坑——`primaryData.lastSalePrice`(脚本的 `c`) 还停在**前一交易日旧价**，
而 `summaryData.PreviousClose`(脚本的 `pc`) 字段反而装着**当日真实收盘**。脚本第 593-620 行
信了 `c` 当现价、把真实收盘当成 prev_close，于是 `today_change=(c-pc)*shrs` 取了**反号**，
5 只活跃美股价格集体错位一个交易日。afterhours(16:03 ET) 抓的好价被这次 closed fetch 覆盖。

**识别信号**：活跃美股全部 `day_open==day_high==day_low==current_price`（退化报价），
且 `data_source` 都是同一次 `... 20:01 ET` 的 closed fetch；snapshot 里某标的现价 == 前一日现价。

**修复手法（已用，self-heal）**：
1. 隔几小时后 Nasdaq API 会 settle，直接 `python3 scripts/data/fetch_us_stocks.py` 重抓即可恢复正确现价/总值（两源 Nasdaq+Polygon 一致）。
2. 但盘后重抓时 Polygon prev-close 会取成**当日**收盘 → `today_change` collapse 成 0；
   需按 Nasdaq 官方 `netChange` 反推 prev_close 补回当日涨跌（per-share net × shares）。
3. `refresh_today_snapshot()`（scripts/harness/_harness_common.py）刷当天 snapshot —— 注意
   直接跑 `build_dashboard.py` **不会**刷 snapshot，必须先手动调它，否则 dashboard 仍用旧 snapshot。
4. 重建 dashboard + commit `portfolio.json` + `snapshots/{date}.json` + `dashboard.json` 推送。

**未做的根因硬化（follow-up）**：给 closed 段加 guard——当 Nasdaq `dp` 方向与 `(c-pc)` 符号
矛盾、或 o==h==l==c 退化报价时，distrust lastSalePrice。需先抓到 20:01 ET 的坏 payload 才能
测对，别凭猜上线金融管线。相关旧坑见 [[openclaw-stale-gha-data]] [[openclaw-equity-based-metrics]]。
