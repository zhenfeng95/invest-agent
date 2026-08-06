#!/usr/bin/env bash
# 把当前工作分支合并进 origin/main 并删除临时分支（供 Cloud Agent 定时任务用）。
#
# 用法（在仓库根目录、已 commit 之后）:
#   bash scheduler/merge_to_main.sh
#
# 行为:
#   1) push 当前分支
#   2) 若当前已是 main：结束
#   3) 否则 fetch → 基于 origin/main 合并当前分支 → push main
#   4) 删除远端与本地临时分支，并 checkout main
#
# 需要: Cloud Agent 对 main 有 push 权限；Automations 保持「不要 Create PR」

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${ROOT}" ]]; then
  echo "[merge_to_main] 不在 git 仓库内" >&2
  exit 1
fi
cd "$ROOT"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "[merge_to_main] 工作区有未提交改动，请先 commit" >&2
  exit 1
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "${BRANCH}" == "HEAD" ]]; then
  echo "[merge_to_main] 处于 detached HEAD，无法自动合并" >&2
  exit 1
fi

echo "[merge_to_main] 当前分支: ${BRANCH}"
git push -u origin "HEAD"

if [[ "${BRANCH}" == "main" || "${BRANCH}" == "master" ]]; then
  echo "[merge_to_main] 已在 ${BRANCH}，无需再合并"
  exit 0
fi

git fetch origin main
git checkout -B main origin/main
git merge --no-edit "${BRANCH}"
git push origin main

git push origin --delete "${BRANCH}" || echo "[merge_to_main] 远端删除 ${BRANCH} 失败（可稍后手动删）" >&2
git branch -D "${BRANCH}" 2>/dev/null || true

echo "[merge_to_main] 已合并进 main 并清理分支 ${BRANCH}"
git status -sb
