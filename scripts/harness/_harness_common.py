"""
_harness_common.py — shared helpers for brief/report/intraday harness scripts.

Extracted to avoid duplicating _git / rebuild_dashboard / push retry logic
across multiple postflight scripts. All functions accept the workspace root
as path argument or default to /root/.openclaw/workspace.
"""
import subprocess
import sys
from pathlib import Path

WS = Path('/root/.openclaw/workspace')


def pct(c, pc):
    """Percentage change from pc → c. Returns 0 if pc invalid."""
    if not pc:
        return 0.0
    try:
        return round((float(c) - float(pc)) / float(pc) * 100, 2)
    except Exception:
        return 0.0


def git_cmd(*args, cwd=None):
    """Run git command in workspace. Returns (success_bool, combined_output)."""
    cwd = cwd or WS
    try:
        r = subprocess.run(['git', '-C', str(cwd)] + list(args),
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def refresh_today_snapshot(ws=None):
    """Overwrite memory/snapshots/{date}.json with current portfolio.json.

    Why: brief_preflight writes today's snapshot at 08:00 HKT before HK open,
    so today_change is stale (often negative) by the time the market closes.
    Calling this before rebuild_dashboard keeps the equity curve's last point
    in sync with the live portfolio. Non-fatal on error.

    Date selection (HKT-aware):
      - Mon-Fri:      write today (HK + US markets active)
      - Sat 00-06:    write Fri (US close at ~04:00 HKT belongs to Fri)
      - Sun / Sat 07+: skip (no market activity, would create stale snapshot)

    Returns (ok, snapshot_filename_or_message). On skip returns (False, msg)
    — caller should treat as non-fatal.
    """
    from datetime import datetime, timedelta
    ws = ws or WS
    try:
        pf = ws / 'portfolio.json'
        if not pf.exists():
            return False, 'portfolio.json missing'
        now = datetime.now()
        wd = now.weekday()  # Mon=0 .. Sun=6
        if wd <= 4:
            target = now
        elif wd == 5 and now.hour < 7:
            target = now - timedelta(days=1)
        else:
            return False, f'skipped (weekend: {now.strftime("%a %H:%M")})'
        date = target.strftime('%Y-%m-%d')
        snap = ws / 'memory' / 'snapshots' / f'{date}.json'
        snap.write_bytes(pf.read_bytes())
        return True, snap.name
    except Exception as e:
        return False, str(e)


def snapshot_date_for_now():
    """Returns the date string refresh_today_snapshot would write, or None if
    it would skip. Used by callers (like report_postflight) that need to know
    the snapshot filename for git add. Mirrors refresh_today_snapshot's date logic.
    """
    from datetime import datetime, timedelta
    now = datetime.now()
    wd = now.weekday()
    if wd <= 4:
        return now.strftime('%Y-%m-%d')
    if wd == 5 and now.hour < 7:
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')
    return None


def rebuild_dashboard(ws=None):
    """Re-run build_dashboard.py to refresh assets/data/dashboard.json.

    Refreshes today's snapshot first so the equity curve reflects the latest
    portfolio state (not the early-morning brief_preflight snapshot).

    Returns (ok, last_300_chars_of_output). Failure is non-fatal — caller
    should log but not abort the commit pipeline.
    """
    ws = ws or WS
    refresh_today_snapshot(ws)
    try:
        r = subprocess.run(
            ['python3', str(ws / 'scripts' / 'data' / 'build_dashboard.py')],
            capture_output=True, text=True, timeout=30, cwd=str(ws),
        )
        return r.returncode == 0, (r.stdout + r.stderr)[-300:]
    except Exception as e:
        return False, str(e)


def push_with_rebase_retry(remote='origin', branch='master', attempts=3):
    """git push with rebase+retry on race. Returns (pushed_ok, last_output).

    If rebase itself fails (real conflict on same file), abort rebase and stop —
    don't loop forever. Manual resolution will be needed.
    """
    last_out = ''
    for i in range(1, attempts + 1):
        ok, out = git_cmd('push', remote, branch)
        if ok:
            return True, out
        last_out = out
        # Race with another cron commit — try rebase
        rebase_ok, rebase_out = git_cmd('pull', '--rebase', remote, branch)
        if not rebase_ok:
            # Conflict — don't loop, leave commit local for manual resolution
            git_cmd('rebase', '--abort')  # cleanup
            return False, f'rebase conflict (manual resolution needed): {rebase_out[-200:]}'
    return False, last_out


def safe_write_text(path, text):
    """Re-export safe_io.safe_write_text for harness scripts.

    Avoids importing scripts/data/safe_io.py path-juggling in each postflight.
    """
    sys.path.insert(0, str(WS / 'scripts' / 'data'))
    from safe_io import safe_write_text as _swt  # type: ignore
    _swt(str(path), text)
