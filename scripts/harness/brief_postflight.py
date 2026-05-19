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
from datetime import datetime, timedelta
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
    '同行扫描',  # NEW: peer rotation section
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


def validate_markdown(path, context=None):
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

    # NEW: peer-rotation enforcement — divergence_signal in context must be addressed
    if context and context.get('peer_scan'):
        divergence_tickers = [t for t, p in context['peer_scan'].items()
                              if p.get('divergence_signal')]
        unaddressed = [t for t in divergence_tickers if t not in text]
        if unaddressed:
            issues.append(f'pre-open.md 漏写 divergence 信号 ticker: {unaddressed} '
                          f'(preflight 标了 {len(divergence_tickers)} 个，markdown 漏 {len(unaddressed)} 个)')

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


def rebuild_dashboard():
    """Refresh assets/data/dashboard.json so Pages stays in sync."""
    try:
        r = subprocess.run(
            ['python3', str(WS / 'scripts' / 'data' / 'build_dashboard.py')],
            capture_output=True, text=True, timeout=30, cwd=str(WS),
        )
        return r.returncode == 0, (r.stdout + r.stderr)[-300:]
    except Exception as e:
        return False, str(e)


def log_calibration(today):
    """Append today's plan actions to memory/calibration.csv (outcome filled in by future preflight)."""
    import csv
    plan_path = WS / 'memory' / f'{today}-plan.json'
    if not plan_path.exists():
        return
    try:
        plan = json.loads(plan_path.read_text())
    except Exception:
        return
    actions = plan.get('actions', [])
    if not actions:
        return

    calib_path = WS / 'memory' / 'calibration.csv'
    new_file = not calib_path.exists()
    fieldnames = ['plan_date','ticker','bucket','trigger_type','trigger_price',
                  'confidence','sim_entry_price','outcome','pnl_5d','pnl_30d','updated_at']
    rows = []
    if not new_file:
        try:
            with open(calib_path, encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
        except Exception:
            rows = []

    # Skip if this plan_date already logged
    existing = {(r.get('plan_date'), r.get('ticker'), r.get('bucket')) for r in rows}
    appended = 0
    for a in actions:
        key = (today, a.get('ticker'), a.get('bucket'))
        if key in existing:
            continue
        rows.append({
            'plan_date':       today,
            'ticker':          a.get('ticker'),
            'bucket':          a.get('bucket', ''),
            'trigger_type':    a.get('trigger_type', ''),
            'trigger_price':   a.get('trigger_price', ''),
            'confidence':      a.get('confidence', ''),
            'sim_entry_price': a.get('simulated_entry_price', ''),
            'outcome':         'pending',  # filled by future preflight retrospective
            'pnl_5d':          '',
            'pnl_30d':         '',
            'updated_at':      datetime.now().isoformat(),
        })
        appended += 1

    # Retention: drop rows older than 365 days (rolling window)
    cutoff = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    before = len(rows)
    rows = [r for r in rows if r.get('plan_date', '') >= cutoff]
    dropped = before - len(rows)

    if appended or dropped:
        import io, sys
        sys.path.insert(0, str(WS / 'scripts' / 'data'))
        from safe_io import safe_write_text
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
        safe_write_text(str(calib_path), buf.getvalue())
        msg = f'  calibration.csv: +{appended} pending rows'
        if dropped:
            msg += f', -{dropped} old (>365d)'
        msg += f' ({len(rows)} total)'
        print(msg)


def maybe_commit(status, today):
    if status == 'fail':
        return False, 'skipped (status=fail)'

    log_calibration(today)   # append today's plan to calibration log (idempotent)
    rebuild_dashboard()  # refresh dashboard.json before commit

    msg_suffix = ' (validation warnings)' if status == 'warn' else ''
    add_ok, add_out = _git('add', 'memory/', 'portfolio.json', 'assets/data/dashboard.json',
                            'memory/calibration.csv')
    if not add_ok:
        return False, f'git add failed: {add_out[-200:]}'

    commit_ok, commit_out = _git('commit', '-m', f'memory: daily deep brief {today}{msg_suffix}')
    if not commit_ok and 'nothing to commit' in commit_out:
        return True, 'nothing to commit (idempotent)'
    if not commit_ok:
        return False, commit_out[-200:]

    # Push so Pages picks it up; rebase + retry handles races with GH Action commits
    for i in range(1, 4):
        push_ok, push_out = _git('push', 'origin', 'master')
        if push_ok:
            return True, 'committed + pushed'
        _git('pull', '--rebase', 'origin', 'master')
    return True, f'committed (push failed: {push_out[-150:]})'


def _ensure_jekyll_front_matter(md_path, date):
    """Prepend Jekyll front matter so Pages can render the brief in-site (not via github.com blob)."""
    if not md_path.exists():
        return
    try:
        content = md_path.read_text()
    except Exception:
        return
    # Already has valid front matter?
    if content.startswith('---\n') and 'layout:' in content.split('---', 2)[1][:200]:
        return
    # Strip stale empty `---\n\n` if present
    if content.startswith('---\n\n') and 'layout:' not in content[:200]:
        content = content[5:].lstrip()
    fm = f'---\nlayout: default\ntitle: 盘前深度简报 · {date}\n---\n\n'
    md_path.write_text(fm + content)


def main():
    today = datetime.now().strftime('%Y-%m-%d')
    md_path   = WS / 'memory' / f'{today}-pre-open.md'
    plan_path = WS / 'memory' / f'{today}-plan.json'

    # Ensure Jekyll can render this brief as a Pages page (not just GitHub blob jump)
    _ensure_jekyll_front_matter(md_path, today)

    # Load preflight context (for cross-validation)
    ctx_path = WS / 'memory' / '.tmp' / f'brief-context-{today}.json'
    context = None
    if ctx_path.exists():
        try:
            context = json.loads(ctx_path.read_text())
        except Exception:
            pass

    issues = []
    issues += validate_markdown(md_path, context=context)
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
