from pydantic import BaseModel
from enum import Enum
from typing import List, Optional


class RiskLevel(str, Enum):
    GREEN = "green"   # 伪冲突，逻辑无交集，可自动合
    YELLOW = "yellow" # 逻辑改动重叠，但未冲突，建议人工看
    RED = "red"       # 真冲突，逻辑互斥，必须人工决策


class ChangeItem(BaseModel):
    file_path: str
    function_name: str  # 改动涉及的具体函数/类名
    change_desc: str    # 自然语言描述（例如：把校验逻辑从JWT改为了Session）


class ConflictPoint(BaseModel):
    file_path: str
    risk: RiskLevel
    branch_a_action: str  # A分支在这个冲突点干了什么
    branch_b_action: str  # B分支在这个冲突点干了什么
    suggestion: str       # AI给出的具体处理建议


class MergeReport(BaseModel):
    # 报告版本
    report_version: str = "1.0"

    # 1. 高层摘要
    branch_a_summary: List[ChangeItem]
    branch_b_summary: List[ChangeItem]

    # 2. 冲突详情
    conflicts: List[ConflictPoint]

    # 3. 总体决策
    overall_advice: str  # "auto_merge" | "manual_review" | "blocked"
    reasoning: str       # 一句话解释为什么给出这个建议
