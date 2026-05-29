#!/usr/bin/env python3
"""
report_watchdog.py — LLM-free safety net for Mode 6 report crons.

WHY (2026-05-29 incident): the HK close cron's primary model (MiniMax-M2.7)
returned an empty `non_deliverable_terminal_turn`, fell back to xiaomi
mimo-v2.5-pro, which then stalled mid-turn — it emitted only
"Preflight data is already available. Let me read the context file to
proceed with Step 2." and never wrote the report. openclaw core delivered
that one-line stub to WeChat as the "report", and because it was non-empty
the run was marked delivered=true with no failure signal. kcn got a useless
stub instead of the close briefing — even though preflight had already
produced a perfectly good `raw_wechat_block`.

postflight can't catch this: the LLM died in Step 2, long before postflight
runs. So this watchdog runs OUT OF BAND (system crontab, a few minutes after
the report cron's expected completion) and asks one question:

    Did the report cron actually deliver today's report?

It decides by checking whether the latest run of the target cron job (today)
has a summary that contains the verbatim first line of preflight's
`raw_wechat_block`. If not — the LLM stalled/failed — it re-sends the
`raw_wechat_block` directly via `openclaw message send` (data only, clearly
banner-flagged as an auto-resend; no analysis sections, since this path
never touches an LLM). A dedupe flag prevents double-sends.

This is a data-delivery safety net, NOT a per-cron failure alert — kcn does
not want individual cron alerts (see feedback_no_individual_cron_alerts), and
this only ever fires to deliver correct content kcn was supposed to receive.

Usage:
    report_watchdog.py --market hk --phase close --job-name "港股收盘报告"
    report_watchdog.py --market us --phase close --job-name "美股收盘报告" --dry-run

Exit 0 always (non-fatal cron); actions are logged to logs/watchdog.jsonl.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Workspace root, resolved from this file's location (location-independent;
# matches the old hardcoded /root path locally, robust if run elsewhere).
WS = Path(__file__).resolve().parents[2]
OC = Path('/root/.openclaw')
TMP = WS / 'memory' / '.tmp'
RUNS_DIR = OC / 'cron' / 'runs'
JOBS_JSON = OC / 'cron' / 'jobs.json'
LOG = WS / 'logs' / 'watchdog.jsonl'
HKT = timezone(timedelta(hours=8))
OPENCLAW_BIN = '/root/.local/share/pnpm/openclaw'


def log(event):
    """Append one JSON line to the watchdog log. Never raises."""
    try:
        event['ts'] = datetime.now(HKT).isoformat()
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f'(watchdog log failed: {e})', file=sys.stderr)


def load_jobs():
    data = json.loads(JOBS_JSON.read_text())
    return data if isinstance(data, list) else data.get('jobs', data.get('items', []))


def find_job_id(job_name):
    for j in load_jobs():
        if isinstance(j, dict) and j.get('name') == job_name:
            return j.get('id')
    return None


def read_runs(job_id):
    """Return list of run records (one finished record per line) for a job."""
    path = RUNS_DIR / f'{job_id}.jsonl'
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def is_today_hkt(ts_ms):
    if not isinstance(ts_ms, (int, float)):
        return False
    d = datetime.fromtimestamp(ts_ms / 1000, HKT).date()
    return d == datetime.now(HKT).date()


def resolve_target(runs):
    """Pull the WeChat delivery target from the job's own most recent
    successful delivery, so we send to wherever this job normally sends
    (no hardcoded account that rots when the bot is re-paired)."""
    for r in reversed(runs):
        d = (r.get('delivery') or {}).get('resolved') or {}
        if d.get('ok') and d.get('to'):
            return d.get('channel'), d.get('to'), d.get('accountId')
    return None, None, None


def send_wechat(channel, to, account, message, dry_run):
    cmd = [OPENCLAW_BIN, 'message', 'send',
           '--channel', channel, '--target', to, '-m', message, '--json']
    if account:
        cmd[3:3] = ['--account', account]
    if dry_run:
        cmd.append('--dry-run')
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    ok = r.returncode == 0
    return ok, (r.stdout + r.stderr)[-400:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--market', choices=['hk', 'us'], required=True)
    ap.add_argument('--phase', choices=['open', 'mid', 'pm', 'close'], required=True)
    ap.add_argument('--job-name', required=True, help='cron job name to inspect')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    today = datetime.now(HKT).strftime('%Y-%m-%d')
    tag = f'{args.market}-{args.phase}'

    # Preflight context (with the canonical raw_wechat_block) must exist —
    # if it doesn't, preflight itself never ran; there's nothing to resend.
    ctx_path = TMP / f'report-context-{args.market}-{args.phase}-{today}.json'
    if not ctx_path.exists():
        log({'tag': tag, 'action': 'skip', 'reason': 'no preflight context (cron likely never ran)'})
        return 0
    ctx = json.loads(ctx_path.read_text())
    raw = (ctx.get('raw_wechat_block') or '').strip()
    if not raw:
        log({'tag': tag, 'action': 'skip', 'reason': 'context has no raw_wechat_block'})
        return 0
    first_line = raw.splitlines()[0]

    job_id = find_job_id(args.job_name)
    if not job_id:
        log({'tag': tag, 'action': 'skip', 'reason': f'job not found: {args.job_name}'})
        return 0

    runs = read_runs(job_id)
    today_runs = [r for r in runs if is_today_hkt(r.get('ts'))]
    last_summary = today_runs[-1].get('summary', '') if today_runs else ''

    delivered_ok = first_line in last_summary
    if delivered_ok:
        log({'tag': tag, 'action': 'ok', 'reason': 'report delivered normally'})
        return 0

    # LLM stalled/failed (or cron never produced a run). Resend the data block.
    flag = TMP / f'watchdog-{tag}-{today}.done'
    if flag.exists():
        log({'tag': tag, 'action': 'skip', 'reason': 'already resent (dedupe flag present)'})
        return 0

    channel, to, account = resolve_target(runs)
    if not to:
        log({'tag': tag, 'action': 'fail', 'reason': 'no delivery target resolved from run history'})
        return 0

    title = ctx.get('title', '').strip()
    banner = ('📨 自动补发（报告模型生成失败/中断，以下为脚本数据直送，'
              '无分析段——可在 dashboard 看完整持仓）\n\n')
    message = banner + (title + '\n\n' if title else '') + raw

    sent_ok, out = send_wechat(channel, to, account, message, args.dry_run)
    log({'tag': tag, 'action': 'resend', 'dry_run': args.dry_run,
         'sent_ok': sent_ok, 'job_id': job_id,
         'last_summary_head': last_summary[:80], 'out': out})

    if sent_ok and not args.dry_run:
        flag.write_text(datetime.now(HKT).isoformat())

    print(json.dumps({'tag': tag, 'delivered_ok': delivered_ok,
                      'resent': sent_ok, 'dry_run': args.dry_run},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
