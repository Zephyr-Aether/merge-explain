# Merge-Explain

**可解释性 AI 合并工具 — 先理解，再合并**

## 解决的问题

用 AI 写代码（Cursor / Claude Code / Copilot 等）越来越普遍，但会带来一个新痛点：

> 多个分支各自有大量 AI 生成的改动，开发者看不懂 Diff，遇到合并冲突时不敢处理。

传统做法要么让 AI 黑盒自动合并（风险高），要么在冲突标记里人肉逐行对比（效率低）。

Merge-Explain 不做黑盒自动合，而是帮你**先理解双方分别做了什么**——LLM 分析两个分支的代码变更语义，输出一份带风险等级和冲突代码的结构化报告，然后按你的确认逐块自动合并。

## 功能

### analyze — 分析变更语义

```bash
./run.sh analyze <branch-a> <branch-b>
```

输出包含：

1. **Branch A / Branch B 变更摘要** — 每个分支改了哪些文件、函数、做了什么
2. **冲突详情** — 每处冲突的风险等级和处理建议，附带冲突代码片段
3. **总体决策** — 全局建议（auto_merge / manual_review / blocked）和理由

**选项：**

| 参数 | 说明 |
| --- | --- |
| `-o`, `--output` | 导出报告（如 `-o report.html`） |
| `-f`, `--format` | 输出格式：`terminal`（默认）、`html`、`markdown` |
| `-v`, `--verbose` | 同时显示原始 Diff 文本 |
| `--no-cache` | 跳过缓存，强制重新调 LLM |
| `-a`, `--auto-apply` | *安全模式* — 仅输出模拟日志，不实际执行合并 |

### resolve — 自动解决冲突

```bash
# 预览（默认，不写文件）
./run.sh resolve <branch-a> <branch-b>

# 实际写入文件
./run.sh resolve <branch-a> <branch-b> --apply

# 复用 analyze 的分析结果
./run.sh resolve <branch-a> <branch-b> --from-report report.json
```

流程会自动：

1. 执行 `git merge` 触发冲突
2. 解析 `<<<<<<<` / `=======` / `>>>>>>>` 冲突标记
3. 提取三方代码（BASE / 双方分支 + 上下文）
4. 逐块调用 LLM 生成合并代码
5. 替换冲突、语法检查

**选项：**

| 参数 | 说明 |
| --- | --- |
| `--apply` | 实际写入文件（默认只预览） |
| `--from-report` | 复用 analyze 输出的报告（冲突建议会注入到 LLM prompt 中） |
| `--risk-threshold` | 风险阈值：`green` / `yellow`（RED 永远跳过） |

### 其他命令

```bash
# 使用内置 sample 数据测试工具流程（无需 API Key）
./run.sh sample

# 显示版本信息
./run.sh version
```

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key（兼容 DeepSeek / 通义千问 / OpenAI）

# 2. 安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. 看看效果（不需要 API Key）
./run.sh sample

# 4. 分析两个分支的差异
./run.sh analyze feature-a feature-b

# 5. 自动解决冲突
./run.sh resolve feature-a feature-b --apply
```

## 完整工作流

```
                    analyze                              resolve
┌──────────────────────────────┐       ┌──────────────────────────────┐
│  1. 找到共同祖先 commit       │       │  1. git merge 触发冲突       │
│  2. 获取三方 diff             │       │  2. 解析 <<<<<<< 冲突标记    │
│  3. LLM 分析变更语义          │       │  3. 提取 BASE/双方版本+上下文 │
│  4. 输出风险等级 + 处理建议    │ ──→   │  4. 逐块调 LLM 生成合并代码  │
│  5. 终端 / HTML / Markdown    │       │  5. 替换冲突 → 语法检查     │
│  6. 结果缓存（省 token）       │       │  6. --apply 写入文件         │
└──────────────────────────────┘       └──────────────────────────────┘
```

## 技术栈

- Python 3.9+
- GitPython — Git 操作
- OpenAI SDK — LLM 调用（兼容 DeepSeek / 通义千问）
- Typer — CLI 框架（带进度条）
- Rich — 终端彩色输出
- Pydantic v2 — 数据模型与验证

## 安全策略

- **analyze** 阶段不碰任何文件，只输出报告
- **resolve** 默认只预览，`--apply` 才写入文件
- 写入前自动备份，语法检查不通过自动回滚
- RED 风险等级的冲突跳过自动解决，强制人工处理
- 整个过程中 `git merge --abort` 兜底恢复

## 项目结构

```
src/
├── main.py         # Typer CLI 入口（analyze / resolve / sample / version）
├── analyzer.py     # LLM Prompt 构造 + API 调用 + 重试 + 降级
├── git_ops.py      # Git diff 获取 + Token 超限降级 + 冲突片段提取
├── merger.py       # 冲突标记解析 + LLM 单块解决 + 安全替换
├── reporter.py     # Rich 终端输出 + HTML / Markdown 导出
└── models.py       # Pydantic 数据模型
```

## MCP Server

merge-explain 提供了标准 MCP Server，可接入任何支持 MCP 协议的 AI 客户端。

### 可用 Tool

| Tool | 说明 |
|------|------|
| `analyze_conflicts` | 分析两个分支的代码变更，返回结构化冲突报告 |
| `resolve_conflicts` | 自动解决合并冲突（dry-run / apply） |
| `list_branches` | 列出仓库中的所有分支 |
| `sample_analysis` | 内置示例分析（无需 API Key） |

### 接入方式

**Smithery 市场**（推荐）：
```bash
# 即将上线
```

**本地运行**：
```bash
python mcp_server.py
```

**Codex / Claude Desktop**：
```json
{
  "mcpServers": {
    "merge-explain": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "OPENAI_API_KEY": "sk-xxx"
      }
    }
  }
}
```

### 从源码安装为 Skill

```bash
skill-installer install https://github.com/Zephyr-Aether/merge-explain
```
