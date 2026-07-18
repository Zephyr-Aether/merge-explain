# Merge-Explain

**可解释性 AI 合并工具 — 先理解，再合并**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)

## 解决的问题

AI 生成代码（Cursor / Claude Code / Copilot）越来越普及，但带来新痛点：

> 多个分支各自有大量 AI 改动，开发者看不懂 Diff，合并冲突时不敢处理。

Merge-Explain 不做黑盒自动合，而是**先理解双方分别做了什么**——LLM 分析变更语义，输出风险等级和处理建议，按你的确认逐块自动合并。

---

## 快速开始

```bash
# 1. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 Key（兼容 OpenAI / DeepSeek / 通义千问）

# 2. 安装
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. 快速体验（无需 Key）
./run.sh sample

# 4. 分析分支差异
./run.sh analyze feature-a feature-b

# 5. 自动解决冲突
./run.sh resolve feature-a feature-b --apply
```

---

## CLI 命令

### analyze — 分析变更语义

```bash
./run.sh analyze <branch-a> <branch-b>
```

输出结构化报告：

| 板块 | 内容 |
|------|------|
| **变更摘要** | 每个分支改了哪些文件、函数、做了什么 |
| **冲突详情** | 风险等级（🟢 🟡 🔴）+ 处理建议 + 冲突代码片段 |
| **总体决策** | `auto_merge` / `manual_review` / `blocked` + 理由 |

| 选项 | 说明 |
|------|------|
| `-o`, `--output` | 导出报告（`-o report.html`） |
| `-f`, `--format` | `terminal`（默认）/ `html` / `markdown` |
| `-v`, `--verbose` | 同时显示原始 Diff |
| `--no-cache` | 跳过缓存，强制重新分析 |

### resolve — 自动解决冲突

```bash
./run.sh resolve <branch-a> <branch-b>          # 预览（默认）
./run.sh resolve <branch-a> <branch-b> --apply  # 写入文件
```

流程：`git merge` 触发冲突 → 解析 `<<<<<<<` 标记 → 提取三方代码 → LLM 逐块合并 → 替换 + 语法检查。

| 选项 | 说明 |
|------|------|
| `--apply` | 实际写入文件（默认只预览） |
| `--from-report` | 复用 analyze 的分析结果 |
| `--risk-threshold` | `green` / `yellow`（RED 永远跳过） |

---

## 安全策略

| 阶段 | 措施 |
|------|------|
| **analyze** | 只读，不碰任何文件 |
| **resolve 预览** | 不写文件，展示 diff |
| **resolve 应用** | 自动备份 → 写入 → 语法检查 → 失败回滚 |
| **RED 冲突** | 跳过自动解决，强制人工处理 |
| **异常兜底** | `git merge --abort` 保证 |

---

## 项目结构

```
merge-explain/
├── SKILL.md                    # skills.sh 标准技能指令
├── agents/
│   └── openai.yaml             # 代理接入配置
├── assets/                     # 技能图标
├── LICENSE.txt                 # MIT 许可证
├── .codex-plugin/
│   └── plugin.json             # Codex 插件注册
│
├── mcp_server.py               # MCP Server（标准协议）
├── mcp_entry.py                 # MCP 入口（自动加载 .env）
├── .mcp.json                   # Claude Code 自动发现配置
├── CLAUDE.md                   # 多平台 MCP 配置模板
│
├── src/
│   ├── main.py                 # CLI 入口（analyze / resolve / sample / version）
│   ├── analyzer.py             # LLM Prompt + API 调用 + 重试降级
│   ├── git_ops.py              # Git diff + Token 截断 + 冲突片段提取
│   ├── merger.py               # 冲突标记解析 + LLM 单块解决 + 安全替换
│   ├── reporter.py             # Rich 终端输出 + HTML / Markdown 导出
│   └── models.py               # Pydantic 数据模型
│
├── tests/                      # 39 个测试
├── scripts/                    # 辅助脚本
├── docs/                       # 设计文档
└── smithery.yaml               # Smithery MCP 市场配置
```

---

## MCP Server

merge-explain 提供标准 MCP Server，可接入任何支持 MCP 协议的 AI 客户端。

### 可用 Tool

| Tool | 说明 |
|------|------|
| `analyze_conflicts` | 分析两个分支变更，返回结构化报告 |
| `resolve_conflicts` | 自动解决合并冲突 |
| `list_branches` | 列出仓库分支 |
| `sample_analysis` | 内置示例（无需 API Key） |

### 多平台支持

| 客户端 | 配置方式 | 文档 |
|--------|---------|------|
| **Claude Code** | `.mcp.json` 自动发现 | [CLAUDE.md](./CLAUDE.md) |
| **Claude Desktop** | `claude_desktop_config.json` | [CLAUDE.md](./CLAUDE.md) |
| **Cursor** | `.cursor/mcp.json` | [CLAUDE.md](./CLAUDE.md) |
| **Continue.dev** | `~/.continue/config.json` | [CLAUDE.md](./CLAUDE.md) |
| **Codex** | `.codex-plugin/plugin.json` 自动发现 | — |

### 本地测试

```bash
python mcp_server.py
```

MCP 客户端通过 stdin/stdout 用 JSON-RPC 2.0 通信：

```
AI 客户端 ──stdin/stdout──> mcp_server.py ──> OpenAI SDK
                              │
                              └──> GitPython
```

---

## 技术栈

- Python 3.9+
- GitPython · OpenAI SDK · Typer · Rich · Pydantic v2
- MCP 标准协议（JSON-RPC 2.0 over stdio）

---

## Skill 市场

本项目遵循 [skills.sh](https://skills.sh) 标准技能格式，可直接提交至市场：

```
skills/.curated/merge-explain/
├── SKILL.md
├── agents/openai.yaml
├── assets/
├── LICENSE.txt
```

也可从 GitHub 直接安装：

```bash
skill-installer install https://github.com/Zephyr-Aether/merge-explain
```
