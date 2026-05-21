#!/usr/bin/env bash
# check_crons.sh — show recent openclaw cron run history across ALL jobs
# Usage:
#   ./check_crons.sh                 # last 20 runs (auto + manual)
#   ./check_crons.sh 50              # last 50
#   ./check_crons.sh --job 港股       # filter by job name
#   ./check_crons.sh --status error  # only failures
#   ./check_crons.sh --kind cron     # only auto-scheduled
#   ./check_crons.sh --full          # no summary truncation
exec python3 "$(dirname "$0")/scripts/data/cron_runs.py" "$@"
