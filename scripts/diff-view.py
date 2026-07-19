"""
生成漂亮的 HTML 侧边对比 diff。
用法: python scripts/diff-view.py <branch> <file-path>
示例: python scripts/diff-view.py feature/timeout-increase src/git_ops.py
"""
import sys, os
from pathlib import Path

# ── 参数 ──
if len(sys.argv) < 3:
    print("用法: python scripts/diff-view.py <branch> <file-path>")
    print("示例: python scripts/diff-view.py feature/timeout-increase src/git_ops.py")
    sys.exit(1)

BRANCH = sys.argv[1]
FILE = sys.argv[2]

# ── 提取两版本内容 ──
import subprocess

def get_content(ref):
    try:
        return subprocess.check_output(
            ["git", "show", f"{ref}:{FILE}"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8")
    except:
        return None

# 使用 merge-base（共同祖先），而不是 main 的最新版本
merge_base = subprocess.check_output(
    ["git", "merge-base", "main", BRANCH]
).decode().strip()
main_content = get_content(merge_base)
branch_content = get_content(BRANCH)

if main_content is None or branch_content is None:
    print(f"❌ 无法读取文件: {FILE}")
    sys.exit(1)

main_lines = main_content.splitlines()
branch_lines = branch_content.splitlines()

# ── 生成 diff 行对 ──
import difflib
matcher = difflib.SequenceMatcher(None, main_lines, branch_lines)

diff_rows = []
for op, i1, i2, j1, j2 in matcher.get_opcodes():
    if op == 'equal':
        for idx in range(i2 - i1):
            diff_rows.append((' ', main_lines[i1 + idx], branch_lines[j1 + idx]))
    elif op == 'replace':
        for idx in range(max(i2 - i1, j2 - j1)):
            m = main_lines[i1 + idx] if i1 + idx < i2 else ''
            b = branch_lines[j1 + idx] if j1 + idx < j2 else ''
            diff_rows.append(('!', m, b))
    elif op == 'delete':
        for idx in range(i2 - i1):
            diff_rows.append(('-', main_lines[i1 + idx], ''))
    elif op == 'insert':
        for idx in range(j2 - j1):
            diff_rows.append(('+', '', branch_lines[j1 + idx]))

# ── 生成 HTML ──
html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Diff: {FILE}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 13px;
    line-height: 1.6;
    background: #0d1117;
    color: #e6edf3;
    padding: 16px;
  }}
  .header {{
    margin-bottom: 16px;
    padding: 12px 16px;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .header h2 {{
    font-size: 16px;
    font-weight: 600;
    color: #e6edf3;
  }}
  .header .file {{ color: #58a6ff; }}
  .header .branch {{ color: #d2a8ff; }}
  .header .tag {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
  }}
  .tag-main {{ background: #1f6feb22; color: #58a6ff; border: 1px solid #1f6feb44; }}
  .tag-branch {{ background: #8957e522; color: #d2a8ff; border: 1px solid #8957e544; }}
  .diff-table {{
    width: 100%;
    border-collapse: collapse;
    border: 1px solid #30363d;
    border-radius: 6px;
    overflow: hidden;
    table-layout: fixed;
  }}
  .diff-table th {{
    background: #161b22;
    padding: 8px 10px;
    text-align: left;
    font-size: 12px;
    font-weight: 600;
    color: #8b949e;
    border-bottom: 1px solid #30363d;
    width: 50%;
  }}
  .diff-table td {{
    vertical-align: top;
    padding: 0;
  }}
  .diff-table .side {{
    width: 50%;
    border-right: 1px solid #30363d;
  }}
  .diff-table .side:last-child {{ border-right: none; }}
  .line {{ display: flex; min-height: 22px; }}
  .line-num {{
    width: 48px;
    min-width: 48px;
    padding: 0 8px;
    text-align: right;
    color: #484f58;
    font-size: 12px;
    line-height: 22px;
    user-select: none;
    border-right: 1px solid #21262d;
  }}
  .line-code {{
    flex: 1;
    padding: 0 10px;
    white-space: pre;
    overflow-x: auto;
    line-height: 22px;
  }}
  .line-equal {{ background: transparent; }}
  .line-equal .line-num {{ background: #0d1117; }}
  .line-add {{ background: #1b4721; }}
  .line-add .line-num {{ background: #1c4220; color: #3fb950; border-right-color: #1b4721; }}
  .line-del {{ background: #54212e; }}
  .line-del .line-num {{ background: #49202b; color: #f85149; border-right-color: #54212e; }}
  .line-rep {{ background: #54212e; }}
  .line-rep .line-num {{ background: #49202b; color: #f85149; border-right-color: #54212e; }}
  .line-rep + .line-add {{ border-top: none; }}
  .line-rep + .line-add .line-num {{ background: #1c4220; color: #3fb950; }}
  .summary {{
    margin-top: 12px;
    padding: 8px 16px;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    font-size: 12px;
    color: #8b949e;
  }}
  .summary span {{ color: #e6edf3; font-weight: 600; }}
</style>
</head>
<body>

<div class="header">
  <span class="tag tag-main">共同祖先</span>
  <span style="color:#8b949e">→</span>
  <span class="tag tag-branch">{BRANCH}</span>
  <h2 style="margin-left:8px"><span class="file">{FILE}</span></h2>
</div>

<table class="diff-table">
<tr>
  <th>共同祖先 (merge-base)</th>
  <th>{BRANCH}</th>
</tr>
<tr>
  <td class="side"><div class="lines">'''

# Render left side
left_rows = []
right_rows = []
ln_main = 0
ln_branch = 0

for op, m, b in diff_rows:
    if op == ' ':
        ln_main += 1
        ln_branch += 1
        cls = 'line-equal'
    elif op == '!':
        ln_main += 1
        ln_branch += 1
        cls = 'line-rep'
    elif op == '-':
        ln_main += 1
        cls = 'line-del'
    elif op == '+':
        ln_branch += 1
        cls = 'line-add'

    left_rows.append(f'<div class="line {cls}"><span class="line-num">{ln_main if m else ""}</span><span class="line-code">{m}</span></div>')
    right_rows.append(f'<div class="line {cls}"><span class="line-num">{ln_branch if b else ""}</span><span class="line-code">{b}</span></div>')

html += '\n'.join(left_rows)
html += '</div></td>\n  <td class="side"><div class="lines">\n'
html += '\n'.join(right_rows)
html += '''</div></td>\n</tr>\n</table>

<div class="summary">
  共 <span>{}</span> 行 · <span style="color:#f85149">-{} 删除</span> · <span style="color:#3fb950">+{} 新增</span>
</div>

</body>
</html>'''.format(
    len(diff_rows),
    sum(1 for op,_,_ in diff_rows if op in ('-','!')),
    sum(1 for op,_,_ in diff_rows if op in ('+','!'))
)

# ── 输出 ──
safe_file = FILE.replace('/', '-')
out_path = f"/tmp/merge-explain-diff-{BRANCH.replace('/', '-')}-{safe_file}.html"
Path(out_path).write_text(html, encoding="utf-8")

# 在终端显示简短摘要
changed = sum(1 for op,_,_ in diff_rows if op != ' ')
print(f"📄 {FILE}")
print(f"   main  →  {BRANCH}")
print(f"   {len(main_lines)} 行 → {len(branch_lines)} 行 ({'%+d' % (len(branch_lines)-len(main_lines))})")
print(f"   {changed} 处变更")
print(f"")

# 自动打开浏览器
import webbrowser
webbrowser.open(f"file://{out_path}")
print(f"🖥️  已自动打开浏览器")
