#!/usr/bin/env bash
# 方案 2：本机 / cron 刷新财经日历（不经 LLM）。
#
# 用法（仓库根目录）:
#   bash scheduler/run-economic-calendar.sh
#   bash scheduler/run-economic-calendar.sh --no-push   # 只写文件不推远端
#
# 依赖: JIN10_BEARER_TOKEN（环境或仓库 .env）
# 推荐 cron（北京时间）:
#   0 8 * * 1-5   …/scheduler/run-economic-calendar.sh
#   30 22 * * 1-5 …/scheduler/run-economic-calendar.sh
#   0 8 * * 1     …/scheduler/run-economic-calendar.sh   # 周一必更（与上重叠可省略）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# 加载 .env（不覆盖已有环境变量）
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [[ -z "${JIN10_BEARER_TOKEN:-}" ]]; then
  echo "[run-economic-calendar] 缺少 JIN10_BEARER_TOKEN" >&2
  exit 1
fi

PUSH=1
for arg in "$@"; do
  case "$arg" in
    --no-push) PUSH=0 ;;
  esac
done

if [[ "$PUSH" -eq 1 ]]; then
  python3 "$ROOT/tools/jin10_economic_calendar.py" --commit --push
else
  python3 "$ROOT/tools/jin10_economic_calendar.py"
fi
