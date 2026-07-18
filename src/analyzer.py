"""
LLM 分析模块：构造 Prompt、调用 OpenAI SDK、解析为 MergeReport。
"""
import json
import os
from typing import Optional

from openai import OpenAI

from src.models import MergeReport

# 默认 System Prompt
SYSTEM_PROMPT = (
    "你是一个顶级的代码合并与重构专家。你的任务是基于两个分支的 Git Diff，分析代码变更的业务语义。\n"
    "请忽略代码格式、变量重命名、注释修改等无意义变更。只关注函数逻辑、类结构、API 接口、数据库模型的变化。\n"
    "你必须输出合法的 JSON 格式，并严格遵循以下结构（对应 Pydantic 模型）：\n"
    '{\n'
    '  "branch_a_summary": [{"file_path": "...", "function_name": "...", "change_desc": "..."}],\n'
    '  "branch_b_summary": [{"file_path": "...", "function_name": "...", "change_desc": "..."}],\n'
    '  "conflicts": [\n'
    '    {\n'
    '      "file_path": "...",\n'
    '      "risk": "red/yellow/green",\n'
    '      "branch_a_action": "例如：删除了旧版支付接口",\n'
    '      "branch_b_action": "例如：重命名了支付参数",\n'
    '      "suggestion": "建议保留 B 分支的命名，适配 A 分支的新接口调用"\n'
    '    }\n'
    '  ],\n'
    '  "overall_advice": "manual_review",\n'
    '  "reasoning": "虽然改动集中，但涉及支付核心模块，必须人工确认..."\n'
    '}'
)


def get_openai_client() -> OpenAI:
    """从环境变量读取配置，创建 OpenAI 客户端。"""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")

    if not api_key:
        raise ValueError(
            "未检测到 OPENAI_API_KEY。请配置 .env 文件，或设置环境变量。\n"
            "参考 .env.example 进行配置。"
        )

    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAI(**kwargs)


def get_model_name() -> str:
    """获取模型名称，默认 gpt-4o-mini。"""
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


# 硬编码的示例 Diff（用于 Phase 2 测试 Pydantic 解析）
SAMPLE_DIFF = """diff --git a/payment.py b/payment.py
index abc123..def456 100644
--- a/payment.py
+++ b/payment.py
@@ -10,15 +10,18 @@ def process_payment(user_id, amount):
-    token = jwt.encode({"user": user_id}, SECRET_KEY)
-    result = gateway.charge(token, amount)
+    session = get_active_session(user_id)
+    result = gateway.charge(session.id, amount)
     return result

diff --git a/user.py b/user.py
index 789abc..012def 100644
--- a/user.py
+++ b/user.py
@@ -5,7 +5,7 @@ def get_user_profile(user_id):
-    return db.query(User).filter(User.id == user_id).first()
+    return db.query(User).filter(User.uid == user_id).first()
"""

SAMPLE_LLM_RESPONSE = """{
  "branch_a_summary": [
    {"file_path": "payment.py", "function_name": "process_payment", "change_desc": "将 JWT 认证改为 Session 认证"},
    {"file_path": "user.py", "function_name": "get_user_profile", "change_desc": "将 User.id 改为 User.uid 查询"}
  ],
  "branch_b_summary": [
    {"file_path": "payment.py", "function_name": "process_payment", "change_desc": "重构支付接口为异步调用"},
    {"file_path": "user.py", "function_name": "get_user_profile", "change_desc": "添加了缓存装饰器"}
  ],
  "conflicts": [
    {
      "file_path": "payment.py",
      "risk": "yellow",
      "branch_a_action": "将 JWT 认证改为 Session 认证",
      "branch_b_action": "重构支付接口为异步调用",
      "suggestion": "两个改动位于不同函数，可以同时合并，但需要确认 Session 认证在异步上下文中是否兼容"
    }
  ],
  "overall_advice": "manual_review",
  "reasoning": "虽然有伪冲突，但支付模块影响订单核心链路，建议人工确认"
}"""


def analyze_diff(diff_text: str) -> MergeReport:
    """
    调用 LLM 分析 Diff 文本，返回结构化的 MergeReport。
    如果 LLM 调用失败，则使用 sample 数据回退。
    """
    try:
        client = get_openai_client()
        model = get_model_name()

        user_prompt = f"请分析以下两个分支之间的 Git Diff 变更：\n\n{diff_text}"

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        raw = response.choices[0].message.content
        if not raw:
            raise ValueError("LLM 返回了空响应")

        report = MergeReport.model_validate_json(raw)
        return report

    except Exception as e:
        # 自动重试 1 次
        try:
            client = get_openai_client()
            model = get_model_name()

            retry_prompt = (
                f"请严格只输出合法的 JSON 对象，不要包含任何其他内容。\n\n"
                f"分析以下 Git Diff：\n\n{diff_text}"
            )

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                        + "\n\n重要：只输出 JSON，不要附带任何解释或标记。",
                    },
                    {"role": "user", "content": retry_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            raw = response.choices[0].message.content
            if raw:
                return MergeReport.model_validate_json(raw)
        except Exception:
            pass

        print(f"[警告] LLM 调用失败 ({e})，使用示例数据降级。")
        return MergeReport.model_validate_json(SAMPLE_LLM_RESPONSE)


def test_with_sample_diff() -> MergeReport:
    """使用硬编码的 sample diff 测试 Pydantic 解析流程。"""
    print("正在使用 Sample Diff 测试 Pydantic 解析...")
    print(f"Sample Diff 长度: {len(SAMPLE_DIFF)} 字符\n")
    report = MergeReport.model_validate_json(SAMPLE_LLM_RESPONSE)
    print("✅ JSON 解析成功！MergeReport 结构如下：")
    print(report.model_dump_json(indent=2))
    return report
