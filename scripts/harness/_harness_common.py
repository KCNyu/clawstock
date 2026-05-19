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


def rebuild_dashboard(ws=None):
    """Re-run build_dashboard.py to refresh assets/data/dashboard.json.

    Returns (ok, last_300_chars_of_output). Failure is non-fatal — caller
    should log but not abort the commit pipeline.
    """
    ws = ws or WS
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
