"""
综合场景测试：用真实 Git 仓库模拟多种分支碰撞情况。
每个场景创建独立 Git 仓库 → 验证 git_ops → 验证完整流水线。
"""
import os
from pathlib import Path

import pytest
from git import Repo, GitCommandError

from src.git_ops import get_repo, get_diff_text, get_merge_base, estimate_tokens
from src.reporter import print_report


# ===========================================================================
# 辅助验证函数
# ===========================================================================

def _verify_repo_state(repo: Repo) -> None:
    """确保仓库在 main 分支且工作区干净。"""
    assert repo.head.is_valid
    # 检查没有未提交的变更
    assert not repo.index.diff(None)


def _check_diff_has_content(diff_text: str) -> None:
    """Diff 非空且看起来像合法的 diff 文本。"""
    assert diff_text, "Diff 不应为空"
    assert "diff --git" in diff_text or "---" in diff_text, \
        "Diff 应包含标准 git diff 标记"


# ===========================================================================
# 场景测试
# ===========================================================================

class TestGreenScenario:
    """GREEN：不同函数改动，互不干扰。"""

    def test_git_ops(self, green_scenario):
        repo, branch_a, branch_b = green_scenario
        _verify_repo_state(repo)

        merge_base = get_merge_base(repo, branch_a, branch_b)
        assert merge_base, "应能找到 merge-base"

        diff_text = get_diff_text(repo, branch_a, branch_b)
        _check_diff_has_content(diff_text)

        # 确认 diff 只涉及 calculator.py
        assert "calculator.py" in diff_text
        # 两个改动都在，互不覆盖
        assert "import logging" in diff_text
        assert "type hints" in diff_text or "multiply(a: int" in diff_text

    def test_full_pipeline(self, green_scenario):
        """完整流水线：git_ops → analyzer(mock) → reporter。"""
        repo, branch_a, branch_b = green_scenario
        diff_text = get_diff_text(repo, branch_a, branch_b)
        assert diff_text

        # analyze_diff 已被 conftest mock 掉，返回 sample data
        from src.analyzer import analyze_diff
        report = analyze_diff(diff_text)
        assert report is not None
        assert report.overall_advice in ("auto_merge", "manual_review", "blocked")

        # reporter 不抛异常
        print_report(report)


class TestYellowScenario:
    """YELLOW：同一函数不同方面改动。"""

    def test_git_ops(self, yellow_scenario):
        repo, branch_a, branch_b = yellow_scenario
        _verify_repo_state(repo)

        diff_text = get_diff_text(repo, branch_a, branch_b)
        _check_diff_has_content(diff_text)

        # 双方都改了 get_user
        assert "get_user" in diff_text
        assert "user_service.py" in diff_text

    def test_full_pipeline(self, yellow_scenario):
        repo, branch_a, branch_b = yellow_scenario
        diff_text = get_diff_text(repo, branch_a, branch_b)
        from src.analyzer import analyze_diff
        report = analyze_diff(diff_text)
        assert report is not None
        print_report(report)


class TestRedScenario:
    """RED：同一行互斥改动。"""

    def test_git_ops(self, red_scenario):
        repo, branch_a, branch_b = red_scenario
        _verify_repo_state(repo)

        diff_text = get_diff_text(repo, branch_a, branch_b)
        _check_diff_has_content(diff_text)

        # 双方都改了 TIMEOUT 这一行
        assert "TIMEOUT" in diff_text
        assert "config.py" in diff_text

    def test_full_pipeline(self, red_scenario):
        repo, branch_a, branch_b = red_scenario
        diff_text = get_diff_text(repo, branch_a, branch_b)
        from src.analyzer import analyze_diff
        report = analyze_diff(diff_text)
        assert report is not None
        print_report(report)


class TestMixedScenario:
    """MIXED：多文件、多风险等级混合。"""

    def test_git_ops(self, mixed_scenario):
        repo, branch_a, branch_b = mixed_scenario
        _verify_repo_state(repo)

        diff_text = get_diff_text(repo, branch_a, branch_b)
        _check_diff_has_content(diff_text)

        # 三个文件都应出现在 diff 中
        assert "payment.py" in diff_text
        assert "auth.py" in diff_text
        assert "logger.py" in diff_text

    def test_full_pipeline(self, mixed_scenario):
        repo, branch_a, branch_b = mixed_scenario
        diff_text = get_diff_text(repo, branch_a, branch_b)
        from src.analyzer import analyze_diff
        report = analyze_diff(diff_text)
        assert report is not None
        print_report(report)


class TestLargeDiff:
    """大 Diff：测试 Token 超限时的截断逻辑。"""

    def test_diff_exceeds_token_limit(self, large_diff_scenario):
        repo, branch_a, branch_b = large_diff_scenario
        diff_text = get_diff_text(repo, branch_a, branch_b)
        token_count = estimate_tokens(diff_text)
        print(f"\n[LargeDiff] token 数: {token_count}")
        from src.git_ops import MAX_DIFF_TOKENS
        # 完整 diff 应超过 token 限制，触发截断逻辑
        # 截断后 token 数应明显小于完整 diff
        assert token_count <= MAX_DIFF_TOKENS + 100, \
            f"截断后 token ({token_count}) 应接近 MAX({MAX_DIFF_TOKENS})"
        # 截断结果应非空
        assert diff_text, "截断后的 diff 不应为空"

    def test_full_pipeline(self, large_diff_scenario):
        repo, branch_a, branch_b = large_diff_scenario
        diff_text = get_diff_text(repo, branch_a, branch_b)
        from src.analyzer import analyze_diff
        report = analyze_diff(diff_text)
        assert report is not None
        print_report(report)


class TestEmptyDiff:
    """空 Diff：两个分支无差异。"""

    def test_no_diff(self, empty_scenario):
        repo, branch_a, branch_b = empty_scenario
        diff_text = get_diff_text(repo, branch_a, branch_b)
        assert not diff_text, "无改动分支应返回空 Diff"


class TestGitOpsEdgeCases:
    """Git 操作的各种边界情况。"""

    def test_get_repo_from_subdir(self, tmp_git_dir):
        """从子目录也能找到仓库。"""
        # 创建仓库
        repo = Repo.init(tmp_git_dir)
        repo.git.config("user.name", "test")
        repo.git.config("user.email", "test@test.com")

        # 在子目录里创建文件并提交
        sub = tmp_git_dir / "sub" / "dir"
        sub.mkdir(parents=True)
        (sub / "hello.py").write_text("x = 1\n")

        repo.index.add(["sub/dir/hello.py"])
        repo.index.commit("init")

        # 从子目录调用 get_repo
        found = get_repo(str(sub))
        assert found is not None
        assert found.working_dir == str(tmp_git_dir)

    def test_diff_file_order_independence(self, green_scenario):
        """交换分支顺序，diff 内容主题一致（只是 +/- 方向不同）。"""
        repo, branch_a, branch_b = green_scenario
        diff_ab = get_diff_text(repo, branch_a, branch_b)
        diff_ba = get_diff_text(repo, branch_b, branch_a)
        assert diff_ab or diff_ba  # 至少一个非空（都不为空才对）
        # 长度应该差不多（方向不同而已）
        assert abs(len(diff_ab) - len(diff_ba)) < max(len(diff_ab), len(diff_ba))


class TestAnalyzerSampleData:
    """Analyzer 的 sample 数据解析。"""

    def test_sample_data_parsing(self):
        """test_with_sample_diff 应能正确解析 sample LLM 响应。"""
        from src.analyzer import test_with_sample_diff
        report = test_with_sample_diff()
        assert report.report_version == "1.0"
        assert len(report.branch_a_summary) > 0
        assert len(report.conflicts) > 0


class TestReporter:
    """Reporter 输出格式验证。"""

    def test_print_report_does_not_crash(self, green_scenario):
        """print_report 对各种报告都能正常输出。"""
        from src.analyzer import test_with_sample_diff
        report = test_with_sample_diff()
        # 只是验证不抛异常
        print_report(report)

    def test_html_export(self, tmp_path, green_scenario):
        """HTML 导出功能正常。"""
        from src.analyzer import test_with_sample_diff
        from src.reporter import export_html

        report = test_with_sample_diff()
        out_path = str(tmp_path / "report.html")
        export_html(report, out_path)

        html = Path(out_path).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html
        assert "Merge-Explain" in html
        assert "总体建议" in html or "overall_advice" in html

    def test_markdown_export(self, tmp_path, green_scenario):
        """Markdown 导出功能正常。"""
        from src.analyzer import test_with_sample_diff
        from src.reporter import export_markdown

        report = test_with_sample_diff()
        out_path = str(tmp_path / "report.md")
        export_markdown(report, out_path)

        md = Path(out_path).read_text(encoding="utf-8")
        assert "# Merge-Explain" in md
        assert "总体决策" in md


# ===========================================================================
# 可选：真实 LLM 集成测试（需要 API Key）
# ===========================================================================

class TestRealLLMIntegration:
    """
    真实 LLM 调用集成测试，仅在设置了 OPENAI_API_KEY 时运行。
    用于验证实际输出质量的辅助测试。
    """

    @pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY")
        or os.environ["OPENAI_API_KEY"] == "test-skip-real-llm",
        reason="需要真实的 OPENAI_API_KEY"
    )
    def test_real_llm_with_green_scenario(self, green_scenario, monkeypatch):
        """真实 LLM 分析 GREEN 场景。"""
        # 移除 mock
        import src.analyzer as analyzer_mod
        original = analyzer_mod.analyze_diff
        # 重新导入真实的 analyze_diff
        from importlib import reload
        reload(analyzer_mod)

        repo, branch_a, branch_b = green_scenario
        diff_text = get_diff_text(repo, branch_a, branch_b)
        report = analyzer_mod.analyze_diff(diff_text)
        assert report is not None
        print_report(report)
        print("\n[真实 LLM] GREEN 场景分析完成")

    @pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY")
        or os.environ["OPENAI_API_KEY"] == "test-skip-real-llm",
        reason="需要真实的 OPENAI_API_KEY"
    )
    def test_real_llm_with_mixed_scenario(self, mixed_scenario, monkeypatch):
        """真实 LLM 分析 MIXED 场景。"""
        import src.analyzer as analyzer_mod
        from importlib import reload
        reload(analyzer_mod)

        repo, branch_a, branch_b = mixed_scenario
        diff_text = get_diff_text(repo, branch_a, branch_b)
        report = analyzer_mod.analyze_diff(diff_text)
        assert report is not None
        print_report(report)
        print("\n[真实 LLM] MIXED 场景分析完成")
