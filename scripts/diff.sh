#!/bin/bash
# 在 VS Code 中查看某个分支相对于 main 的文件 diff
# 用法: ./scripts/diff.sh <branch> [file-path]
# 示例: ./scripts/diff.sh feature/timeout-increase src/git_ops.py

set -e
BRANCH="$1"
FILE="${2:-.}"

if [ -z "$BRANCH" ]; then
  echo "用法: $0 <branch> [file-path]"
  echo "示例: $0 feature/my-branch src/main.py"
  exit 1
fi

code --diff <(git show "main:${FILE}") <(git show "${BRANCH}:${FILE}")
