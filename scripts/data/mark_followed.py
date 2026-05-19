#!/usr/bin/env python3
"""
mark_followed.py — Tier 1.1 reality-check: did kcn actually follow a plan action?

Usage:
  # Mark single action followed=true (按 plan 真的执行了)
  python3 scripts/data/mark_followed.py 2026-05-19 SOXL cut

  # Mark followed=false (你看到 plan 但选择不执行)
  python3 scripts/data/mark_followed.py 2026-05-19 SOXL cut --no

  # Interactive: show today's plan, prompt for each action
  python3 scripts/data/mark_followed.py --interactive

  # Show stats
  python3 scripts/data/mark_followed.py --stats

Why this exists:
- brief_postflight writes plan actions to calibration.csv with followed='unknown'
- Calibration Brier score only counts followed='true' rows (otherwise garbage in)
- If you ignore a plan (followed='false'), it shouldn't penalize the model
- If you forget to mark, it stays 'unknown' and is silently excluded
"""
import argparse
import csv
import io
import os
import sys
from datetime import datetime

WS = '/root/.openclaw/workspace'
CSV = os.path.join(WS, 'memory', 'calibration.csv')
FIELDS = ['plan_date','ticker','bucket','trigger_type','trigger_price',
          'confidence','sim_entry_price','outcome','pnl_5d','pnl_30d',
          'followed','followed_at','updated_at']


def load_rows():
    if not os.path.exists(CSV):
        print(f'  no calibration.csv yet', file=sys.stderr)
        sys.exit(1)
    return list(csv.DictReader(open(CSV, encoding='utf-8')))


def save_rows(rows):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from safe_io import safe_write_text
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
    safe_write_text(CSV, buf.getvalue())


def mark(date, ticker, bucket, followed):
    rows = load_rows()
    matches = [r for r in rows
               if r.get('plan_date') == date
               and r.get('ticker') == ticker
               and r.get('bucket') == bucket]
    if not matches:
        print(f'  ✗ no row matching {date} / {ticker} / {bucket}')
        print(f'  hint: check `python3 mark_followed.py --stats` for available rows')
        sys.exit(1)
    for r in matches:
        r['followed'] = 'true' if followed else 'false'
        r['followed_at'] = datetime.now().isoformat()
    save_rows(rows)
    print(f'  ✓ marked {len(matches)} row(s): {date} {ticker} {bucket} → followed={followed}')


def stats():
    rows = load_rows()
    from collections import Counter
    counts = Counter(r.get('followed', 'unknown') for r in rows)
    out = {k: counts.get(k, 0) for k in ('true', 'false', 'unknown')}
    total = sum(out.values())
    print(f'  total rows: {total}')
    for k in ('true', 'false', 'unknown'):
        print(f'    {k:8s}: {out[k]:>3} ({100*out[k]/total if total else 0:.0f}%)')
    if out['unknown'] > 0:
        print(f'  ⚠ {out["unknown"]} rows still unknown — mark them:')
        for r in rows:
            if r.get('followed') == 'unknown':
                print(f'    python3 scripts/data/mark_followed.py {r["plan_date"]} {r["ticker"]} {r["bucket"]}  [--no]')


def interactive():
    """Walk all unknown rows, prompt for each."""
    rows = load_rows()
    unknown = [r for r in rows if r.get('followed') == 'unknown']
    if not unknown:
        print('  ✓ all plan actions already marked, nothing to do')
        return
    print(f'  {len(unknown)} unknown actions to confirm:\n')
    changed = 0
    for r in unknown:
        print(f"  {r['plan_date']} · {r['ticker']:6s} · {r['bucket']:18s} · conf {r['confidence']} · trigger {r.get('trigger_type')} @ {r.get('trigger_price','-')}")
        try:
            ans = input('    followed? [y]es / [n]o / [s]kip: ').strip().lower()
        except (KeyboardInterrupt, EOFError):
            print('\n  aborted')
            break
        if ans == 'y':
            r['followed'] = 'true'
            r['followed_at'] = datetime.now().isoformat()
            changed += 1
        elif ans == 'n':
            r['followed'] = 'false'
            r['followed_at'] = datetime.now().isoformat()
            changed += 1
        # 's' or anything else = skip
    if changed:
        save_rows(rows)
        print(f'\n  ✓ updated {changed} rows')
    else:
        print('  no changes')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('date', nargs='?', help='YYYY-MM-DD plan_date')
    ap.add_argument('ticker', nargs='?', help='ticker symbol')
    ap.add_argument('bucket', nargs='?', help='bucket value (cut/trim_on_rebound/...)')
    ap.add_argument('--no', action='store_true', help='Mark followed=false (you ignored this plan)')
    ap.add_argument('--stats', action='store_true', help='Show followed-stats summary')
    ap.add_argument('--interactive', '-i', action='store_true', help='Walk unknown rows prompting for each')
    args = ap.parse_args()

    if args.stats:
        stats()
    elif args.interactive:
        interactive()
    elif args.date and args.ticker and args.bucket:
        mark(args.date, args.ticker, args.bucket, followed=not args.no)
    else:
        ap.print_help()
        sys.exit(0)


if __name__ == '__main__':
    main()
