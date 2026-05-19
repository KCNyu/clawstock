#!/usr/bin/env python3
"""
gh_action_weekly_review.py — Sunday 22:00 HKT weekly portfolio review via Xiaomi.

Bundles past 7 days of plans / calibration rows / snapshots / current risk
into a single prompt, calls Xiaomi, writes memory/weekly/{ISO-week}.md.

Env: XIAOMI_API_KEY required
"""
import csv
import glob
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xiaomi_llm import chat


def aggregate_week():
    today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    week_id = f"{iso_year}-W{iso_week:02d}"
    start = today - timedelta(days=7)

    plans = []
    for f in sorted(glob.glob('memory/*-plan.json')):
        d_str = os.path.basename(f).split('-plan.json')[0]
        try:
            d = date.fromisoformat(d_str)
            if d >= start:
                plans.append({'date': d_str, 'data': json.loads(open(f).read())})
        except Exception:
            pass

    calib_rows = []
    if os.path.exists('memory/calibration.csv'):
        for r in csv.DictReader(open('memory/calibration.csv')):
            if r.get('plan_date', '') >= start.isoformat():
                calib_rows.append(r)

    snapshots = []
    for f in sorted(glob.glob('memory/snapshots/*.json')):
        d_str = os.path.basename(f).split('.json')[0]
        try:
            d = date.fromisoformat(d_str)
            if d >= start - timedelta(days=1):
                snapshots.append(json.loads(open(f).read()))
        except Exception:
            pass

    risk = None
    if os.path.exists('assets/data/risk.json'):
        risk = json.loads(open('assets/data/risk.json').read())

    return {
        'week': week_id,
        'window': f'{start.isoformat()} -> {today.isoformat()}',
        'plans': plans,
        'calibration_rows': calib_rows,
        'snapshots': snapshots[-7:],
        'current_risk': risk,
    }


def main():
    bundle = aggregate_week()
    week_id = bundle['week']

    system = "You are Rick, kcn's HK+US stock analyst. Write a weekly portfolio review."

    user = (
        f"根据这一周（{week_id}）的 brief / plan / calibration / risk 数据, "
        f"写一篇 markdown 周复盘。长度 1500-2500 字。"
        "\n\n"
        "重点回答 4 个问题:\n"
        "1. **本周净值**: 总市值 USD-base 周初 vs 周末, "
        "涪跌 + 主要贡献者 + 主要拖累\n"
        "2. **plan 兌现**: calibration_rows 里 followed=true/false 各几条? "
        "哪些 outcome=win? 哪些 outcome=loss? 本周 brier 趋势\n"
        "3. **风险演变**: 当前 risk.json 数值, ɫ/Vol/Max DD/Sharpe 怎么走?\n"
        "4. **下周关注 3 条**: actionable (ticker + 触发条件 + 仓位影响)\n\n"
        f"数据 bundle (JSON):\n```json\n{json.dumps(bundle, ensure_ascii=False)[:40000]}\n```\n\n"
        "直接出 markdown, 不要客套."
    )

    out = chat(system=system, user=user, max_tokens=8000, temperature=0.6)

    os.makedirs('memory/weekly', exist_ok=True)
    path = Path(f'memory/weekly/{week_id}.md')
    fm = f"---\nlayout: default\ntitle: 周复盘 · {week_id}\n---\n\n"
    path.write_text(fm + out.strip())
    print(f'  wrote {path}  ({len(out)} chars)')


if __name__ == '__main__':
    main()
