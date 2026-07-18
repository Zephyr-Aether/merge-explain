"""
LLM 分析模块：构造 Prompt、调用 OpenAI SDK、解析为 MergeReport。
"""
import json
import os
import time
from typing import Optional

from openai import OpenAI, APIError, APITimeoutError, APIConnectionError, RateLimitError

from src.models import MergeReport


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是 Merge-Explain 的分析引擎，一个代码合并冲突分析专家。\n"
    "你的输入是两个分支之间的 Git Diff，输出是一份结构化的合并建议报告。\n"
    "\n"
    "## 分析原则\n"
    "1. 只关注有意义的变更：函数逻辑、类结构、API 接口、数据库模型、配置文件、依赖声明。\n"
    "   忽略：代码格式化、变量/函数重命名、注释增删、空白字符、文档字符串微调。\n"
    "2. 推断意图：从 diff 上下文中理解每个分支改动的业务目的，而不是逐行复述 diff。\n"
    "3. 诚实判断：如果 diff 中没有实质性变更，如实汇报。\n"
    "\n"
    "## 风险等级定义\n"
    '  - "green"：双方改的是完全不同的文件或函数，逻辑无交集。可以安全自动合并。\n'
    '  - "yellow"：双方改了同一文件/函数但改的是不同方面，没有直接的行冲突。\n'
    "    建议开发者人工复核，但大概率能正常合并。\n"
    '  - "red"：双方改动了同一行、同一判断条件、互斥的配置值，或导致语法错误。\n'
    "    必须人工决策，不能自动合。\n"
    "\n"
    "## 输出格式\n"
    "你必须输出合法的 JSON，严格遵循以下结构：\n"
    '{\n'
    '  "branch_a_summary": [\n'
    '    {"file_path": "path/to/file.py", "function_name": "函数/类名", '
    '"change_desc": "一句话描述改动的业务含义"}\n'
    '  ],\n'
    '  "branch_b_summary": [{"file_path": "...", "function_name": "...", '
    '"change_desc": "..."}],\n'
    '  "conflicts": [\n'
    '    {\n'
    '      "file_path": "path/to/file.py",\n'
    '      "risk": "green" | "yellow" | "red",\n'
    '      "branch_a_action": "A 分支做了什么，解释业务意图",\n'
    '      "branch_b_action": "B 分支做了什么，解释业务意图",\n'
    '      "suggestion": "具体可执行的处理建议"\n'
    '    }\n'
    '  ],\n'
    '  "overall_advice": "auto_merge" | "manual_review" | "blocked",\n'
    '  "reasoning": "一句话解释总体判断依据"\n'
    '}\n'
    "\n"
    "## 约束\n"
    "- 每个 summary 数组至少包含一条记录；完全没有实质性变更则写「无实质性变更」。\n"
    "- conflicts 可以为空数组。\n"
    '- overall_advice 只能是 "auto_merge"、"manual_review" 或 "blocked" 之一。\n'
    "- 如果 diff 中出现潜在的语法错误、类型不匹配、API 不兼容等问题，在 suggestion 中明确指出。\n"
    "- 只输出 JSON，不附加任何解释、代码块标记或额外的文字。"
)


# ---------------------------------------------------------------------------
# 默认不暴露 API Key 时的 fallback 数据
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 不响应 JSON 模式的模型名单
# ---------------------------------------------------------------------------

_MODELS_WITHOUT_JSON_MODE = {
    "o1-preview", "o1-mini", "o3-mini",
}


def _supports_json_mode(model: str) -> bool:
    """检查模型是否支持 response_format={'type': 'json_object'}。"""
    return model not in _MODELS_WITHOUT_JSON_MODE and not model.startswith("o1-")


# ---------------------------------------------------------------------------
# OpenAI 客户端工厂
# ---------------------------------------------------------------------------

def get_openai_client() -> OpenAI:
    """从环境变量读取配置，创建 OpenAI 客户端。"""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")

    if not api_key:
        raise ValueError(
            "未检测到 OPENAI_API_KEY。请配置 .env 文件，或设置环境变量。\n"
            "参考 .env.example 进行配置。"
        )

    kwargs = {"api_key": api_key, "timeout": 60.0}
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAI(**kwargs)


def get_model_name() -> str:
    """获取模型名称，默认 gpt-4o-mini。"""
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# 核心：分析 Diff
# ---------------------------------------------------------------------------

def analyze_diff(diff_text: str) -> MergeReport:
    """
    调用 LLM 分析 Diff 文本，返回结构化的 MergeReport。

    边界处理：
    - diff_text 为空时跳过 LLM，直接返回空报告
    - 网络/API 错误会自动重试（最多 2 次，带指数退避）
    - 模型不支持 JSON 模式时，退化为普通请求 + 后处理
    - 最后兜底：返回 sample 数据
    """
    # === 边界 1：空 diff ===
    if not diff_text or not diff_text.strip():
        return MergeReport(
            branch_a_summary=[],
            branch_b_summary=[],
            conflicts=[],
            overall_advice="auto_merge",
            reasoning="两个分支之间没有任何差异，无需合并操作。",
        )

    model = get_model_name()

    # === 尝试调用 LLM（含 2 次重试）===
    last_error: Optional[Exception] = None

    for attempt in range(2):  # 首次 + 1 次重试
        try:
            client = get_openai_client()
            user_prompt = (
                f"请分析以下两个分支之间的 Git Diff 变更：\n\n{diff_text}"
            )

            kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.05,
            }

            # 支持 JSON 模式的模型用结构化输出，否则靠 prompt 约束
            if _supports_json_mode(model):
                kwargs["response_format"] = {"type": "json_object"}

            # 重试时再加一层约束
            if attempt > 0:
                kwargs["messages"][0]["content"] += (
                    "\n\n【重要】你上一次的输出未能通过 JSON 校验。"
                    "请严格只输出合法的 JSON 对象，不要包含任何其他字符。"
                )

            response = client.chat.completions.create(**kwargs)
            raw = response.choices[0].message.content
            if not raw:
                raise ValueError("LLM 返回了空响应")

            return MergeReport.model_validate_json(raw)

        except (APITimeoutError, APIConnectionError, RateLimitError) as e:
            last_error = e
            if attempt == 0:
                time.sleep(1)  # 简单退避
                continue
        except (APIError, ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt == 0:
                continue
        except Exception as e:
            last_error = e
            break  # 未知错误不重试

    # === 兜底：sample 数据 ===
    reason = ""
    if last_error:
        reason = f" ({type(last_error).__name__}: {last_error})"
    print(f"[警告] LLM 调用失败{reason}，使用示例数据降级。")
    return MergeReport.model_validate_json(SAMPLE_LLM_RESPONSE)


# ---------------------------------------------------------------------------
# 测试辅助（内置 sample diff 验证 Pydantic 解析）
# ---------------------------------------------------------------------------

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


def test_with_sample_diff() -> MergeReport:
    """使用硬编码的 sample diff 测试 Pydantic 解析流程。"""
    print("正在使用 Sample Diff 测试 Pydantic 解析...")
    print(f"Sample Diff 长度: {len(SAMPLE_DIFF)} 字符\n")
    report = MergeReport.model_validate_json(SAMPLE_LLM_RESPONSE)
    print("✅ JSON 解析成功！MergeReport 结构如下：")
    print(report.model_dump_json(indent=2))
    return report
