# Merge-Explain

**可解释性 AI 合并工具 — 先理解，再合并**

## 解决的问题

用 AI 写代码（Cursor / Claude Code / Copilot 等）越来越普遍，但会带来一个新痛点：

> 多个分支各自有大量 AI 生成的改动，开发者看不懂 Diff，遇到合并冲突时不敢处理。

传统做法要么让 AI 黑盒自动合并（风险高），要么在冲突标记里人肉逐行对比（效率低）。

Merge-Explain 不做自动合，而是帮你**先理解双方分别做了什么**——LLM 分析两个分支的代码变更语义，输出一份带风险等级和处理建议的结构化报告，让开发者看懂后再决定怎么合。

## 安装

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key（默认兼容 DeepSeek / 通义千问等）

# 2. 安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 用法

```bash
# 分析两个分支的差异（核心功能）
./run.sh analyze <branch-a> <branch-b>

# 用内置的示例数据测试工具流程
./run.sh sample

# 查看帮助
./run.sh --help
```

### 输出示例

终端输出包含四部分：

1. **Branch A / Branch B 变更摘要** — 列出每个分支改了哪些文件、函数、做了什么
2. **冲突详情** — 逐点列出每处冲突的风险等级（🟢 自动合并 / 🟡 建议人工 / 🔴 必须人工）和处理建议
3. **总体决策** — 全局建议（auto_merge / manual_review / blocked）和一句话理由

### 选项

| 参数 | 说明 |
| --- | --- |
| `--output`, `-o` | 导出报告到文件（如 `-o report.html`） |
| `--format`, `-f` | 输出格式：`terminal`（默认）、`html`、`markdown` |
| `--auto-apply`, `-a` | **安全模式** — 仅模拟合并日志，不实际执行 Git merge |

## 工作流程

```
merge-explain analyze feature-a feature-b
        │
        ├─ 1. 找到两个分支的共同祖先 commit
        ├─ 2. 获取三方 diff（共同祖先 → branch-a + branch-b）
        ├─ 3. 若 diff 超过 5000 tokens，自动降级为函数级片段
        ├─ 4. 调用 LLM 分析变更语义
        └─ 5. 输出结构化报告（终端 / HTML / Markdown）
```

## 技术栈

- Python 3.9+（推荐 3.10+）
- GitPython — Git 操作
- OpenAI SDK — LLM 调用（兼容 DeepSeek / 通义千问）
- Typer — CLI 框架
- Rich — 终端美化
- Pydantic v2 — 数据模型与验证

## 安全策略

- MVP 阶段**不执行任何实际 Git merge**，`--auto-apply` 仅输出模拟日志
- 如需真实合并，请在确认报告后手动执行 `git merge`
