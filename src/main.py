"""
Merge-Explain CLI 入口。
"""
import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.analyzer import analyze_diff, test_with_sample_diff
from src.git_ops import get_repo, get_diff_text
from src.reporter import (
    console,
    export_html,
    export_markdown,
    print_report,
)

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

        # Step 3: 调用 LLM 分析
        task3 = progress.add_task("正在调用 AI 分析变更...", total=None)
        try:
            report = analyze_diff(diff_text)
        except Exception as e:
            console.print(f"[red]❌ AI 分析失败: {e}[/red]")
            raise typer.Exit(code=1)
        progress.remove_task(task3)

    # 输出报告
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
        # 未指定 format 但给了 output，默认导出 HTML
        export_html(report, output)
    elif output:
        # 已有 format，已在上面导出
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
