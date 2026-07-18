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
