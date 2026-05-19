#!/usr/bin/env python3
"""
gh_action_news_digest.py — daily 21:00 HKT US news digest via Xiaomi.

Fetches Finnhub company-news for 7 active US holdings (past 48h),
calls Xiaomi to distill into actionable bullets, writes
assets/data/us_news_digest.json.

Env: FINNHUB_API_KEY + XIAOMI_API_KEY required
"""
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xiaomi_llm import chat


def fetch_news(tickers, since_days=2):
    finnhub_key = os.environ.get('FINNHUB_API_KEY')
    if not finnhub_key:
        print('FINNHUB_API_KEY not set — abort', file=sys.stderr)
        sys.exit(1)
    today = date.today()
    since = (today - timedelta(days=since_days)).isoformat()
    until = today.isoformat()
    out = {}
    for t in tickers:
        try:
            r = requests.get(
                'https://finnhub.io/api/v1/company-news',
                params={'symbol': t, 'from': since, 'to': until, 'token': finnhub_key},
                timeout=15,
            )
            items = r.json() if r.status_code == 200 else []
            out[t] = [
                {
                    'headline': it.get('headline', '')[:200],
                    'summary': (it.get('summary', '') or '')[:400],
                    'datetime': it.get('datetime'),
                    'source': it.get('source', ''),
                }
                for it in (items or [])[:5]
            ]
            print(f'  {t}: {len(out[t])} news')
        except Exception as e:
            out[t] = []
            print(f'  {t}: error {e}', file=sys.stderr)
    return out


def main():
    pf = json.load(open('portfolio.json'))
    tickers = [h['ticker'] for h in pf['portfolios']['us_stocks']['holdings']
               if h.get('shares', 0) > 0]

    raw = fetch_news(tickers, since_days=2)
    if not any(raw.values()):
        print('all empty news — nothing to digest', file=sys.stderr)
        return

    system = "You are Rick, kcn's stock analyst. Distill US holding news into actionable bullets."

    user = (
        "下面 7 个 US holding 过去 48h 的 Finnhub news. 提炼成 markdown digest:\n\n"
        "## 格式 (严格遵守)\n\n"
        "### Top 3-5 移动信号 (跨 ticker 排序)\n"
        "- TICKER: 1 行核心 fact + 1 行 implication for kcn's position\n"
        "- ...\n\n"
        "### Per-ticker 简报 (有新闻才列)\n"
        "- TICKER: 关键事件 - 影响判断 (1 行)\n\n"
        "### 风险 watch (若有)\n"
        "- 任何 financial guidance / regulatory / 大股东减持 / 失败合约 等 risk 关键词\n\n"
        "要求:\n"
        "- 总长 ≤ 500 字 (digest 不是 brief)\n"
        "- 重复 / 营销稿 / 通用市场新闻 -> 忽略\n"
        "- 优先 ticker-specific catalyst (财报 / 合约 / 监管 / 大单)\n"
        "- 不许说 \"需要进一步研究\" 这种废话\n"
        "- 直接出 markdown\n\n"
        f"Raw news (JSON):\n```json\n{json.dumps(raw, ensure_ascii=False)[:25000]}\n```\n"
    )

    digest = chat(system=system, user=user, max_tokens=2000, temperature=0.5)

    out = {
        'generated_at': datetime.now().isoformat(),
        'lookback_hours': 48,
        'tickers': tickers,
        'digest_markdown': digest.strip(),
        'raw_news_counts': {t: len(v) for t, v in raw.items()},
    }
    os.makedirs('assets/data', exist_ok=True)
    with open('assets/data/us_news_digest.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'  digest size: {len(digest)} chars')


if __name__ == '__main__':
    main()
