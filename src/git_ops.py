"""
Git 操作封装：获取分支间的 Diff 信息。
"""
import os
import re
from typing import List, Optional, Tuple

from git import Repo, GitCommandError


def get_repo(path: str = ".") -> Repo:
    """获取当前目录的 Git 仓库对象。"""
    repo = Repo(path, search_parent_directories=True)
    return repo


def estimate_tokens(text: str) -> int:
    """粗略估计文本的 token 数（按 4 字符 / token）。"""
    return len(text) // 4


MAX_DIFF_TOKENS = 5000


def get_diff_text(repo: Repo, branch_a: str, branch_b: str) -> str:
    """
    获取两个分支间的完整 Diff 文本。
    如果 Diff 超过 MAX_DIFF_TOKENS，自动降级为仅文件名 + 逐文件截取函数片段。
    """
    try:
        # 获取 merge-base
        merge_base = repo.git.merge_base(branch_a, branch_b).strip()
        # 分别对比两分支相对于 merge-base 的变更（比 combined diff 信息更完整）
        diff_a = repo.git.diff(merge_base, branch_a)
        diff_b = repo.git.diff(merge_base, branch_b)
        if diff_a and diff_b:
            diff_text = diff_a + "\n" + diff_b
        else:
            diff_text = diff_a or diff_b or ""
    except GitCommandError as e:
        raise RuntimeError(f"获取 Git Diff 失败: {e}")

    if not diff_text or estimate_tokens(diff_text) <= MAX_DIFF_TOKENS:
        return diff_text or ""

    # Diff 太大，降级为逐文件截取函数级片段
    return _get_truncated_diff(repo, branch_a, branch_b, merge_base)


def _get_truncated_diff(
    repo: Repo, branch_a: str, branch_b: str, merge_base: str
) -> str:
    """
    当完整 Diff 超过 Token 限制时，只截取发生改动的函数/类上下文片段。
    分别获取两分支的变更文件列表后合并去重。
    """
    # 分别获取两分支的变更文件列表（相对 merge-base）
    files_a = repo.git.diff(
        merge_base, branch_a, "--name-only"
    ).strip().splitlines()
    files_b = repo.git.diff(
        merge_base, branch_b, "--name-only"
    ).strip().splitlines()
    changed_files = list(set(files_a + files_b))
    changed_files = [f for f in changed_files if f.strip()]

    fragments: List[str] = []

    for file_path in changed_files:
        try:
            diff_a = repo.git.diff(merge_base, branch_a, "--", file_path)
            diff_b = repo.git.diff(merge_base, branch_b, "--", file_path)
            file_diff = ""
            if diff_a:
                file_diff += diff_a
            if diff_b:
                if file_diff:
                    file_diff += "\n"
                file_diff += diff_b
            if not file_diff:
                continue

            context = _extract_function_context(file_diff)
            if context:
                fragments.append(f"## {file_path}\n{context}\n")
        except GitCommandError:
            continue

    return "\n".join(fragments) if fragments else ""
def _extract_function_context(diff_text: str) -> str:
    """
    从单个文件的 Diff 中提取函数/类定义的上下文行。
    只保留包含 def / class / async def 的行及附近几行。
    """
    lines = diff_text.splitlines()
    context_lines: List[str] = []
    func_pattern = re.compile(r"^\+\s*(def |async def |class )", re.MULTILINE)

    for i, line in enumerate(lines):
        if func_pattern.match(line):
            start = max(0, i - 3)
            end = min(len(lines), i + 15)
            chunk = lines[start:end]
            context_lines.append("--- 函数/类上下文 ---")
            context_lines.extend(chunk)
            context_lines.append("")

    return "\n".join(context_lines)


def get_merge_base(repo: Repo, branch_a: str, branch_b: str) -> Optional[str]:
    """获取两个分支的 merge-base commit hash。"""
    try:
        return repo.git.merge_base(branch_a, branch_b).strip()
    except GitCommandError:
        return None


def safe_merge_check(repo: Repo, branch_a: str, branch_b: str) -> str:
    """
    安全地模拟合并（仅检查冲突，不修改工作区）。
    返回合并结果文本。
    """
    try:
        result = repo.git.merge(branch_a, "--no-commit", "--no-ff", "--no-stat")
        repo.git.merge("--abort")
        return result
    except GitCommandError as e:
        try:
            repo.git.merge("--abort")
        except GitCommandError:
            pass
        return f"冲突检测结果: {e}"
    except Exception as e:
        return f"合并检测异常: {e}"


def get_diff_for_file(
    repo: Repo, branch_a: str, branch_b: str, file_path: str, merge_base: str
) -> str:
    """获取单个文件在两个分支间的三方 diff。"""
    try:
        return repo.git.diff(merge_base, branch_a, branch_b, "--", file_path)
    except GitCommandError:
        return ""
