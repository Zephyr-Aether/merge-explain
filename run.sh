#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

case "${1:-ui}" in
  ui|api)
    cd "$SCRIPT_DIR"
    exec "$VENV/bin/python" -c "
import uvicorn
from server import app
uvicorn.run(app, host='127.0.0.1', port=13920)
"
    ;;
  install)
    echo "=== Backend ==="
    cd "$SCRIPT_DIR"
    "$VENV/bin/pip" install -e .
    "$VENV/bin/pip" install fastapi uvicorn python-multipart
    echo "=== Frontend ==="
    cd "$SCRIPT_DIR/frontend"
    npm install
    echo "Done! Run: ./run.sh ui"
    ;;
  build)
    cd "$SCRIPT_DIR/frontend" && npm run build
    echo "Frontend built. Run: ./run.sh ui"
    ;;
  dev)
    cd "$SCRIPT_DIR/frontend" && npm run dev &
    "$SCRIPT_DIR/.venv/bin/python" -c "
import uvicorn
from server import app
uvicorn.run(app, host='127.0.0.1', port=13920)
"
    ;;
  *)
    exec "$SCRIPT_DIR/.venv/bin/merge-explain" "$@"
    ;;
esac
