from pydantic import BaseModel
from enum import Enum
from typing import List, Optional


class RiskLevel(str, Enum):
    GREEN = "green"   # 伪冲突，逻辑无交集，可自动合
    YELLOW = "yellow" # 逻辑改动重叠，但未冲突，建议人工看
    RED = "red"       # 真冲突，逻辑互斥，必须人工决策


class ChangeItem(BaseModel):
    file_path: str
    function_name: str
    change_desc: str


class ConflictPoint(BaseModel):
    file_path: str
    risk: RiskLevel
    branch_a_action: str
    branch_b_action: str
    suggestion: str
    code_snippet: Optional[str] = None


class MergeReport(BaseModel):
    report_version: str = "1.0"
    branch_a_summary: List[ChangeItem]
    branch_b_summary: List[ChangeItem]
    conflicts: List[ConflictPoint]
    overall_advice: str
    reasoning: str


# ===================== resolve 模型 =====================

class ConflictRegion(BaseModel):
    """从 <<<<<<< 标记中解析出的一个冲突块"""
    file_path: str
    region_id: str              # 唯一标识，用于定位
    base_version: str           # 共同祖先版本（diff3 格式）
    branch_a_version: str       # <<<<<<< 到 ======= 之间的代码
    branch_b_version: str       # ======= 到 >>>>>>> 之间的代码
    context_before: str         # 冲突前的上下文
    context_after: str          # 冲突后的上下文
    suggestion: Optional[str] = None


class ResolveChange(BaseModel):
    """单次冲突解决的记录"""
    file_path: str
    region_id: str
    resolved_code: str
    explanation: str
    risk: RiskLevel


class ResolveReport(BaseModel):
    """resolve 命令的输出报告"""
    report_version: str = "1.0"
    branch_a: str
    branch_b: str
    changes: List[ResolveChange]
    skipped: List[ConflictRegion]
    total_conflicts: int
    resolved_count: int
    skipped_count: int
    status: str   # "all_resolved" | "partial" | "failed"
