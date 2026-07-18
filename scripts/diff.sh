#!/bin/bash
# 在 VS Code 中查看某个分支相对于 main 的文件 diff
# 用法: ./scripts/diff.sh <branch> <file-path>
# 示例: ./scripts/diff.sh feature/timeout-increase src/git_ops.py
# 不需要安装 code 命令，用 macOS 自带的 open

set -e
BRANCH="$1"
FILE="$2"

if [ -z "$BRANCH" ] || [ -z "$FILE" ]; then
  echo "用法: $0 <branch> <file-path>"
  echo "示例: $0 feature/my-branch src/main.py"
  exit 1
fi

# 将文件名中的 / 替换为 -，用作临时文件名
SAFE_FILE=$(echo "$FILE" | tr '/' '-')
SAFE_BRANCH=$(echo "$BRANCH" | tr '/' '-')

TMP_MAIN="/tmp/merge-explain-main-${SAFE_FILE}"
TMP_BRANCH="/tmp/merge-explain-${SAFE_BRANCH}-${SAFE_FILE}"

# 提取两个版本的内容到临时文件
git show "main:${FILE}" > "$TMP_MAIN" 2>/dev/null || { echo "❌ main 上不存在 $FILE"; exit 1; }
git show "${BRANCH}:${FILE}" > "$TMP_BRANCH" 2>/dev/null || { echo "❌ ${BRANCH} 上不存在 $FILE"; exit 1; }

# 尝试用 macOS open 打开 VS Code diff 视图（不需要 code 命令）
echo "🔄 正在打开 VS Code diff 视图..."
if open -a "Visual Studio Code" --args --diff "$TMP_MAIN" "$TMP_BRANCH" 2>/dev/null; then
  echo "✅ 已打开 VS Code diff 视图"
  echo "   临时文件（可删除）:"
  echo "     main: $TMP_MAIN"
  echo "     ${BRANCH}: $TMP_BRANCH"
else
  echo "⚠️ 未找到 VS Code，改用终端 git diff："
  echo ""
  git diff main..."$BRANCH" -- "$FILE"
fi
