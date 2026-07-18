# Merge-Explain MCP 配置

本目录包含一个 MCP Server，支持以下 AI 客户端。

## Claude Desktop

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "merge-explain": {
      "command": "python",
      "args": ["/absolute/path/to/mcp_server.py"],
      "env": {
        "OPENAI_API_KEY": "sk-xxx",
        "OPENAI_BASE_URL": "",
        "OPENAI_MODEL": "gpt-4o-mini"
      }
    }
  }
}
```

## Claude Code

在项目根目录的 `.mcp.json` 中添加：

```json
{
  "mcpServers": {
    "merge-explain": {
      "command": "python",
      "args": ["mcp_server.py"],
      "env": {
        "OPENAI_API_KEY": "sk-xxx"
      }
    }
  }
}
```

## Cursor

在 `.cursor/mcp.json` 中添加：

```json
{
  "mcpServers": {
    "merge-explain": {
      "type": "python",
      "command": "python",
      "args": ["mcp_server.py"]
    }
  }
}
```

## Continue.dev

在 `~/.continue/config.json` 中添加：

```json
{
  "experimental": {
    "mcpServers": {
      "merge-explain": {
        "command": "python",
        "args": ["mcp_server.py"]
      }
    }
  }
}
```

## Windsurf / Cascade

支持标准 MCP stdio 协议，配置方式同上。

## 一键配置

本仓库已内置 `.mcp.json`，如果你在使用 **Claude Code**，只需：

```bash
# 1. 进入项目目录
cd /path/to/merge-explain

# 2. 配置 .env（API Key）
cp .env.example .env
# 编辑 .env，填入你的 OPENAI_API_KEY

# 3. Claude Code 会自动读取 .mcp.json，MCP Server 即刻可用
claude
```

对 **Claude Desktop**，在 `claude_desktop_config.json` 中指向本仓库的 `mcp_server.py` 即可：

```json
{
  "mcpServers": {
    "merge-explain": {
      "command": "python",
      "args": ["/absolute/path/to/merge-explain/mcp_server.py"],
      "env": {}
    }
  }
}
```

**不需要发布到任何平台。**仓库本身就是 skill + MCP 的完整载体。
