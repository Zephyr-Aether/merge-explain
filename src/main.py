"""
Merge-Explain CLI 入口。
"""
import json
import sys
from pathlib import Path
import hashlib
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.analyzer import analyze_diff, test_with_sample_diff, MergeReport
from src.git_ops import get_repo, get_diff_text, extract_conflict_snippets, get_merge_base
from src.merger import resolve_all, parse_conflict_markers, ConflictRegion
from src.reporter import (
    console,
    export_html,
    export_markdown,
    print_report,
)
_CACHE_DIR = Path(".merge-explain-cache")


def _cache_key(branch_a: str, branch_b: str, diff_text: str, model: str) -> str:
    """生成缓存 key（分支 + diff 摘要 + 模型名）。"""
    raw = f"{branch_a}||{branch_b}||{len(diff_text)}||{diff_text[:200]}||{model}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_cache(key: str) -> Optional[MergeReport]:
    """尝试从缓存加载报告。"""
    cache_file = _CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            raw = cache_file.read_text(encoding="utf-8")
            return MergeReport.model_validate_json(raw)
        except Exception:
            return None
    return None


def _save_cache(key: str, report: MergeReport) -> None:
    """将报告写入缓存。"""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _CACHE_DIR / f"{key}.json"
    cache_file.write_text(report.model_dump_json(), encoding="utf-8")



app = typer.Typer(
    name="merge-explain",
    help="可解释性 AI 合并工具 — 先理解，再合并",
    add_completion=False,
)


def _load_env() -> None:
    """加载 .env 文件（如果存在）。"""
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # 也尝试加载项目根目录的 .env
        load_dotenv()


@app.command()
def analyze(
    branch_a: str = typer.Argument(
        ..., help="源分支 A（要合并进来的分支）"
    ),
    branch_b: str = typer.Argument(
        ..., help="目标分支 B（合并的目标分支）"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="导出报告的文件路径（可选）",
    ),
    format: str = typer.Option(
        "terminal", "--format", "-f",
        help="输出格式: terminal / html / markdown",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="同时显示原始 Diff 文本",
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache",
        help="跳过缓存，重新调用 LLM 分析",
    ),
    auto_apply: bool = typer.Option(
        False, "--auto-apply", "-a",
        help="【安全模式】仅模拟合并，不实际执行 Git Merge",
    ),
):
    """
    分析两个分支的代码变更，生成可读的冲突语义报告。

    流程：获取 Diff → 调用 LLM 分析 → 输出结构化报告。
    """
    _load_env()

    console.print("[bold cyan]=== Merge-Explain: 可解释性 AI 合并工具 ===[/bold cyan]")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: 获取 Git 仓库
        task1 = progress.add_task("正在获取 Git 仓库...", total=None)
        try:
            repo = get_repo()
        except Exception as e:
            console.print(f"[red]❌ 无法获取 Git 仓库: {e}[/red]")
            raise typer.Exit(code=1)
        progress.remove_task(task1)

        # Step 2: 获取 Diff
        task2 = progress.add_task("正在获取 Diff 信息...", total=None)
        diff_text = get_diff_text(repo, branch_a, branch_b)
        if not diff_text:
            console.print("[yellow]⚠️ 两个分支之间没有差异，或 Diff 为空。[/yellow]")
            raise typer.Exit(code=0)
        progress.remove_task(task2)
        console.print(
            f"[dim]Diff 长度: {len(diff_text)} 字符 "
            f"(~{len(diff_text) // 4} tokens)[/dim]"
        )

        # Step 3: 调用 LLM 分析（带缓存）
        model_name = __import__("src.analyzer", fromlist=["get_model_name"]).get_model_name()
        ckey = _cache_key(branch_a, branch_b, diff_text, model_name)

        if not no_cache:
            cached = _load_cache(ckey)
            if cached is not None:
                console.print()
                console.print("[bold yellow]📦 使用缓存结果（加 --no-cache 强制重新分析）[/bold yellow]")
                report = cached
                progress.remove_task(task3) if 'task3' in dir() else None
                continue_after_cache = True
            else:
                continue_after_cache = False
        else:
            continue_after_cache = False

        if not continue_after_cache:
            task3 = progress.add_task("正在调用 AI 分析变更...", total=None)
            try:
                report = analyze_diff(diff_text)
                _save_cache(ckey, report)
            except Exception as e:
                console.print(f"[red]❌ AI 分析失败: {e}[/red]")
                raise typer.Exit(code=1)
            progress.remove_task(task3)

    # 输出报告
    # 输出原始 diff（--verbose）
    if verbose:
        console.print()
        console.print(Panel(
            f"[bold]原始 Diff[/bold]\n\n[dim]{diff_text[:2000]}[/dim]"
            + ("\n\n... (截断)" if len(diff_text) > 2000 else ""),
            border_style="dim"
        ))

    # 为每个冲突点提取代码片段
    for conflict in report.conflicts:
        snippet = extract_conflict_snippets(diff_text, conflict.file_path)
        if snippet:
            # 截断到合理长度
            lines = snippet.split("\n")
            if len(lines) > 30:
                snippet = "\n".join(lines[:30]) + "\n... (截断)"
            conflict.code_snippet = snippet

    console.print()
    console.print("[bold green]✅ 分析完成！[/bold green]")
    console.print()

    if format == "html" and output:
        export_html(report, output)
    elif format == "markdown" and output:
        export_markdown(report, output)
    else:
        print_report(report)

    # 导出（额外输出格式支持）
    if output and format == "terminal":
        export_html(report, output)
    elif output:
        pass

    # 处理 --auto-apply
    if auto_apply:
        console.print()
        console.print(
            Panel(
                "[bold yellow]🔒 安全模式 — 模拟合并（不实际执行）[/bold yellow]\n\n"
                "当前为 MVP 阶段，--auto-apply 仅输出模拟日志，\n"
                "不会修改 Git 历史或执行实际合并操作。\n\n"
                "如需启用真实合并，请在确认报告后手动执行:\n"
                f"  git merge {branch_a}",
                border_style="yellow",
            )
        )



@app.command()
def resolve(
    branch_a: str = typer.Argument(
        ..., help="源分支 A（要合并进来的分支）"
    ),
    branch_b: str = typer.Argument(
        ..., help="目标分支 B（我们站在这个分支上）"
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run",
        help="预览模式：只输出解决结果，不修改文件（默认开启）",
    ),
    apply: bool = typer.Option(
        False, "--apply",
        help="应用模式：实际写入文件",
    ),
    from_report: str = typer.Option(
        None, "--from-report",
        help="复用 analyze 输出的报告 JSON 文件",
    ),
    risk_threshold: str = typer.Option(
        "yellow", "--risk-threshold",
        help="风险阈值：green / yellow（red 永远跳过）",
    ),
):
    """
    自动解决两个分支的合并冲突。

    先触发 git merge，解析冲突标记，逐块调用 LLM 生成合并代码。
    默认只预览不写文件，加 --apply 才实际写入。
    """
    _load_env()
    console.print("[bold cyan]=== Merge-Explain: 智能冲突解决 ===[/bold cyan]")
    console.print()

    # 加载 analyze 报告
    suggestions = None
    if from_report:
        try:
            report_data = json.loads(Path(from_report).read_text(encoding="utf-8"))
            from src.models import MergeReport as AnalyzeReport
            analyze_report = AnalyzeReport.model_validate(report_data)
            suggestions = {}
            for c in analyze_report.conflicts:
                suggestions[c.file_path] = c.suggestion
            console.print(f"[dim]已加载分析报告: {from_report}[/dim]")
        except Exception as e:
            console.print(f"[yellow]警告: 加载报告失败 ({e})，跳过建议注入[/yellow]")

    actual_apply = apply or not dry_run
    console.print(f"[dim]模式: {'应用' if actual_apply else '预览'} | "
                  f"风险阈值: {risk_threshold}[/dim]")
    console.print()

    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("正在获取 Git 仓库...", total=None)
        try:
            repo = get_repo()
        except Exception as e:
            console.print(f"[red]❌ 无法获取 Git 仓库: {e}[/red]")
            raise typer.Exit(code=1)
        progress.remove_task(task)

        task = progress.add_task("正在分析并解决冲突...", total=None)

    report = resolve_all(
        repo=repo,
        branch_a=branch_a,
        branch_b=branch_b,
        suggestions=suggestions,
        risk_threshold=risk_threshold,
        dry_run=not actual_apply,
    )

    console.print()
    console.print(f"[bold]解决报告[/bold]")
    console.print(f"  总冲突: {report.total_conflicts}")
    console.print(f"  已解决: [green]{report.resolved_count}[/green]")
    console.print(f"  跳过:   [yellow]{report.skipped_count}[/yellow]")
    console.print(f"  状态:   {report.status}")

    if report.changes:
        console.print()
        for c in report.changes:
            console.print(f"  [green]✅[/green] {c.region_id}")
            if not actual_apply:
                code_preview = c.resolved_code[:200]
                console.print(f"     [dim]{code_preview}[/dim]")
        console.print()
        if actual_apply:
            console.print("[bold green]✅ 冲突已解决并写入文件！请执行 git diff 确认并提交。[/bold green]")
        else:
            console.print("[yellow]💡 预览模式，文件未被修改。确认无误后加 --apply 应用。[/yellow]")
    else:
        console.print()
        console.print("[green]✅ 没有需要解决的冲突！[/green]")


@app.command()
@app.command()
def sample():
    """使用内置的示例 Diff 测试工具流程（无需 Git 仓库）。"""
    _load_env()
    from src.reporter import print_sample_test

    print_sample_test()


@app.command()
def version():
    """显示工具版本信息。"""
    console.print("[bold]merge-explain[/bold] 版本 0.1.0 (MVP)")
    console.print("可解释性 AI 合并工具")


def main():
    """Typer 应用入口。"""
    _load_env()
    app()


if __name__ == "__main__":
    main()
