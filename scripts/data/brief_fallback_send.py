#!/usr/bin/env python3
"""
brief_fallback_send.py — manual 1027 / partial-output recovery for daily brief.

When MiniMax `output new_sensitive (1027)` truncates the brief cron to a half
sentence and openclaw still marks it delivered, kcn sees a useless WeChat msg.
This script reads today's already-written pre-open.md + plan.json (preflight
+ LLM-written files are usually on disk before the truncation), composes a
WeChat-friendly TL;DR + key sections, and sends via openclaw message CLI.

Usage:
    python3 scripts/data/brief_fallback_send.py            # send today
    python3 scripts/data/brief_fallback_send.py --date 2026-05-26
    python3 scripts/data/brief_fallback_send.py --dry-run  # print, don't send

Per memory openclaw-minimax-sensitive-1027.md — the canonical recovery path
when diagnostics.summary contains "output new_sensitive (1027)".
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WS = Path('/root/.openclaw/workspace')

# Hardcoded per openclaw.json channels.openclaw-weixin — recovery target is kcn's
# personal WeChat (the only routing the cron itself uses).
CHANNEL = 'openclaw-weixin'
ACCOUNT = '61bf112daf0d-im-bot'
TARGET = 'o9cq80-hGTruM-OSs8kNmDOtLVZI@im.wechat'

MAX_LEN = 1200  # match brief soft limit; WeChat truncates long msgs anyway


def extract_section(md_text, header_token):
    """Pull a `▎{header}` section body (until next ▎ or EOF). Best-effort."""
    m = re.search(rf'▎\s*{re.escape(header_token)}[^\n]*\n(.*?)(?=\n▎|\Z)', md_text, re.DOTALL)
    return m.group(1).strip() if m else ''


def extract_tldr(md_text):
    """Pull TL;DR line(s) if present near the top."""
    m = re.search(r'(?:^|\n)▎?\s*TL;DR[^\n]*\n(.*?)(?=\n▎|\n##|\Z)', md_text, re.DOTALL)
    return m.group(1).strip() if m else ''


def compose_fallback(date):
    md_path = WS / 'memory' / f'{date}-pre-open.md'
    plan_path = WS / 'memory' / f'{date}-plan.json'

    if not md_path.exists():
        return None, f'pre-open.md 缺失: {md_path}'

    md = md_path.read_text()
    plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}

    parts = [f'📊 盘前简报 fallback｜{date}（1027 触发，原 brief 被腰斩，自动重发）\n']

    tldr = extract_tldr(md)
    if tldr:
        parts.append(f'▎TL;DR\n{tldr[:400]}\n')

    for section in ('Judge', '操作建议', 'Next-Session'):
        body = extract_section(md, section)
        if body:
            parts.append(f'▎{section}\n{body[:400]}\n')

    actions = plan.get('actions', [])
    if actions:
        lines = ['▎Actions (plan.json)']
        for a in actions[:6]:
            ticker = a.get('ticker', '?')
            bucket = a.get('bucket', '?')
            trigger = a.get('trigger_type', '?')
            tp = a.get('trigger_price', '')
            conf = a.get('confidence', '')
            lines.append(f'  {ticker} | {bucket} | {trigger}{f" @{tp}" if tp else ""}'
                         f'{f" (conf={conf})" if conf != "" else ""}')
        parts.append('\n'.join(lines) + '\n')

    parts.append(f'\n完整 brief 见 GitHub Pages 或 memory/{date}-pre-open.md')

    text = '\n'.join(parts)
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 30] + '\n…\n(超长，看完整 pre-open.md)'
    return text, None


def send_via_openclaw(text):
    cmd = [
        'openclaw', 'message', 'send',
        '--channel', CHANNEL,
        '--account', ACCOUNT,
        '--target', TARGET,
        '--message', text,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.returncode == 0, (r.stdout + r.stderr)[-400:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'))
    parser.add_argument('--dry-run', action='store_true',
                        help='print fallback text without sending')
    args = parser.parse_args()

    text, err = compose_fallback(args.date)
    if err:
        print(f'compose failed: {err}', file=sys.stderr)
        return 2

    print(f'--- fallback text ({len(text)} chars) ---')
    print(text)
    print('---')

    if args.dry_run:
        print('[dry-run] not sent')
        return 0

    ok, out = send_via_openclaw(text)
    print(f'send: {"ok" if ok else "FAILED"}')
    if not ok:
        print(out, file=sys.stderr)
        return 1
    print(out[:200])
    return 0


if __name__ == '__main__':
    sys.exit(main())
