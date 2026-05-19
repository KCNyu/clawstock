#!/usr/bin/env bash
# safe_push.sh — push with rebase retry but abort on real conflict (don't loop forever)
# 各 GH Action workflow 引用此脚本统一行为
set -e

MAX_RETRIES=3
REMOTE="${1:-origin}"
BRANCH="${2:-master}"

for i in $(seq 1 $MAX_RETRIES); do
  if git push "$REMOTE" "$BRANCH"; then
    echo "✓ pushed on attempt $i"
    exit 0
  fi
  echo "push failed attempt $i, trying rebase..."
  
  if git pull --rebase "$REMOTE" "$BRANCH"; then
    echo "  rebase clean, will retry push"
    sleep $((i * 3))
  else
    # rebase failed (probably conflict on same file) — abort + don't retry
    echo "  ✗ rebase conflict — abort, leaving commit local"
    git rebase --abort 2>/dev/null || true
    echo "  Manual resolution needed: git pull --rebase + resolve + git push"
    exit 2
  fi
done

echo "✗ push failed after $MAX_RETRIES retries"
exit 1
