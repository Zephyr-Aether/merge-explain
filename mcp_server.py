"""
MCP Server — 将 merge-explain 能力暴露为结构化 Tool，供 AI 直接调用。

协议：MCP stdio（JSON-RPC 2.0 over stdin/stdout）
工具列表：
  - analyze_conflicts  → 分析两个分支变更，返回结构化报告
  - resolve_conflicts  → 自动解决合并冲突
  - list_branches      → 列出仓库分支
  - sample_analysis    → 内置示例分析（无需 API Key）
"""
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

# ── 确保能导入 src 模块 ──
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from src.analyzer import analyze_diff, test_with_sample_diff
from src.git_ops import get_repo, get_diff_text, get_merge_base
from src.models import MergeReport


# ═══════════════════════════════════════════════════════════════════════════
# MCP 协议通信
# ═══════════════════════════════════════════════════════════════════════════

def _send(obj: dict) -> None:
    """向 stdout 写入 JSON-RPC 响应（单行）。"""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _error(id_val: Any, code: int, message: str, data: Any = None) -> dict:
    return {"jsonrpc": "2.0", "id": id_val, "error": {"code": code, "message": message, "data": data}}


def _result(id_val: Any, result_data: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_val, "result": result_data}


# ═══════════════════════════════════════════════════════════════════════════
# Tool 定义
# ═══════════════════════════════════════════════════════════════════════════

TOOLS: list[dict] = [
    {
        "name": "analyze_conflicts",
        "description": "分析两个特性分支分别合入目标分支时会产生哪些冲突。默认对比 main，也可指定其他目标分支",
        "inputSchema": {
            "type": "object",
            "properties": {
                "branch_a": {
                    "type": "string",
                    "description": "特性分支 A",
                },
                "branch_b": {
                    "type": "string",
                    "description": "特性分支 B",
                },
                "target": {
                    "type": "string",
                    "description": "目标分支（两个分支最终要合入的分支），默认 main",
                    "default": "main",
                },
                "repo_path": {
                    "type": "string",
                    "description": "Git 仓库路径，默认当前目录",
                    "default": ".",
                },
            },
            "required": ["branch_a", "branch_b"],
        },
    },
    {
        "name": "resolve_conflicts",
        "description": "将一个分支合并到目标分支，自动解决合并冲突。触发 git merge，解析冲突标记，逐块调用 LLM 生成合并代码",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "源分支（要合并进来的分支）",
                },
                "target": {
                    "type": "string",
                    "description": "目标分支（合并的目标），默认 main",
                    "default": "main",
                },
                "apply": {
                    "type": "boolean",
                    "description": "是否实际写入文件，false 则仅预览",
                    "default": False,
                },
                "repo_path": {
                    "type": "string",
                    "description": "Git 仓库路径，默认当前目录",
                    "default": ".",
                },
            },
            "required": ["source"],
        },
    },
    {
        "name": "list_branches",
        "description": "列出 Git 仓库中的所有分支",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Git 仓库路径，默认当前目录",
                    "default": ".",
                },
            },
        },
    },
    {
        "name": "sample_analysis",
        "description": "使用内置示例数据运行一次分析，展示工具输出格式（无需 API Key，无需真实 Git 仓库）",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Tool handlers
# ═══════════════════════════════════════════════════════════════════════════

def _handle_analyze(branch_a: str, branch_b: str, target: str = "main", repo_path: str = ".") -> dict:
    repo = get_repo(repo_path)
    target = target or "main"
    # 分别获取两个分支相对于目标分支的变更（三点式 diff = 分支独有的变化）
    diff_a = repo.git.diff(f"{target}...{branch_a}")
    diff_b = repo.git.diff(f"{target}...{branch_b}")
    diff_text = ""
    if diff_a:
        diff_text += f"# {branch_a} 相对 {target} 的变更\n{diff_a}\n"
    if diff_b:
        diff_text += f"# {branch_b} 相对 {target} 的变更\n{diff_b}"
    if not diff_text.strip():
        return {"success": True, "message": f"两个分支相对 {target} 都没有差异", "report": None}
    report = analyze_diff(diff_text)

    # 提取代码片段
    from src.git_ops import extract_conflict_snippets
    for c in report.conflicts:
        snippet = extract_conflict_snippets(diff_text, c.file_path)
        if snippet:
            lines = snippet.split("\n")
            if len(lines) > 30:
                snippet = "\n".join(lines[:30]) + "\n... (截断)"
            c.code_snippet = snippet

    return {
        "success": True,
        "report": json.loads(report.model_dump_json()),
    }


def _handle_resolve(source: str, target: str = "main", apply: bool = False, repo_path: str = ".") -> dict:
    from src.merger import resolve_all
    from git import Repo

    repo = Repo(repo_path, search_parent_directories=True)
    target = target or "main"
    report = resolve_all(repo, source, target, dry_run=not apply)
    return {
        "success": True,
        "report": json.loads(report.model_dump_json()),
    }


def _handle_list_branches(repo_path: str = ".") -> dict:
    from git import Repo
    repo = Repo(repo_path, search_parent_directories=True)
    branches = []
    for h in repo.heads:
        branches.append({"name": h.name, "commit": h.commit.hexsha[:8]})
    return {"success": True, "branches": branches}


def _handle_sample() -> dict:
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        report = test_with_sample_diff()
    return {
        "success": True,
        "report": json.loads(report.model_dump_json()),
    }


HANDLERS: dict[str, Callable] = {
    "analyze_conflicts": _handle_analyze,
    "resolve_conflicts": _handle_resolve,
    "list_branches": _handle_list_branches,
    "sample_analysis": _handle_sample,
}


# ═══════════════════════════════════════════════════════════════════════════
# MCP 协议主循环
# ═══════════════════════════════════════════════════════════════════════════

def _serve() -> None:
    """主循环：逐行读取 stdin 上的 JSON-RPC 请求并响应。"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        # ── initialize ──
        if method == "initialize":
            _send(_result(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "merge-explain",
                    "version": "0.1.0",
                },
            }))
            continue

        # ── notifications ──
        if method == "notifications/initialized":
            continue

        # ── tools/list ──
        if method == "tools/list":
            _send(_result(req_id, {"tools": TOOLS}))
            continue

        # ── tools/call ──
        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            handler = HANDLERS.get(tool_name)
            if not handler:
                _send(_error(req_id, -32601, f"Tool not found: {tool_name}"))
                continue

            try:
                result_data = handler(**arguments)
                # 工具调用的结果需要包装在 content 数组里
                _send(_result(req_id, {
                    "content": [{"type": "text", "text": json.dumps(result_data, ensure_ascii=False)}],
                }))
            except Exception as e:
                tb = traceback.format_exc()
                _send(_error(req_id, -32603, str(e), tb))
            continue

        # ── 未知方法 ──
        _send(_error(req_id, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    _serve()
