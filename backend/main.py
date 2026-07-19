"""
Merge-Explain FastAPI Backend
"""
import sys, os, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Merge-Explain", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Import existing modules ──
from src.git_ops import get_repo, get_diff_text
from src.analyzer import analyze_diff
from src.merger import resolve_all
from git import Repo

# ── Models ──
class LoadReq(BaseModel): path: str = "."
class AnalyzeReq(BaseModel): repo: str = "."; branch_a: str; branch_b: str; target: str = "main"
class ResolveReq(BaseModel): repo: str = "."; source: str; target: str = "main"; apply: bool = False; commit: bool = False
class ListDirsReq(BaseModel): path: str = "."
class CompareReq(BaseModel): repo: str = "."; ref_a: str = "main"; ref_b: str; file: str

# ── Endpoints ──

@app.post("/api/load")
def api_load(req: LoadReq):
    try:
        repo = get_repo(req.path)
        branches = sorted([h.name for h in repo.heads])
        return {"success": True, "path": str(Path(repo.working_dir).resolve()), "branches": branches}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/analyze")
def api_analyze(req: AnalyzeReq):
    try:
        repo = get_repo(req.repo)
        merge_base = repo.git.merge_base(req.target, req.branch_a).strip()
        diff_a = repo.git.diff(merge_base, req.branch_a)
        diff_b = repo.git.diff(merge_base, req.branch_b)
        diff_text = ""
        if diff_a: diff_text += f"# {req.branch_a} vs {req.target}\\n{diff_a}\\n"
        if diff_b: diff_text += f"# {req.branch_b} vs {req.target}\\n{diff_b}"
        if not diff_text.strip():
            return {"success": True, "report": {"conflicts": [], "overall_advice": "auto_merge", "reasoning": "无差异"}}
        report = analyze_diff(diff_text)
        data = json.loads(report.model_dump_json())
        for c in data.get("conflicts", []):
            snippet = _extract_snippet(diff_text, c["file_path"])
            if snippet: c["code_snippet"] = snippet
        return {"success": True, "report": data}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e)}

@app.post("/api/resolve")
def api_resolve(req: ResolveReq):
    try:
        repo = Repo(req.repo, search_parent_directories=True)
        report = resolve_all(repo, req.source, req.target, dry_run=not (req.apply or req.commit), commit=req.commit)
        return {"success": True, "report": json.loads(report.model_dump_json())}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/list-dirs")
def api_list_dirs(req: ListDirsReq):
    try:
        p = Path(req.path).resolve()
        dirs = sorted([c.name for c in p.iterdir() if c.is_dir() and not c.name.startswith(".")])
        parent = str(p.parent) if p.parent != p else ""
        return {"success": True, "current": str(p), "parent": parent, "dirs": dirs, "is_git": (p / ".git").exists()}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/compare")
def api_compare(req: CompareReq):
    import difflib, subprocess
    try:
        def get_lines(ref):
            try:
                out = subprocess.check_output(["git", "-C", req.repo, "show", f"{ref}:{req.file}"], stderr=subprocess.DEVNULL).decode()
                return out.splitlines()
            except: return []
        lines_a = get_lines(req.ref_a)
        lines_b = get_lines(req.ref_b)
        matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
        rows, na, nb = [], 0, 0
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            for idx in range(max(i2-i1, j2-j1)):
                la = lines_a[i1+idx] if i1+idx < i2 else ""
                lb = lines_b[j1+idx] if j1+idx < j2 else ""
                if op == 'equal': na += 1; nb += 1; rows.append({"t":"eq","la":la,"lb":lb,"na":na,"nb":nb})
                elif op == 'replace': na += 1; nb += 1; rows.append({"t":"rp","la":la,"lb":lb,"na":na,"nb":nb})
                elif op == 'delete': na += 1; rows.append({"t":"dl","la":la,"lb":"","na":na,"nb":0})
                elif op == 'insert': nb += 1; rows.append({"t":"ad","la":"","lb":lb,"na":0,"nb":nb})
        return {"success": True, "rows": rows}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/pick-folder")
def api_pick_folder():
    import subprocess, platform
    try:
        if platform.system() == "Darwin":
            path = subprocess.check_output(["osascript", "-e", "POSIX path of (choose folder)"]).decode().strip()
            return {"success": True, "path": path}
        return {"success": False}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _extract_snippet(diff_text: str, file_path: str) -> str:
    lines = diff_text.splitlines()
    result, in_file = [], False
    for line in lines:
        if line.startswith("diff --git") and file_path in line: in_file = True
        if in_file:
            result.append(line)
            if line.startswith("diff --git") and file_path not in line: break
    return "\n".join(result[:80]) if result else ""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=13920)
