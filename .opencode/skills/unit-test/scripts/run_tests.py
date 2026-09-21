"""
一键运行后端单元测试并生成 HTML 报告。

用法（在 backend 目录下执行）:
    C:\\Users\\13445\\miniconda3\\python.exe scripts\\run_tests.py

产物:
    reports/pytest_report.html        测试结果网页报告
    reports/coverage_html/index.html  代码覆盖率网页报告
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

def _is_backend_dir(d: Path) -> bool:
    """判断目录是否为后端根目录（含 app/ 且有 run.py 或 .env）"""
    return (d / "app").is_dir() and ((d / "run.py").exists() or (d / ".env").exists())


def find_backend_dir() -> Path:
    """自动定位后端根目录：优先当前目录，其次沿脚本祖先目录向上查找"""
    cwd = Path.cwd()
    if _is_backend_dir(cwd):
        return cwd
    p = Path(__file__).resolve().parent
    for _ in range(8):
        if _is_backend_dir(p):
            return p
        p = p.parent
    raise SystemExit("ERROR: Cannot locate backend directory (need app/ + run.py or .env)")


BACKEND_DIR = find_backend_dir()
PYTHON = r"C:\Users\13445\miniconda3\python.exe"

REQUIRED_PACKAGES = [
    "pytest", "pytest-asyncio", "pytest-cov", "pytest-html", "pytest-mock",
]

CONFTEST_CONTENT = r'''"""
pytest 全局配置：独立测试数据库 + 常用 fixtures
注意: DATABASE_URL 环境变量必须在导入 app.* 之前设置。
"""
import os
import uuid

# 使用独立测试数据库，绝不触碰生产 bankkb.db
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./tests/test_bankkb.db"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import init_db, async_session_factory
from app.main import app
from app.models.user import User
from app.core.security import get_password_hash

TEST_PASSWORD = "TestPass#123456"
ADMIN_USERNAME = "ut_admin"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_db():
    """初始化测试数据库并创建种子管理员账号（幂等）"""
    await init_db()
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.username == ADMIN_USERNAME))
        if not result.scalar_one_or_none():
            admin = User(
                username=ADMIN_USERNAME,
                email="ut_admin@test.com",
                password_hash=get_password_hash(TEST_PASSWORD),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            await db.commit()
    yield


@pytest_asyncio.fixture
async def client():
    """HTTP 客户端（ASGI in-memory，不占端口）"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> str:
    """管理员 token"""
    return await _login(client, ADMIN_USERNAME, TEST_PASSWORD)


@pytest_asyncio.fixture
async def user_token_factory(client: AsyncClient):
    """注册并登录一个全新普通用户，返回其 token"""
    async def factory() -> str:
        username = f"ut_user_{uuid.uuid4().hex[:8]}"
        resp = await client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@test.com",
                "password": TEST_PASSWORD,
            },
        )
        assert resp.status_code in (200, 201), resp.text
        return await _login(client, username, TEST_PASSWORD)
    return factory
'''

PYTEST_INI_CONTENT = """[pytest]
testpaths = tests
asyncio_mode = auto
filterwarnings =
    ignore::DeprecationWarning
"""


def run(cmd: list) -> None:
    """运行命令并透传输出"""
    print(">", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def ensure_packages() -> None:
    """检查并安装缺失的测试依赖"""
    print("==> 检查测试依赖...")
    installed = subprocess.run(
        [PYTHON, "-m", "pip", "list", "--format=freeze"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.lower()
    to_install = [p for p in REQUIRED_PACKAGES if p.lower() not in installed]
    if to_install:
        print(f"==> 安装缺失依赖: {to_install}")
        run([PYTHON, "-m", "pip", "install", *to_install])
    else:
        print("    依赖齐全")


def ensure_skeleton() -> None:
    """确保 tests 目录骨架存在（conftest.py / pytest.ini）"""
    (BACKEND_DIR / "tests").mkdir(exist_ok=True)
    conftest = BACKEND_DIR / "tests" / "conftest.py"
    if not conftest.exists():
        conftest.write_text(CONFTEST_CONTENT, encoding="utf-8")
        print("==> 生成 tests/conftest.py")
    ini = BACKEND_DIR / "pytest.ini"
    if not ini.exists():
        ini.write_text(PYTEST_INI_CONTENT, encoding="utf-8")
        print("==> 生成 pytest.ini")


def main() -> None:
    os.chdir(BACKEND_DIR)
    ensure_packages()
    ensure_skeleton()

    # 清理旧的测试数据库与报告
    old_db = BACKEND_DIR / "tests" / "test_bankkb.db"
    if old_db.exists():
        old_db.unlink()
    reports = BACKEND_DIR / "reports"
    if reports.exists():
        shutil.rmtree(reports)
    reports.mkdir(exist_ok=True)

    print("==> 运行 pytest (覆盖率 + HTML 报告)...")
    run([
        PYTHON, "-m", "pytest", "tests/", "-v",
        "--cov=app",
        "--cov-report=term",
        f"--cov-report=html:{reports / 'coverage_html'}",
        f"--html={reports / 'pytest_report.html'}",
        "--self-contained-html",
    ])

    print()
    print("=" * 60)
    print("报告已生成：")
    print(f"  测试报告   : {reports / 'pytest_report.html'}")
    print(f"  覆盖率报告 : {reports / 'coverage_html' / 'index.html'}")
    print("用浏览器打开即可查看。")
    print("=" * 60)


if __name__ == "__main__":
    main()