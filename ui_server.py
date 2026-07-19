"""
Merge-Explain Web UI — 浏览器中可视化分析合并冲突。
启动: python ui_server.py
"""
import json, os, sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 确保能导入 src
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from src.git_ops import get_repo, get_diff_text, get_merge_base
from src.analyzer import analyze_diff


PORT = 13920
TEMPLATE = Path(__file__).parent / "templates" / "index.html"
HTML_CACHE = None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self._serve_html()
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        routes = {
            "/api/load": self._load_repo,
            "/api/analyze": self._analyze,
            "/api/resolve": self._resolve,
            "/api/list-dirs": self._list_dirs,
            "/api/compare": self._compare,
        }
        handler = routes.get(self.path)
        if handler:
            handler(body)
        else:
            self._json(404, {"error": "not found"})

    # ── HTML ──
    def _serve_html(self):
        global HTML_CACHE
        if HTML_CACHE is None:
            HTML_CACHE = TEMPLATE.read_text(encoding="utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(HTML_CACHE.encode())

    # ── API: list directories ──
    def _list_dirs(self, body):
        path = body.get("path", ".")
        try:
            p = Path(path).resolve()
            entries = []
            for child in sorted(p.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    entries.append(child.name)
            parent = str(p.parent) if p.parent != p else ""
            self._json(200, {
                "success": True,
                "current": str(p),
                "parent": parent,
                "dirs": entries,
                "is_git": (p / ".git").exists()
            })
        except Exception as e:
            self._json(200, {"success": False, "error": str(e)})

    # ── API: compare two refs for a file ──
    def _compare(self, body):
        ref_a = body.get("ref_a", "main")
        ref_b = body.get("ref_b", "")
        file_path = body.get("file", "")
        repo_path = body.get("repo", ".")
        import difflib, subprocess
        try:
            def get_lines(ref):
                try:
                    out = subprocess.check_output(
                        ["git", "-C", repo_path, "show", f"{ref}:{file_path}"],
                        stderr=subprocess.DEVNULL
                    ).decode("utf-8")
                    return out.splitlines()
                except:
                    return []
            lines_a = get_lines(ref_a)
            lines_b = get_lines(ref_b)
            matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
            rows = []
            na, nb = 0, 0
            for op, i1, i2, j1, j2 in matcher.get_opcodes():
                for idx in range(max(i2-i1, j2-j1)):
                    la = lines_a[i1+idx] if i1+idx < i2 else ""
                    lb = lines_b[j1+idx] if j1+idx < j2 else ""
                    if op == 'equal':
                        na += 1; nb += 1
                        rows.append({"t":"eq","la":la,"lb":lb,"na":na,"nb":nb})
                    elif op == 'replace':
                        na += 1; nb += 1
                        rows.append({"t":"rp","la":la,"lb":lb,"na":na,"nb":nb})
                    elif op == 'delete':
                        na += 1
                        rows.append({"t":"dl","la":la,"lb":"","na":na,"nb":0})
                    elif op == 'insert':
                        nb += 1
                        rows.append({"t":"ad","la":"","lb":lb,"na":0,"nb":nb})
            self._json(200, {"success": True, "rows": rows, "file": file_path})
        except Exception as e:
            import traceback
            self._json(200, {"success": False, "error": str(e), "trace": traceback.format_exc()})

    # ── API: load repo ──
    def _load_repo(self, body):
        path = body.get("path", ".")
        try:
            repo = get_repo(path)
            branches = sorted([h.name for h in repo.heads])
            abs_path = str(Path(repo.working_dir).resolve())
            self._json(200, {"success": True, "path": abs_path, "branches": branches})
        except Exception as e:
            self._json(200, {"success": False, "error": str(e)})

    # ── API: analyze ──
    def _analyze(self, body):
        repo_path = body.get("repo", ".")
        branch_a = body.get("branch_a", "")
        branch_b = body.get("branch_b", "")
        target = body.get("target", "main")
        try:
            repo = get_repo(repo_path)
            # 分别获取两个分支相对于 target 的 diff
            merge_base = repo.git.merge_base(target, branch_a).strip()
            diff_a = repo.git.diff(merge_base, branch_a)
            diff_b = repo.git.diff(merge_base, branch_b)
            diff_text = ""
            if diff_a:
                diff_text += f"# {branch_a} 相对 {target} 的变更\n{diff_a}\n"
            if diff_b:
                diff_text += f"# {branch_b} 相对 {target} 的变更\n{diff_b}\n"
            if not diff_text.strip():
                self._json(200, {"success": True, "report": {
                    "branch_a_summary": [], "branch_b_summary": [],
                    "conflicts": [],
                    "overall_advice": "auto_merge",
                    "reasoning": "两个分支相对目标分支都没有差异"
                }})
                return

            report = analyze_diff(diff_text)
            d = json.loads(report.model_dump_json())

            # 附上代码片段
            for c in d.get("conflicts", []):
                snippet = self._extract_snippet(diff_text, c["file_path"])
                if snippet:
                    c["code_snippet"] = snippet

            self._json(200, {"success": True, "report": d})
        except Exception as e:
            import traceback
            self._json(200, {"success": False, "error": str(e), "trace": traceback.format_exc()})

    # ── API: resolve ──
    def _resolve(self, body):
        repo_path = body.get("repo", ".")
        source = body.get("source", "")
        target = body.get("target", "")
        apply = body.get("apply", False)
        try:
            from src.merger import resolve_all
            from git import Repo
            repo = Repo(repo_path, search_parent_directories=True)
            report = resolve_all(repo, source, target, dry_run=not apply)
            d = json.loads(report.model_dump_json())
            self._json(200, {"success": True, "report": d})
        except Exception as e:
            import traceback
            self._json(200, {"success": False, "error": str(e), "trace": traceback.format_exc()})

    # ── helper ──
    def _extract_snippet(self, diff_text, file_path):
        lines = diff_text.splitlines()
        result = []
        in_file = False
        for line in lines:
            if line.startswith("diff --git") and file_path in line:
                in_file = True
            if in_file:
                result.append(line)
                if in_file and line.startswith("diff --git") and file_path not in line:
                    break
        return "\n".join(result[:60]) if result else ""

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, fmt, *args):
        pass  # 安静运行


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"\n  🌐 Merge-Explain Web UI")
    print(f"  {'='*40}")
    print(f"  地址: http://127.0.0.1:{PORT}")
    print(f"  退出: Ctrl+C\n")

    # 自动打开浏览器
    import webbrowser
    webbrowser.open(f"http://127.0.0.1:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  已停止")
        server.server_close()


if __name__ == "__main__":
    main()
