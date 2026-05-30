#!/usr/bin/env bash
# commit_dreaming.sh — 兜底提交 openclaw "Memory Dreaming Promotion" 的产物。
#
# 背景 (2026-05-30): dreaming 是 openclaw core 内置 cron (03:00 HKT, delivery=none),
# 把短期记忆促进追加进顶层 MEMORY.md / DREAMS.md,但 **core 不自动 commit**;而 harness
# 各 postflight 的 `git add memory/` 又不含仓库根的 MEMORY.md/DREAMS.md → 促进内容长期脏在
# 工作区,直到某次手动 `git add -A` 才被捎带,且会害得别的 push 撞脏工作区 rebase。
# 本脚本由 system crontab 在 dreaming 之后 (03:20) 跑,只提交这两个文件。
#
# 鲁棒性: 只 stage MEMORY.md/DREAMS.md (不碰宿主其它在写的脏文件);push 被拒时用
# rebase.autoStash 自动绕开"工作区脏 → pull --rebase 拒跑"的坑;真冲突则留本地不死循环。
set -uo pipefail

WS=/root/.openclaw/workspace
cd "$WS" || exit 1

git config user.name  "github-actions[bot]" 2>/dev/null || true
git config user.email "41898282+github-actions[bot]@users.noreply.github.com" 2>/dev/null || true

git add MEMORY.md DREAMS.md
if git diff --cached --quiet; then
  echo "$(date -Is) dreaming-commit: MEMORY/DREAMS 无变化,跳过"
  exit 0
fi

git commit -q -m "memory: dreaming 促进自动提交 $(TZ=Asia/Hong_Kong date +%Y-%m-%d)" || { echo "$(date -Is) commit 失败"; exit 1; }
echo "$(date -Is) dreaming-commit: 已提交 $(git rev-parse --short HEAD)"

for i in 1 2 3; do
  if git push origin master 2>/dev/null; then
    echo "$(date -Is) dreaming-commit: pushed (attempt $i)"
    exit 0
  fi
  echo "$(date -Is) push 第 $i 次被拒,autostash rebase 重试…"
  # rebase.autoStash 自动 stash 宿主未暂存改动、rebase、再恢复 — 绕开脏工作区拒跑
  if ! git -c rebase.autoStash=true pull --rebase origin master 2>&1 | tail -2; then
    echo "$(date -Is) dreaming-commit: rebase 冲突,留本地提交不推送 (下次或手动处理)"
    git rebase --abort 2>/dev/null || true
    exit 2
  fi
  sleep $((i * 3))
done
echo "$(date -Is) dreaming-commit: 3 次仍失败,留本地"
exit 1
