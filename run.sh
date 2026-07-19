#!/usr/bin/env bash
# Merge-Explain 快捷运行脚本
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-}" in
  ui)
    exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/ui_server.py"
    ;;
  *)
    exec "$SCRIPT_DIR/.venv/bin/merge-explain" "$@"
    ;;
esac
