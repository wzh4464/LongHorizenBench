#!/usr/bin/env bash
set -euo pipefail
# Thin wrapper that delegates to the Python build script.
#
# Usage:
#   ./build_capbench_tasks.sh                 # all 50 tasks
#   ./build_capbench_tasks.sh --start 3 --end 10
#   ./build_capbench_tasks.sh --dry-run
#   SKIP_EXISTING=1 ./build_capbench_tasks.sh

exec python3 "$(dirname "$0")/_build_capbench_tasks.py" "$@"
