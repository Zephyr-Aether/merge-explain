 #!/usr/bin/env bash
 # Merge-Explain 快捷运行脚本
 # 用法: ./run.sh analyze branch-a branch-b
 #       ./run.sh sample
 #       ./run.sh version
 
 SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
 exec "$SCRIPT_DIR/.venv/bin/merge-explain" "$@"
