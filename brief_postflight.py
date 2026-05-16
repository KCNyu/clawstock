#!/usr/bin/env python3
"""
brief_postflight.py — validate LLM outputs + commit if pass.

Runs AFTER the agent writes memory/{date}-pre-open.md + memory/{date}-plan.json.

Validates:
  1. plan.json schema (required fields, valid enums, confidence 0-1)
  2. pre-open.md required sections (Header / Tier 1 / Tier 2 / Tier 3 / Judge / Confidence / Next-Session)
  3. Sanity: no HKD+USD direct-sum errors (historical bug)
  4. Sanity: concentration HHI was actually mentioned (preflight provided it)

Outputs JSON to stdout:
  {"status": "pass|warn|fail", "issues": [...], "wechat_prefix": "..."}

Side effects:
  - status=pass: git add memory/ portfolio.json + commit
  - status=warn: same as pass but commit msg flags validation warnings
  - status=fail: no commit (preserve commit history clean); print issues
"""

import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path

WS = Path('/root/.openclaw/workspace')

VALID_BUCKETS = {
    'cut', 'trim_on_rebound', 'hold_and_watch', 't_only', 'add_only_on_trigger',
}
VALID_TRIGGER_TYPES = {
    'open', 'price_above', 'price_below', 'index_breakdown', 'event', 'manual',
}
REQUIRED_MARKDOWN_TOKENS = [
    'Header', 'Tier 1', 'Tier 2', 'Tier 3', 'Judge', 'Confidence', 'Next-Session',
]
HKD_USD_BUG_PATTERNS = [
    '合计 -4423', '合计 -4,423', '合计 -4423.0',
]


def validate_plan_json(path):
    if not path.exists():
        return ['plan.json 缺失（critical）']
    try:
        plan = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [f'plan.json 解析失败: {e}']

    issues = []
    for field in ('date', 'fx_rate_usdhkd', 'actions'):
        if field not in plan:
            issues.append(f'plan.json 缺顶层字段 "{field}"')

    actions = plan.get('actions', [])
    if not isinstance(actions, list) or not actions:
        issues.append('plan.json actions 空或非 list')
        return issues

    for i, a in enumerate(actions):
        tag = f'plan.json action[{i}] ({a.get("ticker", "?")})'
        if not a.get('ticker'):
            issues.append(f'{tag}: 缺 ticker')
        if a.get('bucket') not in VALID_BUCKETS:
            issues.append(f'{tag}: bucket "{a.get("bucket")}" 不合法')
        if a.get('trigger_type') not in VALID_TRIGGER_TYPES:
            issues.append(f'{tag}: trigger_type "{a.get("trigger_type")}" 不合法')
        conf = a.get('confidence')
        if conf is not None and not (0.0 <= float(conf) <= 1.0):
            issues.append(f'{tag}: confidence {conf} 不在 [0, 1]')
    return issues


def validate_markdown(path):
    if not path.exists():
        return ['pre-open.md 缺失（critical）']
    try:
        text = path.read_text()
    except Exception as e:
        return [f'pre-open.md 读取失败: {e}']

    issues = []
    for token in REQUIRED_MARKDOWN_TOKENS:
        if token not in text:
            issues.append(f'pre-open.md 缺段标记 "{token}"')

    for bug in HKD_USD_BUG_PATTERNS:
        if bug in text:
            issues.append(f'pre-open.md 出现历史 bug 模式 "{bug}" (HKD+USD 直接相加)')

    if 'HHI' not in text and 'hhi' not in text:
        issues.append('pre-open.md 未提及 HHI（集中度风险段漏掉？）')

    if 'USDHKD' not in text and 'FX' not in text and '汇率' not in text:
        issues.append('pre-open.md 未提及 FX rate / 汇率')

    return issues


def categorize(issues):
    if not issues:
        return 'pass'
    has_critical = any('缺失' in i or '解析失败' in i for i in issues)
    if has_critical:
        return 'fail'
    return 'warn' if len(issues) <= 4 else 'fail'


def _git(*args):
    try:
        r = subprocess.run(['git', '-C', str(WS)] + list(args),
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def maybe_commit(status, today):
    if status == 'fail':
        return False, 'skipped (status=fail)'

    msg_suffix = ' (validation warnings)' if status == 'warn' else ''
    add_ok, add_out = _git('add', 'memory/', 'portfolio.json')
    if not add_ok:
        return False, f'git add failed: {add_out[-200:]}'

    commit_ok, commit_out = _git('commit', '-m', f'memory: daily deep brief {today}{msg_suffix}')
    if not commit_ok and 'nothing to commit' in commit_out:
        return True, 'nothing to commit (idempotent)'
    return commit_ok, commit_out[-200:] if not commit_ok else 'committed'


def main():
    today = datetime.now().strftime('%Y-%m-%d')
    md_path   = WS / 'memory' / f'{today}-pre-open.md'
    plan_path = WS / 'memory' / f'{today}-plan.json'

    issues = []
    issues += validate_markdown(md_path)
    issues += validate_plan_json(plan_path)

    status = categorize(issues)

    if status == 'pass':
        wechat_prefix = ''
    elif status == 'warn':
        wechat_prefix = (f'⚠️ Validation warnings ({len(issues)}): '
                         + '; '.join(issues[:3])
                         + ('; ...' if len(issues) > 3 else '')
                         + '\n\n')
    else:
        wechat_prefix = (f'🔴 Validation FAILED ({len(issues)} issues), brief 仍发布但未 commit:\n'
                         + '\n'.join('- ' + i for i in issues[:5])
                         + ('\n- ...' if len(issues) > 5 else '')
                         + '\n\n')

    commit_ok, commit_msg = maybe_commit(status, today)

    result = {
        'status':        status,
        'date':          today,
        'issues':        issues,
        'wechat_prefix': wechat_prefix,
        'commit_ok':     commit_ok,
        'commit_msg':    commit_msg,
        'files_checked': {
            'pre_open_md':  str(md_path),
            'plan_json':    str(plan_path),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status == 'pass' else (1 if status == 'warn' else 2)


if __name__ == '__main__':
    sys.exit(main())
