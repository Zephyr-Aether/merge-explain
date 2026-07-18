"""
报告输出模块：Rich 终端彩色打印 + HTML/Markdown 导出。
"""
import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from src.models import MergeReport, RiskLevel

console = Console()

_RISK_STYLES = {
    RiskLevel.GREEN: "bold green",
    RiskLevel.YELLOW: "bold yellow",
    RiskLevel.RED: "bold red",
}

_RISK_LABELS = {
    RiskLevel.GREEN: "🟢 自动合并",
    RiskLevel.YELLOW: "🟡 建议人工",
    RiskLevel.RED: "🔴 必须人工",
}

_ADVICE_STYLES = {
    "auto_merge": "bold green",
    "manual_review": "bold yellow",
    "blocked": "bold red",
}


def print_report(report: MergeReport) -> None:
    """在终端打印格式化的 MergeReport。"""
    _print_header(report)
    _print_summary(report)
    _print_conflicts(report)
    _print_overall(report)


def _print_header(report: MergeReport) -> None:
    """打印报告标题。"""
    title = Text("Merge-Explain 冲突分析报告", style="bold cyan")
    subtitle = Text(f"报告版本: {report.report_version}", style="dim")
    console.print()
    console.print(Panel(title, subtitle=subtitle, box=box.ROUNDED))
    console.print()


def _print_summary(report: MergeReport) -> None:
    """打印分支变更摘要。"""
    for branch_label, items in [
        ("Branch A 变更摘要", report.branch_a_summary),
        ("Branch B 变更摘要", report.branch_b_summary),
    ]:
        table = Table(
            title=branch_label,
            title_style="bold",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold blue",
        )
        table.add_column("文件路径", style="dim", width=35)
        table.add_column("函数/类名", style="cyan", width=30)
        table.add_column("变更描述", style="white", width=70)

        for item in items:
            table.add_row(item.file_path, item.function_name, item.change_desc)

        if not items:
            table.add_row("—", "—", "无变更")

        console.print(table)
        console.print()


def _print_conflicts(report: MergeReport) -> None:
    """打印冲突详情（用颜色区分风险等级）。"""
    if not report.conflicts:
        console.print(Panel("✅ 未检测到冲突点", style="bold green"))
        console.print()
        return

    for i, conflict in enumerate(report.conflicts, 1):
        risk_style = _RISK_STYLES.get(conflict.risk, "white")
        risk_label = _RISK_LABELS.get(conflict.risk, "未知")

        conflict_panel = Panel(
            f"[bold]冲突点 #{i}[/bold]   风险等级: [{risk_style}]{risk_label}[/{risk_style}]\n\n"
            f"[bold]文件:[/bold] {conflict.file_path}\n\n"
            f"[bold]Branch A 操作:[/bold]\n{conflict.branch_a_action}\n\n"
            f"[bold]Branch B 操作:[/bold]\n{conflict.branch_b_action}\n\n"
            f"[bold]处理建议:[/bold]\n{conflict.suggestion}",
            title=f"⚠ 冲突点 #{i}",
            border_style=conflict.risk.value,
            box=box.ROUNDED,
        )
        console.print(conflict_panel)
        console.print()


def _print_overall(report: MergeReport) -> None:
    """打印总体决策建议。"""
    advice_style = _ADVICE_STYLES.get(report.overall_advice, "white")
    advice_labels = {
        "auto_merge": "✅ 建议自动合并",
        "manual_review": "⚠️ 建议人工审查",
        "blocked": "🚫 阻塞，必须人工处理",
    }
    advice_label = advice_labels.get(report.overall_advice, report.overall_advice)

    overall_panel = Panel(
        f"[{advice_style}]{advice_label}[/{advice_style}]\n\n"
        f"[bold]理由:[/bold] {report.reasoning}",
        title="总体决策",
        border_style="bright_blue",
        box=box.ROUNDED,
    )
    console.print(overall_panel)
    console.print()


def export_html(report: MergeReport, output_path: str) -> None:
    """将报告导出为 HTML 文件。"""
    risk_colors = {
        RiskLevel.GREEN: "#22c55e",
        RiskLevel.YELLOW: "#eab308",
        RiskLevel.RED: "#ef4444",
    }

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN"><head><meta charset="UTF-8">',
        "<title>Merge-Explain 冲突分析报告</title>",
        "<style>",
        "body { font-family: -apple-system, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; }",
        "h1 { color: #222; } h2 { color: #444; margin-top: 30px; }",
        "table { width: 100%; border-collapse: collapse; margin: 16px 0; }",
        "th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #ddd; }",
        "th { background: #f5f5f5; }",
        ".conflict-card { border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 12px 0; }",
        ".risk-green { border-left: 4px solid #22c55e; }",
        ".risk-yellow { border-left: 4px solid #eab308; }",
        ".risk-red { border-left: 4px solid #ef4444; }",
        ".advice { font-size: 1.2em; font-weight: bold; padding: 12px; border-radius: 8px; }",
        ".advice-auto_merge { background: #dcfce7; color: #166534; }",
        ".advice-manual_review { background: #fef9c3; color: #854d0e; }",
        ".advice-blocked { background: #fee2e2; color: #991b1b; }",
        "</style></head><body>",
        "<h1>Merge-Explain 冲突分析报告</h1>",
        f"<p>报告版本: {report.report_version}</p>",
    ]

    for label, items in [
        ("Branch A 变更摘要", report.branch_a_summary),
        ("Branch B 变更摘要", report.branch_b_summary),
    ]:
        html_parts.append(f"<h2>{label}</h2>")
        if not items:
            html_parts.append("<p>无变更</p>")
        else:
            html_parts.append(
                "<table><tr><th>文件路径</th><th>函数/类名</th><th>变更描述</th></tr>"
            )
            for item in items:
                html_parts.append(
                    f"<tr><td>{item.file_path}</td>"
                    f"<td>{item.function_name}</td>"
                    f"<td>{item.change_desc}</td></tr>"
                )
            html_parts.append("</table>")

    html_parts.append("<h2>冲突详情</h2>")
    if not report.conflicts:
        html_parts.append("<p>✅ 未检测到冲突点</p>")
    else:
        for conflict in report.conflicts:
            color = risk_colors.get(conflict.risk, "#666")
            html_parts.append(
                f'<div class="conflict-card risk-{conflict.risk.value}">'
                f"<p><strong>文件:</strong> {conflict.file_path}</p>"
                f"<p><strong>风险等级:</strong> "
                f'<span style="color:{color};font-weight:bold">{conflict.risk.value}</span></p>'
                f"<p><strong>Branch A 操作:</strong> {conflict.branch_a_action}</p>"
                f"<p><strong>Branch B 操作:</strong> {conflict.branch_b_action}</p>"
                f"<p><strong>处理建议:</strong> {conflict.suggestion}</p>"
                "</div>"
            )

    html_parts.append(
        f'<div class="advice advice-{report.overall_advice}">'
        f"<p>总体建议: {report.overall_advice}</p>"
        f"<p>理由: {report.reasoning}</p>"
        "</div>"
    )
    html_parts.append("</body></html>")

    Path(output_path).write_text("\n".join(html_parts), encoding="utf-8")
    console.print(f"[green]✅ HTML 报告已导出: {output_path}[/green]")


def export_markdown(report: MergeReport, output_path: str) -> None:
    """将报告导出为 Markdown 文件。"""
    lines = [
        "# Merge-Explain 冲突分析报告",
        f"报告版本: {report.report_version}",
        "",
    ]

    for label, items in [
        ("## Branch A 变更摘要", report.branch_a_summary),
        ("## Branch B 变更摘要", report.branch_b_summary),
    ]:
        lines.append(label)
        if not items:
            lines.append("无变更")
        else:
            lines.append("| 文件路径 | 函数/类名 | 变更描述 |")
            lines.append("| --- | --- | --- |")
            for item in items:
                lines.append(
                    f"| {item.file_path} | {item.function_name} | {item.change_desc} |"
                )
        lines.append("")

    lines.append("## 冲突详情")
    if not report.conflicts:
        lines.append("✅ 未检测到冲突点")
    else:
        for i, conflict in enumerate(report.conflicts, 1):
            lines.append(f"### 冲突点 #{i} (风险: {conflict.risk.value})")
            lines.append(f"- **文件**: {conflict.file_path}")
            lines.append(f"- **Branch A 操作**: {conflict.branch_a_action}")
            lines.append(f"- **Branch B 操作**: {conflict.branch_b_action}")
            lines.append(f"- **处理建议**: {conflict.suggestion}")
            lines.append("")

    lines.append("## 总体决策")
    lines.append(f"**建议**: {report.overall_advice}")
    lines.append(f"**理由**: {report.reasoning}")
    lines.append("")

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[green]✅ Markdown 报告已导出: {output_path}[/green]")


def print_sample_test() -> None:
    """打印一个示例报告（用于 Phase 3 独立测试）。"""
    from src.analyzer import test_with_sample_diff

    report = test_with_sample_diff()
    print_report(report)
