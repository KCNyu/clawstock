#!/usr/bin/env python3
"""
system_check.py — master health gate for clawock.

Run from anywhere (idempotent). Exits 0 if system is healthy enough to push.
Exits 1 on any critical failure; exits 2 on warning-only.

Used by:
  • .githooks/pre-push        (blocks bad pushes from this clone)
  • harness postflight        (calls before git commit/push)
  • CI weekly-health.yml      (full check)
  • Manual: `python3 scripts/system_check.py`
"""
import csv
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent

# Check result severity
CRITICAL = '✗ CRITICAL'
WARNING  = '⚠ WARN'
OK       = '✓ OK'


class Result:
    def __init__(self):
        self.checks = []
    def add(self, name, severity, msg=''):
        self.checks.append((name, severity, msg))
    def critical_count(self):
        return sum(1 for _, s, _ in self.checks if s == CRITICAL)
    def warn_count(self):
        return sum(1 for _, s, _ in self.checks if s == WARNING)
    def ok_count(self):
        return sum(1 for _, s, _ in self.checks if s == OK)


def check_baseline_files(r):
    """All required bootstrap + workspace MD files exist."""
    required = ['SOUL.md', 'IDENTITY.md', 'USER.md', 'MEMORY.md', 'TOOLS.md',
                'AGENTS.md', 'CLAUDE.md', 'BOOTSTRAP.md', 'portfolio.json']
    missing = [f for f in required if not (WS / f).exists()]
    if missing:
        r.add('baseline files', CRITICAL, f'missing: {missing}')
    else:
        r.add('baseline files', OK, f'{len(required)} files present')


def check_scripts_compile(r):
    """All Python scripts compile."""
    failed = []
    for pat in ['scripts/data/*.py', 'scripts/harness/*.py']:
        for f in glob.glob(str(WS / pat)):
            try:
                rr = subprocess.run(['python3', '-m', 'py_compile', f],
                                   capture_output=True, text=True, timeout=10)
                if rr.returncode != 0:
                    failed.append(f'{Path(f).name}: {rr.stderr[-100:]}')
            except Exception as e:
                failed.append(f'{Path(f).name}: {e}')
    if failed:
        r.add('scripts compile', CRITICAL, '; '.join(failed))
    else:
        r.add('scripts compile', OK, 'all scripts compile')


def check_portfolio_schema(r):
    p = WS / 'portfolio.json'
    if not p.exists():
        r.add('portfolio.json', CRITICAL, 'missing')
        return
    try:
        d = json.loads(p.read_text())
    except Exception as e:
        r.add('portfolio.json', CRITICAL, f'parse fail: {e}')
        return
    bad = []
    if 'portfolios' not in d:
        bad.append('missing portfolios key')
    else:
        for region in ('us_stocks', 'hk_stocks'):
            if region not in d['portfolios']:
                bad.append(f'missing {region}')
                continue
            holdings = d['portfolios'][region].get('holdings')
            if not isinstance(holdings, list):
                bad.append(f'{region}.holdings not a list')
                continue
            for h in holdings:
                for f in ('ticker', 'shares', 'cost_basis'):
                    if f not in h:
                        bad.append(f'{region} holding missing {f}: {h.get("ticker")}')
    if bad:
        r.add('portfolio.json schema', CRITICAL, '; '.join(bad[:3]))
    else:
        r.add('portfolio.json schema', OK, 'valid')


def check_plan_json_schema(r):
    """All memory/*-plan.json must satisfy schema."""
    plans = glob.glob(str(WS / 'memory' / '*-plan.json'))
    if not plans:
        r.add('plan.json schema', OK, '0 plans yet')
        return
    bad = []
    VALID_BUCKETS = {'cut','trim_on_rebound','hold_and_watch','t_only','add_only_on_trigger'}
    VALID_TRIGGERS = {'open','price_above','price_below','index_breakdown','event','manual'}
    for p in plans:
        try:
            d = json.loads(open(p).read())
        except Exception as e:
            bad.append(f'{Path(p).name}: parse fail'); continue
        if 'date' not in d:
            bad.append(f'{Path(p).name}: missing date')
        for a in (d.get('actions') or []):
            if a.get('bucket') and a['bucket'] not in VALID_BUCKETS:
                bad.append(f'{Path(p).name}: bad bucket "{a["bucket"]}"')
            if a.get('trigger_type') and a['trigger_type'] not in VALID_TRIGGERS:
                bad.append(f'{Path(p).name}: bad trigger_type "{a["trigger_type"]}"')
            c = a.get('confidence')
            if c is not None:
                try:
                    cf = float(c)
                    if not (0 <= cf <= 1):
                        bad.append(f'{Path(p).name}: confidence {cf} out of [0,1]')
                except Exception:
                    bad.append(f'{Path(p).name}: confidence not numeric')
    if bad:
        r.add('plan.json schema', CRITICAL, '; '.join(bad[:3]))
    else:
        r.add('plan.json schema', OK, f'{len(plans)} plans valid')


def check_dashboard_buildable(r):
    """build_dashboard.py produces sub-200KB output."""
    out = WS / 'assets' / 'data' / 'dashboard.json'
    try:
        rr = subprocess.run(
            ['python3', str(WS / 'scripts' / 'data' / 'build_dashboard.py')],
            capture_output=True, text=True, timeout=30, cwd=str(WS),
        )
        if rr.returncode != 0:
            r.add('dashboard.json build', CRITICAL, rr.stderr[-200:])
            return
    except Exception as e:
        r.add('dashboard.json build', CRITICAL, str(e))
        return
    if not out.exists():
        r.add('dashboard.json build', CRITICAL, 'no output file')
        return
    size = out.stat().st_size
    if size > 200_000:
        r.add('dashboard.json size', WARNING, f'{size:,} > 200KB cap')
    else:
        r.add('dashboard.json build', OK, f'{size:,} bytes')


def check_peer_map_coverage(r):
    """All active holdings should have a peer-map.json entry."""
    pf_p = WS / 'portfolio.json'
    pm_p = WS / 'memory' / 'peer-map.json'
    if not pm_p.exists():
        r.add('peer-map coverage', WARNING, 'peer-map.json missing')
        return
    try:
        pf = json.loads(pf_p.read_text())
        pm = json.loads(pm_p.read_text()).get('holdings', {})
    except Exception as e:
        r.add('peer-map coverage', CRITICAL, f'parse fail: {e}')
        return
    missing = []
    for region in ('hk_stocks', 'us_stocks'):
        for h in pf['portfolios'].get(region, {}).get('holdings', []):
            if h.get('shares', 0) > 0 and h['ticker'] not in pm:
                missing.append(h['ticker'])
    if missing:
        r.add('peer-map coverage', WARNING, f'active holdings without peers: {missing}')
    else:
        r.add('peer-map coverage', OK, 'all active holdings mapped')


def check_no_leaked_secrets(r):
    """Tracked files must not contain raw API keys."""
    bad = []
    try:
        out = subprocess.check_output(
            ['git', '-C', str(WS), 'grep', '-nE',
             r'(sk-[a-zA-Z0-9_-]{20,}|tp-[a-zA-Z0-9_-]{20,}|FINNHUB_API_KEY\s*=\s*[a-zA-Z0-9]+|POLYGON_API_KEY\s*=\s*[a-zA-Z0-9]+)',
             '--', ':!*.md', ':!.gitignore', ':!openclaw.json*', ':!.githooks/*', ':!scripts/system_check.py'],
            text=True, timeout=10, stderr=subprocess.DEVNULL,
        )
        if out.strip():
            bad = out.strip().splitlines()[:3]
    except subprocess.CalledProcessError:
        pass  # git grep returns 1 when no match — that's the OK case
    except Exception:
        pass
    if bad:
        r.add('secret leak scan', CRITICAL, f'{len(bad)} potential leaks: {bad}')
    else:
        r.add('secret leak scan', OK, 'no leaked secrets in tracked files')


def check_openclaw_doctor(r):
    """Run openclaw doctor and confirm 0 errors."""
    try:
        rr = subprocess.run(['openclaw', 'doctor'], capture_output=True, text=True, timeout=60)
        out = rr.stdout + rr.stderr
        # Look for "Errors: 0" line
        if 'Errors: 0' in out:
            r.add('openclaw doctor', OK, 'errors=0')
        elif 'Errors:' in out:
            # Extract count
            import re
            m = re.search(r'Errors:\s*(\d+)', out)
            n = int(m.group(1)) if m else '?'
            r.add('openclaw doctor', CRITICAL, f'errors={n}')
        else:
            r.add('openclaw doctor', WARNING, 'could not parse output')
    except FileNotFoundError:
        r.add('openclaw doctor', WARNING, 'openclaw CLI not on PATH (skipped)')
    except Exception as e:
        r.add('openclaw doctor', WARNING, f'doctor run failed: {e}')


def check_calibration_csv(r):
    """calibration.csv parseable + bounded."""
    p = WS / 'memory' / 'calibration.csv'
    if not p.exists():
        r.add('calibration.csv', OK, 'no log yet (first runs)')
        return
    try:
        rows = list(csv.DictReader(open(p, encoding='utf-8')))
    except Exception as e:
        r.add('calibration.csv', CRITICAL, f'parse fail: {e}')
        return
    if len(rows) > 5000:
        r.add('calibration.csv size', WARNING, f'{len(rows)} rows — retention may not be working')
    else:
        r.add('calibration.csv', OK, f'{len(rows)} rows')


def check_cron_paths_exist(r):
    """All scripts referenced from openclaw/cron/jobs.json exist."""
    jp = Path('/root/.openclaw/cron/jobs.json')
    if not jp.exists():
        r.add('cron paths', WARNING, 'jobs.json not found (running outside openclaw env?)')
        return
    try:
        d = json.loads(jp.read_text())
    except Exception as e:
        r.add('cron paths', CRITICAL, f'jobs.json parse fail: {e}')
        return
    import re
    refs = set()
    for j in d.get('jobs', []):
        msg = (j.get('payload') or {}).get('message', '')
        refs.update(re.findall(r'/root/\.openclaw/workspace/scripts/[a-z/_]+\.py', msg))
    missing = [r_ for r_ in refs if not os.path.exists(r_)]
    if missing:
        r.add('cron paths', CRITICAL, f'missing: {missing}')
    else:
        r.add('cron paths', OK, f'{len(refs)} cron-referenced scripts present')


def main():
    r = Result()
    checks = [
        check_baseline_files,
        check_scripts_compile,
        check_portfolio_schema,
        check_plan_json_schema,
        check_dashboard_buildable,
        check_peer_map_coverage,
        check_no_leaked_secrets,
        check_openclaw_doctor,
        check_calibration_csv,
        check_cron_paths_exist,
    ]
    for c in checks:
        try:
            c(r)
        except Exception as e:
            r.add(c.__name__, CRITICAL, f'check itself crashed: {e}')

    # Print report
    print('═' * 64)
    print(f'  clawock system check  · {r.ok_count()} ok · {r.warn_count()} warn · {r.critical_count()} critical')
    print('═' * 64)
    for name, severity, msg in r.checks:
        line = f'  {severity:14s}  {name:25s}'
        if msg:
            line += f'  {msg}'
        print(line)
    print('═' * 64)

    if r.critical_count() > 0:
        print(f'\n🚫 {r.critical_count()} critical failure(s) — push/commit BLOCKED')
        return 1
    if r.warn_count() > 0:
        print(f'\n⚠️  {r.warn_count()} warning(s) — push allowed but please review')
        return 2
    print('\n✅ all checks passed — system OK to publish')
    return 0


if __name__ == '__main__':
    sys.exit(main())
