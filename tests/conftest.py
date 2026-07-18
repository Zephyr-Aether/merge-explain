"""
pytest 全局 fixtures：临时 Git 仓库、Mock LLM。
"""
import os
import shutil
from pathlib import Path
from typing import Generator, Tuple

import pytest
from git import Repo

# 加载 .env（如果有），再设置默认值防止真实调用
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", "test-skip-real-llm")


# ---------------------------------------------------------------------------
# 临时 Git 仓库工厂
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_git_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """创建一个干净的临时目录作为 Git 仓库根目录。"""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    yield repo_dir
    # cleanup 由 tmp_path 自动处理


def _init_repo(work_dir: Path) -> Repo:
    """初始化 Git 仓库，配置 user。"""
    repo = Repo.init(work_dir)
    repo.git.config("user.name", "test")
    repo.git.config("user.email", "test@test.com")
    return repo


def _commit(repo: Repo, message: str) -> None:
    """添加所有变更并提交。"""
    repo.git.add("--all")
    repo.index.commit(message)


def _checkout_b(repo: Repo, branch_name: str) -> None:
    """从当前 HEAD 创建并切换到新分支。"""
    repo.git.checkout("HEAD", b=branch_name)


def _write(repo: Repo, file_path: str, content: str) -> None:
    """写文件。"""
    full_path = Path(repo.working_dir) / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)


def _read(repo: Repo, file_path: str) -> str:
    """读文件。"""
    return (Path(repo.working_dir) / file_path).read_text()


# ---------------------------------------------------------------------------
# 场景 1：GREEN — 不同函数改动
# ---------------------------------------------------------------------------

@pytest.fixture
def green_scenario(tmp_git_dir: Path) -> Tuple[Repo, str, str]:
    """
    Base: calculator.py 有 add() 和 multiply()
    Branch A (feature/logging): 给 add() 加日志
    Branch B (feature/types):   给 multiply() 加类型注解
    → 互不干扰，预期 GREEN
    """
    repo = _init_repo(tmp_git_dir)
    _write(repo, "calculator.py",
           "def add(a, b):\n    return a + b\n\n"
           "def multiply(a, b):\n    return a * b\n")
    _commit(repo, "initial")

    # Branch A
    _checkout_b(repo, "feature/logging")
    _write(repo, "calculator.py",
           "import logging\nlogger = logging.getLogger(__name__)\n\n"
           "def add(a, b):\n    logger.debug(f'Adding {a} + {b}')\n    return a + b\n\n"
           "def multiply(a, b):\n    return a * b\n")
    _commit(repo, "add logging to add()")

    # Branch B
    repo.git.checkout("main")
    _checkout_b(repo, "feature/types")
    _write(repo, "calculator.py",
           "def add(a, b):\n    return a + b\n\n"
           "def multiply(a: int, b: int) -> int:\n    return a * b\n")
    _commit(repo, "add type hints to multiply()")

    repo.git.checkout("main")
    return repo, "feature/logging", "feature/types"


# ---------------------------------------------------------------------------
# 场景 2：YELLOW — 同一函数不同方面
# ---------------------------------------------------------------------------

@pytest.fixture
def yellow_scenario(tmp_git_dir: Path) -> Tuple[Repo, str, str]:
    """
    Base: user_service.py 有 get_user()
    Branch A: 加参数校验
    Branch B: 加缓存装饰器
    → 同一函数逻辑重叠，但不互斥
    """
    repo = _init_repo(tmp_git_dir)
    _write(repo, "user_service.py",
           "def get_user(user_id: int):\n"
           "    return {'id': user_id, 'name': 'Alice'}\n")
    _commit(repo, "initial")

    # Branch A
    _checkout_b(repo, "feature/validation")
    _write(repo, "user_service.py",
           "def get_user(user_id: int):\n"
           "    if not isinstance(user_id, int) or user_id <= 0:\n"
           "        raise ValueError('Invalid user_id')\n"
           "    return {'id': user_id, 'name': 'Alice'}\n")
    _commit(repo, "add validation")

    # Branch B
    repo.git.checkout("main")
    _checkout_b(repo, "feature/cache")
    _write(repo, "user_service.py",
           "from functools import lru_cache\n\n"
           "@lru_cache(maxsize=128)\n"
           "def get_user(user_id: int):\n"
           "    return {'id': user_id, 'name': 'Alice'}\n")
    _commit(repo, "add caching")

    repo.git.checkout("main")
    return repo, "feature/validation", "feature/cache"


# ---------------------------------------------------------------------------
# 场景 3：RED — 同一行互斥改动
# ---------------------------------------------------------------------------

@pytest.fixture
def red_scenario(tmp_git_dir: Path) -> Tuple[Repo, str, str]:
    """
    Base: config.py  TIMEOUT = 30
    Branch A: TIMEOUT = 60
    Branch B: TIMEOUT = 120
    → 真冲突
    """
    repo = _init_repo(tmp_git_dir)
    _write(repo, "config.py",
           "# App config\nTIMEOUT = 30\nMAX_RETRIES = 3\n")
    _commit(repo, "initial")

    # Branch A
    _checkout_b(repo, "feature/timeout-60")
    _write(repo, "config.py",
           "# App config\nTIMEOUT = 60\nMAX_RETRIES = 3\n")
    _commit(repo, "change timeout to 60")

    # Branch B
    repo.git.checkout("main")
    _checkout_b(repo, "feature/timeout-120")
    _write(repo, "config.py",
           "# App config\nTIMEOUT = 120\nMAX_RETRIES = 3\n")
    _commit(repo, "change timeout to 120")

    repo.git.checkout("main")
    return repo, "feature/timeout-60", "feature/timeout-120"


# ---------------------------------------------------------------------------
# 场景 4：MIXED — 多文件混合
# ---------------------------------------------------------------------------

@pytest.fixture
def mixed_scenario(tmp_git_dir: Path) -> Tuple[Repo, str, str]:
    """
    同时包含三种风险等级的场景。
    文件:
      - payment.py: 两个分支改了同一个函数的不同部位 (YELLOW)
      - auth.py:    两个分支改了互斥的逻辑 (RED)
      - logger.py:  只有 Branch A 改了 (GREEN)
    """
    repo = _init_repo(tmp_git_dir)
    _write(repo, "payment.py",
           "def process_payment(user_id, amount):\n"
           "    token = get_token(user_id)\n"
           "    return charge(token, amount)\n")
    _write(repo, "auth.py",
           "AUTH_METHOD = 'jwt'\n"
           "def verify(request):\n"
           "    return request.headers.get('Authorization')\n")
    _write(repo, "logger.py",
           "def log(msg):\n    print(msg)\n")
    _commit(repo, "initial")

    # Branch A
    _checkout_b(repo, "feature/payment-v2")
    _write(repo, "payment.py",
           "def process_payment(user_id, amount):\n"
           "    token = get_token(user_id)\n"
           "    log_audit(user_id, amount)\n"
           "    return charge(token, amount)\n")
    _write(repo, "auth.py",
           "AUTH_METHOD = 'session'\n"
           "def verify(request):\n"
           "    return request.cookies.get('session_id')\n")
    _write(repo, "logger.py",
           "import logging\nlogger = logging.getLogger(__name__)\n"
           "def log(msg):\n    logger.info(msg)\n")
    _commit(repo, "payment audit + session auth + logger upgrade")

    # Branch B
    repo.git.checkout("main")
    _checkout_b(repo, "feature/async-payment")
    _write(repo, "payment.py",
           "async def process_payment(user_id, amount):\n"
           "    token = get_token(user_id)\n"
           "    return await charge_async(token, amount)\n")
    _write(repo, "auth.py",
           "AUTH_METHOD = 'oauth2'\n"
           "def verify(request):\n"
           "    return request.headers.get('OAuth2-Token')\n")
    _commit(repo, "async payment + oauth2 auth")

    repo.git.checkout("main")
    return repo, "feature/payment-v2", "feature/async-payment"


# ---------------------------------------------------------------------------
# 场景 5：大 Diff（测试截断逻辑）
# ---------------------------------------------------------------------------

@pytest.fixture
def large_diff_scenario(tmp_git_dir: Path) -> Tuple[Repo, str, str]:
    """
    生成超过 5000 token 的 Diff，测试自动截断逻辑。
    通过在一个大文件里批量插入大量行来制造大 Diff。
    """
    repo = _init_repo(tmp_git_dir)
    # 初始文件：200 行，包含函数定义和大片数据
    lines = ["def process(data):", "    result = []", "    for i in data:", "        result.append(i * 2)", "    return result", ""]
    lines += [f"item_{i} = {i}" for i in range(200)]
    _write(repo, "bigfile.py", "\n".join(lines) + "\n")
    _commit(repo, "initial")

    # Branch A: 插入大量代码（制造大 diff）
    _checkout_b(repo, "feature/big-a")
    big_lines = [f"item_{i} = {i}" for i in range(500)]
    # 添加新的函数 + 大量数据
    extra_a = (
        "def process_v2(data):\n"
        "    return [x * 3 for x in data]\n"
        "\n"
    )
    extra_a += "\n".join(f"new_a_{i} = A{i}" for i in range(1500))
    extra_a += "\n"
    _write(repo, "bigfile.py",
           "\n".join(big_lines) + "\n" +
           extra_a)
    _commit(repo, "big change A")

    # Branch B: 添加另一个函数 + 大量数据
    repo.git.checkout("main")
    _checkout_b(repo, "feature/big-b")
    extra_b = (
        "def process_v3(data):\n"
        "    return {x: x ** 2 for x in data}\n"
        "\n"
    )
    extra_b += "\n".join(f"new_b_{i} = B{i}" for i in range(1500))
    extra_b += "\n"
    _write(repo, "bigfile.py",
           "\n".join(f"item_{i} = {i}" for i in range(50, 250)) +
           "\n" + extra_b)
    _commit(repo, "big change B")

    repo.git.checkout("main")
    return repo, "feature/big-a", "feature/big-b"


# ---------------------------------------------------------------------------
# 场景 6：空 Diff（无变更）
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_scenario(tmp_git_dir: Path) -> Tuple[Repo, str, str]:
    """两个分支完全相同，预期空 Diff。"""
    repo = _init_repo(tmp_git_dir)
    _write(repo, "readme.md", "# Project\n")
    _commit(repo, "initial")

    repo.git.branch("feature/no-change")
    return repo, "main", "feature/no-change"


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_openai(monkeypatch):
    """
    自动 mock 掉 OpenAI 调用，防止真实请求。
    对所有测试生效；需要真实 LLM 的测试可以手动 override。
    """
    import src.analyzer

    original_analyze = src.analyzer.analyze_diff

    def mock_analyze(diff_text: str):
        """绕过 LLM，直接返回基于 sample 数据的 MergeReport。"""
        from src.models import MergeReport
        return MergeReport.model_validate_json(
            src.analyzer.SAMPLE_LLM_RESPONSE
        )

    monkeypatch.setattr(src.analyzer, "analyze_diff", mock_analyze)
    yield
    monkeypatch.setattr(src.analyzer, "analyze_diff", original_analyze)
