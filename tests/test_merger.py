"""
测试冲突解析、替换、语法检查。
"""
import os
import tempfile
from pathlib import Path

import pytest

from src.merger import (
    parse_conflict_markers,
    replace_conflict_in_file,
    _syntax_check,
)
from src.models import ConflictRegion, RiskLevel


# ---------------------------------------------------------------------------
# 测试数据：含冲突标记的文件
# ---------------------------------------------------------------------------

SIMPLE_CONFLICT_FILE = """
def hello():
<<<<<<< HEAD
    print("hello from branch B")
=======
    print("hello from branch A")
>>>>>>> branch_a
    return True
""".lstrip()

DIFF3_CONFLICT_FILE = """
def add(a, b):
<<<<<<< HEAD
    return a + b + 1
||||||| base
    return a + b
=======
    return a * b
>>>>>>> branch_a
""".lstrip()

MULTI_CONFLICT_FILE = """
first = 1

<<<<<<< HEAD
second = 2
=======
second = 3
>>>>>>> branch_a

third = 3

<<<<<<< HEAD
fourth = 4
=======
fourth = 5
>>>>>>> branch_a

fifth = 5
""".lstrip()


# ---------------------------------------------------------------------------
# parse_conflict_markers
# ---------------------------------------------------------------------------

class TestParseConflictMarkers:
    def test_simple_conflict(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(SIMPLE_CONFLICT_FILE)
        regions = parse_conflict_markers(str(f))
        assert len(regions) == 1
        r = regions[0]
        assert "branch B" in r.branch_b_version
        assert "branch A" in r.branch_a_version
        assert r.base_version == ""
        assert "return True" in r.context_after
        assert "def hello()" in r.context_before

    def test_diff3_conflict(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(DIFF3_CONFLICT_FILE)
        regions = parse_conflict_markers(str(f))
        assert len(regions) == 1
        r = regions[0]
        assert "a + b" in r.base_version       # 共同祖先
        assert "a + b + 1" in r.branch_b_version  # HEAD
        assert "a * b" in r.branch_a_version    # branch_a

    def test_multi_conflict(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(MULTI_CONFLICT_FILE)
        regions = parse_conflict_markers(str(f))
        assert len(regions) == 2
        assert "second = 2" in regions[0].branch_b_version
        assert "second = 3" in regions[0].branch_a_version
        assert "fourth = 4" in regions[1].branch_b_version
        assert "fourth = 5" in regions[1].branch_a_version

    def test_no_conflict(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\ny = 2\n")
        regions = parse_conflict_markers(str(f))
        assert len(regions) == 0

    def test_nonexistent_file(self):
        regions = parse_conflict_markers("/nonexistent/file.py")
        assert regions == []


# ---------------------------------------------------------------------------
# replace_conflict_in_file
# ---------------------------------------------------------------------------

class TestReplaceConflict:
    def test_replace_simple(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(SIMPLE_CONFLICT_FILE)

        regions = parse_conflict_markers(str(f))
        assert len(regions) == 1

        region = regions[0]
        resolved = '    print("hello from both branches!")'

        ok, msg = replace_conflict_in_file(str(f), region, resolved)
        assert ok, f"替换失败: {msg}"

        result = f.read_text()
        assert "hello from both branches!" in result
        assert "<<<<<<<" not in result
        assert ">>>>>>>" not in result
        assert "=======" not in result

    def test_replace_multi(self, tmp_path):
        """多冲突文件，只替换第一个，第二个保留。"""
        f = tmp_path / "test.py"
        f.write_text(MULTI_CONFLICT_FILE)

        regions = parse_conflict_markers(str(f))
        assert len(regions) == 2

        region0 = regions[0]
        ok, msg = replace_conflict_in_file(str(f), region0, "second = 42")
        assert ok, f"替换失败: {msg}"

        result = f.read_text()
        assert "second = 42" in result
        # 第二个冲突应仍在
        assert "<<<<<<<" in result
        assert "fourth" in result


# ---------------------------------------------------------------------------
# _syntax_check
# ---------------------------------------------------------------------------

class TestSyntaxCheck:
    def test_valid_python(self, tmp_path):
        f = tmp_path / "ok.py"
        f.write_text("x = 1\ny = 2\n")
        ok, msg = _syntax_check(str(f))
        assert ok
        assert msg == ""

    def test_invalid_python(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("x = 1\ny = \n")
        ok, msg = _syntax_check(str(f))
        assert not ok

    def test_non_python(self, tmp_path):
        f = tmp_path / "readme.md"
        f.write_text("# Hello\n")
        ok, msg = _syntax_check(str(f))
        assert ok
