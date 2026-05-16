#!/usr/bin/env python3
"""
intraday_postflight.py — Mode 7 (intraday) harness postflight.

Validates the LLM-generated intraday check-in.

Usage: pipe brief text via stdin, or --text-file PATH.

Validates:
  1. ▎我的看法 段必须存在
  2. 总长度 ≤ 600 字 (warn), ≤ 1000 字 (fail)
  3. 必须以 raw_wechat_block 开头 (verbatim)
  4. 若 preflight should_alert=true：报告必须提到至少一个异动票或 alert_reason
  5. 无敷衍 phrases

Note: Mode 7 does NOT git commit (per SKILL.md; cron runs */30 too noisy to commit each time).
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

WS = Path('/root/.openclaw/workspace')
TMP = WS / 'memory' / '.tmp'

REQUIRED_SECTION = '▎我的看法'
FORBIDDEN_PHRASES = ['数据待获取', '等待数据', 'TODO', 'TBD']


def load_context(market):
    path = TMP / f'intraday-context-{market}-latest.json'
    if not path.exists():
        return None, f'preflight latest context 不存在: {path.name}'
    try:
        return json.loads(path.read_text()), None
    except Exception as e:
        return None, f'context 解析失败: {e}'


def validate(text, ctx):
    issues = []

    raw = ctx.get('raw_wechat_block', '').strip()
    if raw:
        first_line = raw.splitlines()[0]
        if first_line not in text:
            issues.append(f'报告未包含原始数据块首行 "{first_line[:40]}..." (verbatim 失败)')

    if REQUIRED_SECTION not in text:
        issues.append(f'缺段标记 "{REQUIRED_SECTION}"')

    n = len(text)
    if n > 1000:
        issues.append(f'报告长度 {n} 字 > 1000 上限')
    elif n > 600:
        issues.append(f'报告长度 {n} 字 > 600 软上限 (warn)')

    if ctx.get('should_alert'):
        anomaly_tickers = [a['ticker'] for a in ctx.get('anomalies', [])]
        mentioned = [t for t in anomaly_tickers if t in text]
        if anomaly_tickers and not mentioned:
            issues.append(f'should_alert=true 但报告未提任何异动票 ({", ".join(anomaly_tickers)})')

    for p in FORBIDDEN_PHRASES:
        if p in text:
            issues.append(f'报告含敷衍词 "{p}"')

    return issues


def categorize(issues):
    if not issues:
        return 'pass'
    has_critical = any(
        '缺段标记' in i or '未包含原始数据块' in i or '> 1000' in i or '敷衍词' in i
        for i in issues
    )
    if has_critical:
        return 'fail'
    return 'warn' if len(issues) <= 2 else 'fail'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--market', choices=['hk', 'us'], required=True)
    parser.add_argument('--text-file', help='briefing text file (default: stdin)')
    args = parser.parse_args()

    text = Path(args.text_file).read_text() if args.text_file else sys.stdin.read()

    ctx, err = load_context(args.market)
    if ctx is None:
        result = {
            'status': 'fail',
            'issues': [err],
            'wechat_prefix': f'🔴 postflight 异常: {err}\n\n',
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    issues = validate(text, ctx)
    status = categorize(issues)

    if status == 'pass':
        wechat_prefix = ''
    elif status == 'warn':
        wechat_prefix = (f'⚠️ Validation warnings ({len(issues)}): '
                         + '; '.join(issues[:2])
                         + '\n\n')
    else:
        wechat_prefix = (f'🔴 Validation FAILED ({len(issues)} issues):\n'
                         + '\n'.join('- ' + i for i in issues[:4])
                         + '\n\n')

    result = {
        'status':        status,
        'market':        args.market,
        'time':          datetime.now().strftime('%H:%M'),
        'issues':        issues,
        'wechat_prefix': wechat_prefix,
        'n_chars':       len(text),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status == 'pass' else (1 if status == 'warn' else 2)


if __name__ == '__main__':
    sys.exit(main())
