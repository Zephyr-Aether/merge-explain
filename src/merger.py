"""
冲突解决模块：
1. 解析 git merge 产生的 <<<<<<< 冲突标记
2. 调用 LLM 逐块生成合并代码
3. 安全应用（语法检查 + 预览 diff）
"""
import re
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from git import Repo, GitCommandError

from src.models import ConflictRegion, ResolveChange, ResolveReport, RiskLevel
from src.analyzer import get_openai_client, get_model_name, _supports_json_mode

# ---------------------------------------------------------------------------
# 冲突标记正则
# ---------------------------------------------------------------------------
_CONFLICT_PAT = re.compile(
    r"(?P<header>^<<<<<<< .*$)\n"
    r"(?P<branch_b>.*?)"
    r"\n(?:(?P<base_header>^\|\|\|\|\|\|\| .*$)\n(?P<base>.*?)\n)?"
    r"\n(?P<divider>^=======$)\n"
    r"(?P<branch_a>.*?)"
    r"\n(?P<footer>^>>>>>>> .*$)",
    re.DOTALL | re.MULTILINE,
)

_CONFLICT_START = re.compile(r"^<<<<<<< ")
_CONFLICT_END = re.compile(r"^>>>>>>> ")
_CONFLICT_DIVIDER = re.compile(r"^=======$")
_CONFLICT_BASE = re.compile(r"^\|\|\|\|\|\|\| ")


# ---------------------------------------------------------------------------
# LLM Prompt
# ---------------------------------------------------------------------------
RESOLVE_PROMPT = """你是一个代码合并专家。你的任务是将两段有冲突的代码合并为一段无冲突的正确代码。

## 输入
- BASE：     共同祖先版本（可能为空）
- BRANCH_A： 分支 A 的改动
- BRANCH_B： 分支 B 的改动（当前 HEAD）

## 原则
1. 保留两边都有的有效逻辑，不要丢弃任意一方的功能
2. 两边改了同一行或同一条件时，判断哪个更合理，或兼容合并
3. 保持代码风格和缩进
4. 不要引入语法错误

## 输出要求
- 只输出合并后的代码，不要附加任何说明文字
- 不要用 markdown 代码块包裹"""


# ---------------------------------------------------------------------------
# 冲突解析
# ---------------------------------------------------------------------------

def parse_conflict_markers(file_path: str) -> List[ConflictRegion]:
    """
    读取文件，解析所有 <<<<<<< 冲突标记。
    支持普通格式和 diff3 格式（含 ||||||| base）。
    返回 ConflictRegion 列表。
    """
    p = Path(file_path)
    if not p.exists():
        return []

    raw = p.read_text(encoding="utf-8")
    return _parse_markers(raw, file_path)


def _parse_markers(content: str, file_path: str) -> List[ConflictRegion]:
    """从文本内容中解析冲突标记。"""
    lines = content.splitlines()
    regions: List[ConflictRegion] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if not _CONFLICT_START.match(line):
            i += 1
            continue

        # 记录冲突起始行号（1-indexed）
        region_line = i + 1
        context_before = "\n".join(lines[max(0, i - 5) : i])

        i += 1
        branch_b: List[str] = []
        base: List[str] = []
        branch_a: List[str] = []
        has_base = False

        # 读取 branch_b 直到 ======= 或 |||||||
        while i < len(lines) and not _CONFLICT_DIVIDER.match(lines[i]):
            if _CONFLICT_BASE.match(lines[i]):
                has_base = True
                break
            branch_b.append(lines[i])
            i += 1

        if has_base:
            i += 1  # 跳过 |||||||
            while i < len(lines) and not _CONFLICT_DIVIDER.match(lines[i]):
                base.append(lines[i])
                i += 1

        # i 在 ======= 行
        i += 1  # 跳过 =======

        while i < len(lines) and not _CONFLICT_END.match(lines[i]):
            branch_a.append(lines[i])
            i += 1

        # i 在 >>>>>>> 行，记录结束位置
        end_idx = i
        i += 1  # 跳过 >>>>>>>

        context_after = "\n".join(lines[end_idx + 1 : min(len(lines), end_idx + 6)])

        region_id = f"{file_path}:{region_line}"

        regions.append(ConflictRegion(
            file_path=file_path,
            region_id=region_id,
            base_version="\n".join(base),
            branch_a_version="\n".join(branch_a).strip(),
            branch_b_version="\n".join(branch_b).strip(),
            context_before=context_before,
            context_after=context_after,
        ))

    return regions


# ---------------------------------------------------------------------------
# 备份 & 语法检查
# ---------------------------------------------------------------------------

def _syntax_check(file_path: str) -> Tuple[bool, str]:
    """Python 语法检查。非 .py 文件直接通过。"""
    if not file_path.endswith(".py"):
        return True, ""
    try:
        code = Path(file_path).read_text(encoding="utf-8")
        compile(code, file_path, "exec")
        return True, ""
    except SyntaxError as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# 单块 LLM 解决
# ---------------------------------------------------------------------------

def resolve_region(region: ConflictRegion) -> Optional[ResolveChange]:
    """调用 LLM 解决单个冲突块。失败返回 None。"""
    try:
        client = get_openai_client()
        model = get_model_name()
    except ValueError as e:
        print(f"  [跳过] {e}")
        return None

    parts = [f"## 文件\n{region.file_path}\n"]
    if region.base_version:
        parts.append(f"\n## BASE（共同祖先）\n{region.base_version}\n")
    parts.append(f"\n## BRANCH_A\n{region.branch_a_version}\n")
    parts.append(f"\n## BRANCH_B\n{region.branch_b_version}\n")
    if region.suggestion:
        parts.append(f"\n## 处理建议\n{region.suggestion}\n")
    prompt = "".join(parts)

    try:
        kwargs: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": RESOLVE_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.05,
            "max_tokens": 4096,
        }
        if _supports_json_mode(model):
            kwargs["response_format"] = {"type": "text"}

        response = client.chat.completions.create(**kwargs)
        raw = response.choices[0].message.content
        if not raw:
            return None

        # 去掉 markdown 代码块包裹
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n```$", "", raw)
            raw = raw.strip()

        return ResolveChange(
            file_path=region.file_path,
            region_id=region.region_id,
            resolved_code=raw,
            explanation="由 LLM 自动合并",
            risk=RiskLevel.YELLOW,
        )
    except Exception as e:
        print(f"  [失败] {region.region_id}: {type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# 替换文件中的冲突块
# ---------------------------------------------------------------------------

def replace_conflict_in_file(
    file_path: str, region: ConflictRegion, resolved_code: str
) -> Tuple[bool, str]:
    """
    在文件中找到该冲突块，用 resolved_code 替换。
    通过匹配 branch_a_version 或 branch_b_version 定位冲突。
    """
    p = Path(file_path)
    if not p.exists():
        return False, "文件不存在"

    content = p.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines: List[str] = []
    i = 0
    found = False

    while i < len(lines):
        if not _CONFLICT_START.match(lines[i]):
            new_lines.append(lines[i])
            i += 1
            continue

        # 找到冲突起始
        start = i
        conflict_content: List[str] = []
        i += 1

        # 收集整个冲突块内容（跳过 base 部分）
        while i < len(lines) and not _CONFLICT_END.match(lines[i]):
            conflict_content.append(lines[i])
            i += 1

        if i < len(lines):
            conflict_content.append(lines[i])  # >>>>>>> 行
            i += 1

        conflict_text = "\n".join(conflict_content)

        # 判断是否目标冲突
        a_in = region.branch_a_version in conflict_text
        b_in = region.branch_b_version in conflict_text

        if a_in or b_in:
            found = True
            resolved_lines = resolved_code.splitlines()
            new_lines.extend(resolved_lines)
        else:
            # 不是目标冲突，还原
            new_lines.append(lines[start])
            new_lines.extend(conflict_content)

    if not found:
        return False, "未在文件中找到匹配的冲突块"

    # 备份后写入
    bak = str(p) + ".bak"
    try:
        shutil.copy2(str(p), bak)
        p.write_text("\n".join(new_lines), encoding="utf-8")

        remaining = "<<<<<<<" in p.read_text(encoding="utf-8")
        if not remaining:
            ok, err = _syntax_check(str(p))
            if not ok:
                shutil.copy2(bak, str(p))
                Path(bak).unlink(missing_ok=True)
                return False, f"语法错误: {err}"

        Path(bak).unlink(missing_ok=True)
        return True, ""
    except Exception as e:
        if Path(bak).exists():
            shutil.copy2(bak, str(p))
            Path(bak).unlink(missing_ok=True)
        return False, str(e)


# ---------------------------------------------------------------------------
# 完整流水线
# ---------------------------------------------------------------------------

def resolve_all(
    repo: Repo,
    branch_a: str,
    branch_b: str,
    suggestions: Optional[dict[str, str]] = None,
    decisions: Optional[dict[str, str]] = None,
    risk_threshold: str = "yellow",
    dry_run: bool = True,
    commit: bool = False,
) -> ResolveReport:
    """
    完整解决流程：
    1. git merge 触发冲突
    2. 解析所有冲突标记
    3. 逐块调用 LLM 解决
    4. 替换文件（或预览）
    5. git merge --abort 恢复
    """
    import time

    changes: List[ResolveChange] = []
    skipped: List[ConflictRegion] = []
    wd = Path(repo.working_dir)
    resolved_files: dict[str, str] = {}

    # 0. 切换到目标分支
    orig_branch = repo.active_branch.name
    if orig_branch != branch_b:
        repo.git.checkout(branch_b)

    try:
        # 1. 触发 merge
        print(f"  合并 {branch_a} → {branch_b} ...")
        repo.git.merge(branch_a, "--no-commit", "--no-ff")
    except GitCommandError:
        pass  # 有冲突是预期的

    aborted = False

    try:
        # 2. 找出有冲突的文件
        conflicted = (
            repo.git.diff("--name-only", "--diff-filter=U").strip().splitlines()
        )
        conflicted = [f for f in conflicted if f.strip()]

        if not conflicted:
            print("  ✅ 无冲突，已自动完成合并。")
            repo.git.merge("--abort")
            aborted = True
            return ResolveReport(
                branch_a=branch_a, branch_b=branch_b,
                changes=[], skipped=[],
                total_conflicts=0, resolved_count=0, skipped_count=0,
                status="all_resolved",
            )

        print(f"  发现 {len(conflicted)} 个冲突文件")

        # 3. 解析所有冲突
        all_regions: List[ConflictRegion] = []
        for fp in conflicted:
            regions = parse_conflict_markers(str(wd / fp))
            sug = (suggestions or {}).get(fp)
            for r in regions:
                if sug:
                    r.suggestion = sug
            all_regions.extend(regions)

        print(f"  共 {len(all_regions)} 个冲突块\n")

        # 4. 逐块解决
        for region in all_regions:
            print(f"  → {region.region_id}")

            if risk_threshold == "green":
                skipped.append(region)
                print("    跳过（阈值 green）")
                continue

            # 检查用户决策
            user_choice = (decisions or {}).get(region.file_path)
            if user_choice in ("a", "b"):
                raw = region.branch_a_version if user_choice == "a" else region.branch_b_version
                result = ResolveChange(
                    file_path=region.file_path,
                    region_id=region.region_id,
                    resolved_code=raw,
                    explanation=f"User chose branch {user_choice.upper()}",
                    risk=RiskLevel.GREEN,
                )
                print(f"    ✅ 用户选择分支 {user_choice.upper()}")
            else:
                time.sleep(0.3)
                result = resolve_region(region)

            if dry_run and not commit:
                changes.append(result)
                print(f"    ✅ (预览) 合并后代码 {len(result.resolved_code)} 字符")
                continue

            ok, msg = replace_conflict_in_file(
                str(wd / region.file_path), region, result.resolved_code
            )
            if ok:
                changes.append(result)
                if not commit and region.file_path not in resolved_files:
                    resolved_files[region.file_path] = Path(wd / region.file_path).read_text()
                print(f"    ✅ 已解决")
            else:
                skipped.append(region)
                print(f"    ❌ {msg}")

        # 5. commit or abort
        if commit and changes:
            repo.git.add("--all")
            repo.git.commit("-m", f"Merge branch '{branch_a}' with automatic conflict resolution")
            aborted = True
        else:
            repo.git.merge("--abort")
            aborted = True
            for fp, content in resolved_files.items():
                Path(wd / fp).write_text(content)

    except Exception as e:
        print(f"  [错误] {e}")
    finally:
        if not aborted:
            try:
                repo.git.merge("--abort")
            except GitCommandError:
                pass
        # 切回原分支
        if orig_branch != branch_b:
            try:
                repo.git.checkout(orig_branch)
            except GitCommandError:
                pass

    total = len(all_regions)
    resolved = len(changes)
    skipped_c = len(skipped)

    status = "all_resolved" if resolved == total else ("partial" if resolved > 0 else "failed")

    return ResolveReport(
        branch_a=branch_a,
        branch_b=branch_b,
        changes=changes,
        skipped=skipped,
        total_conflicts=total,
        resolved_count=resolved,
        skipped_count=skipped_c,
        status=status,
    )
