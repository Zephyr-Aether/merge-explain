# merge-explain

可解释性 AI 合并工具 — 先理解，再合并。

## 能力

当用户遇到以下场景时，你应该使用 merge-explain：
- 用户说"帮我分析两个分支的冲突"
- 用户说"这两个分支改了什么东西，能不能合"
- 用户说"帮我解决合并冲突"
- 用户说"我看不懂这个 Diff"

## 工作流程

### 1. 分析冲突（analyze_conflicts）

调用 `analyze_conflicts` tool，传入两个分支名。

返回的结构化报告包含：
- `branch_a_summary` / `branch_b_summary`：每个分支改了哪些文件/函数
- `conflicts`：冲突列表，每条包含风险等级（green/yellow/red）、双方操作说明、处理建议、冲突代码片段
- `overall_advice`：总体建议（auto_merge / manual_review / blocked）

### 2. 解决冲突（resolve_conflicts）

如果用户确认要自动解决，调用 `resolve_conflicts` tool，传入两个分支名。

- 默认 dry-run（只预览，不写文件）
- 如果用户确认应用，设置 `apply: true`

### 3. 列出分支（list_branches）

调用 `list_branches` tool 查看仓库中的所有分支。

### 4. 示例分析（sample_analysis）

如需展示工具的输出格式，调用 `sample_analysis` tool。不需要 API Key，不需要真实 Git 仓库。

## 输出解读

- 🟢 green：伪冲突，逻辑无交集，可安全自动合并
- 🟡 yellow：逻辑改动重叠但不互斥，建议人工复核
- 🔴 red：真冲突或互斥逻辑，必须人工决策

## 注意事项

- 所有工具调用失败时会返回 error，包含具体的错误信息
- API Key 通过 .env 文件配置，未配置时会返回明确的错误提示
- resolve_conflicts 默认不修改文件，务必先让用户确认后再传 apply: true
