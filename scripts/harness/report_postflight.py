#!/usr/bin/env python3
"""
report_postflight.py — Mode 6 (briefing) harness postflight.

Validates the LLM-generated WeChat briefing AFTER it's been written.

Usage: read the briefing text from stdin (preferred for cron),
       or pass --text-file PATH.

Validates:
  1. ▎情绪面 / ▎技术面 / ▎操作建议 三段标记齐全
  2. 若 preflight needs_risk_section=true, 必须有 ▎风险提示 段
  3. 总长度 ≤ 1200 字 (warn) / ≤ 1500 字 (fail) — HK + US 统一（2026-05-21 起）
  4. 必须以 raw_wechat_block 开头（脚本数据块 verbatim，禁止编造）
  5. 如果 preflight 有 anomalies，报告必须提到至少一个 anomaly 票
  6. 没有"等待数据/数据待获取"等敷衍词

Side effects:
  - status=pass/warn: git add portfolio.json && git commit -m "{commit_msg}"
  - status=fail: no commit, return non-zero

Outputs JSON to stdout:
  {"status": "pass|warn|fail", "issues": [...], "wechat_prefix": "..."}
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WS = Path('/root/.openclaw/workspace')
TMP = WS / 'memory' / '.tmp'

REQUIRED_SECTIONS = ['▎情绪面', '▎技术面', '▎操作建议']
FORBIDDEN_PHRASES = ['数据待获取', '等待数据', '数据缺失（占位）', 'TODO', 'TBD']

# Char limits — HK + US 统一 1200/1500（2026-05-21 起，与 Mode 7 intraday 对齐）
CHAR_LIMITS = {
    'hk': {'soft': 1200, 'hard': 1500},
    'us': {'soft': 1200, 'hard': 1500},
}


def load_context(market, phase, date):
    path = TMP / f'report-context-{market}-{phase}-{date}.json'
    if not path.exists():
        return None, f'preflight context 不存在: {path.name}'
    try:
        return json.loads(path.read_text()), None
    except Exception as e:
        return None, f'preflight context 解析失败: {e}'


def validate(text, ctx):
    issues = []

    # 1. raw block 必须 verbatim 出现
    raw = ctx.get('raw_wechat_block', '').strip()
    if raw:
        first_line = raw.splitlines()[0]
        if first_line not in text:
            issues.append(f'报告未包含原始数据块首行 "{first_line[:40]}..." (verbatim 验证失败)')

    # 2. 必有三段标记
    for sec in REQUIRED_SECTIONS:
        if sec not in text:
            issues.append(f'缺段标记 "{sec}"')

    # 3. 风险提示段（若 preflight 标了 needs）
    if ctx.get('needs_risk_section') and '▎风险提示' not in text:
        issues.append('preflight 标 needs_risk_section=true 但未见 "▎风险提示" 段')

    # 4. 长度 (per-market)
    n_chars = len(text)
    limits = CHAR_LIMITS.get(ctx.get('market', 'hk'), CHAR_LIMITS['hk'])
    soft, hard = limits['soft'], limits['hard']
    if n_chars > hard:
        issues.append(f'报告长度 {n_chars} 字 > {hard} 上限')
    elif n_chars > soft:
        issues.append(f'报告长度 {n_chars} 字 > {soft} 软上限 (warn)')

    # 5. 异动票必须被提到
    anomalies = ctx.get('anomalies', [])
    if anomalies:
        mentioned = [a['ticker'] for a in anomalies if a['ticker'] in text]
        if not mentioned:
            tickers = ', '.join(a['ticker'] for a in anomalies)
            issues.append(f'preflight 标了 {len(anomalies)} 个 ≥3% 异动票 ({tickers}) 但报告全部未提及')

    # 6. 敷衍 phrases
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            issues.append(f'报告含敷衍词 "{phrase}"')

    return issues


def categorize(issues):
    if not issues:
        return 'pass'
    has_critical = any(
        '缺段标记' in i or '未包含原始数据块' in i
        or ('字 >' in i and '上限' in i and '软上限' not in i)  # hard char limit hit
        or '敷衍词' in i
        for i in issues
    )
    if has_critical:
        return 'fail'
    return 'warn' if len(issues) <= 3 else 'fail'


sys.path.insert(0, str(Path(__file__).parent))
from _harness_common import git_cmd as _git, rebuild_dashboard, push_with_rebase_retry  # noqa: E402


def maybe_commit(status, commit_msg):
    if status == 'fail':
        return False, 'skipped (status=fail)'
    rebuild_dashboard()
    suffix = ' (validation warnings)' if status == 'warn' else ''
    ok, _ = _git('add', 'portfolio.json', 'assets/data/dashboard.json')
    if not ok:
        return False, 'git add failed'
    ok, out = _git('commit', '-m', f'{commit_msg}{suffix}')
    if not ok and 'nothing to commit' in out:
        return True, 'nothing to commit (idempotent)'
    if not ok:
        return False, out[-200:]

    # Push so Pages updates; rebase+retry handles races with GH Action commits
    push_ok, push_out = push_with_rebase_retry()
    if push_ok:
        return True, 'committed + pushed'
    return True, f'committed (push failed: {push_out[-150:]})'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--market', choices=['hk', 'us'], required=True)
    parser.add_argument('--phase', choices=['open', 'mid', 'pm', 'close'], required=True)
    parser.add_argument('--text-file', help='briefing text file (default: stdin)')
    args = parser.parse_args()

    if args.text_file:
        text = Path(args.text_file).read_text()
    else:
        text = sys.stdin.read()

    today = datetime.now().strftime('%Y-%m-%d')
    ctx, ctx_err = load_context(args.market, args.phase, today)

    if ctx is None:
        result = {
            'status': 'fail',
            'issues': [ctx_err],
            'wechat_prefix': f'🔴 postflight 异常: {ctx_err}\n\n',
            'commit_ok': False,
            'commit_msg': 'skipped (no preflight context)',
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    issues = validate(text, ctx)
    status = categorize(issues)

    if status == 'pass':
        wechat_prefix = ''
    elif status == 'warn':
        wechat_prefix = (f'⚠️ Validation warnings ({len(issues)}): '
                         + '; '.join(issues[:3])
                         + ('; ...' if len(issues) > 3 else '')
                         + '\n\n')
    else:
        wechat_prefix = (f'🔴 Validation FAILED ({len(issues)} issues), 报告仍发布但未 commit:\n'
                         + '\n'.join('- ' + i for i in issues[:5])
                         + ('\n- ...' if len(issues) > 5 else '')
                         + '\n\n')

    commit_ok, commit_msg = maybe_commit(status, ctx['commit_msg'])

    result = {
        'status':        status,
        'market':        args.market,
        'phase':         args.phase,
        'date':          today,
        'issues':        issues,
        'wechat_prefix': wechat_prefix,
        'commit_ok':     commit_ok,
        'commit_msg':    commit_msg,
        'n_chars':       len(text),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status == 'pass' else (1 if status == 'warn' else 2)


if __name__ == '__main__':
    sys.exit(main())
