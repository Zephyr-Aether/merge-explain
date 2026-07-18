"""MCP 入口：加载 .env → 启动 merge-explain MCP Server"""
import os, sys
from pathlib import Path

# 确保能导入 src 模块
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from mcp_server import _serve
_serve()
