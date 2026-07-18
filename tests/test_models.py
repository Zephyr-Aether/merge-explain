"""
测试 Pydantic 数据模型的解析和验证。
"""
import json

import pytest
from pydantic import ValidationError

from src.models import RiskLevel, ChangeItem, ConflictPoint, MergeReport


class TestRiskLevel:
    def test_valid_values(self):
        assert RiskLevel.GREEN.value == "green"
        assert RiskLevel.YELLOW.value == "yellow"
        assert RiskLevel.RED.value == "red"

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            RiskLevel("blue")


class TestChangeItem:
    def test_full_construction(self):
        item = ChangeItem(
            file_path="src/main.py",
            function_name="run",
            change_desc="添加了日志",
        )
        assert item.file_path == "src/main.py"
        assert item.function_name == "run"
        assert item.change_desc == "添加了日志"

    def test_missing_field(self):
        with pytest.raises(ValidationError):
            ChangeItem(file_path="x.py", function_name="f")  # 缺少 change_desc


class TestConflictPoint:
    def test_full_construction(self):
        cp = ConflictPoint(
            file_path="app.py",
            risk=RiskLevel.RED,
            branch_a_action="删除旧接口",
            branch_b_action="重命名参数",
            suggestion="保留 B 的命名",
        )
        assert cp.risk == RiskLevel.RED
        assert cp.suggestion == "保留 B 的命名"

    def test_json_roundtrip(self):
        cp = ConflictPoint(
            file_path="x.py", risk=RiskLevel.YELLOW,
            branch_a_action="a", branch_b_action="b", suggestion="s",
        )
        data = json.loads(cp.model_dump_json())
        restored = ConflictPoint.model_validate(data)
        assert restored.risk == RiskLevel.YELLOW


class TestMergeReport:
    def test_full_report(self):
        report = MergeReport(
            branch_a_summary=[
                ChangeItem(file_path="a.py", function_name="f1", change_desc="改 A"),
            ],
            branch_b_summary=[
                ChangeItem(file_path="b.py", function_name="f2", change_desc="改 B"),
            ],
            conflicts=[
                ConflictPoint(
                    file_path="c.py", risk=RiskLevel.GREEN,
                    branch_a_action="a", branch_b_action="b", suggestion="s",
                ),
            ],
            overall_advice="auto_merge",
            reasoning="无冲突",
        )
        assert report.report_version == "1.0"  # 默认值
        assert report.overall_advice == "auto_merge"
        assert len(report.conflicts) == 1

    def test_model_validate_json(self):
        raw = """{
            "branch_a_summary": [
                {"file_path": "pay.py", "function_name": "pay", "change_desc": "改支付"}
            ],
            "branch_b_summary": [],
            "conflicts": [
                {
                    "file_path": "pay.py",
                    "risk": "yellow",
                    "branch_a_action": "加校验",
                    "branch_b_action": "改签名",
                    "suggestion": "合"
                }
            ],
            "overall_advice": "manual_review",
            "reasoning": "涉及支付"
        }"""
        report = MergeReport.model_validate_json(raw)
        assert report.conflicts[0].risk == RiskLevel.YELLOW
        assert report.branch_a_summary[0].function_name == "pay"

    def test_invalid_risk(self):
        raw = """{
            "branch_a_summary": [],
            "branch_b_summary": [],
            "conflicts": [{"file_path": "x.py", "risk": "purple",
                           "branch_a_action": "a", "branch_b_action": "b",
                           "suggestion": "s"}],
            "overall_advice": "ok",
            "reasoning": "test"
        }"""
        with pytest.raises(ValidationError):
            MergeReport.model_validate_json(raw)

    def test_empty_report(self):
        """全空报告的边界情况。"""
        report = MergeReport(
            branch_a_summary=[],
            branch_b_summary=[],
            conflicts=[],
            overall_advice="auto_merge",
            reasoning="No changes",
        )
        assert len(report.branch_a_summary) == 0
        assert len(report.conflicts) == 0
