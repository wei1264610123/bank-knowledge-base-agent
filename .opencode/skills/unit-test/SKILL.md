---
name: Unit Test
description: 为 Python/FastAPI 后端创建并执行单元测试，生成 HTML 测试报告与覆盖率报告。当用户要求"跑测试/做单元测试/测试报告/验证代码质量"时使用。
---

# 单元测试技能（unit-test）

对 FastAPI 后端执行"编写测试 → 运行测试 → 输出网页报告"的完整流程。
只针对后端 `backend/` 目录，不涉及前端。

## 核心原则（必须遵守）

1. **禁止真实调用外部 API**：测试中所有阿里云百炼调用（LLM 对话、Embedding）必须用 `unittest.mock` / `pytest-mock` 打桩替换，绝不消耗额度、不依赖网络。
2. **使用独立测试数据库**：测试用临时 SQLite 文件（如 `backend/tests/test_bankkb.db`），启动时清理重建，绝不影响生产 `bankkb.db`。
3. **Windows 环境**：Python 使用 `C:\Users\13445\miniconda3\python.exe`（不在 PATH），shell 命令一律用完整路径；控制台输出中文可能乱码，日志尽量用英文。
4. 测试失败要先区分是"测试代码写错"还是"被测代码有 bug"，再决定修复哪边。

## 工作流

### 第1步：环境准备
1. 确认 `backend/` 目录存在并进入该目录。
2. 安装/确认依赖（用当前 Python 完整路径）：
   ```
   C:\Users\13445\miniconda3\python.exe -m pip install pytest pytest-asyncio pytest-cov pytest-html httpx pytest-mock
   ```
3. 确认测试目录骨架存在，没有则从本技能的 `templates/` 复制：
   - `templates/conftest.py` → `backend/tests/conftest.py`
   - `templates/pytest.ini` → `backend/pytest.ini`
   - `templates/test_*.py` → `backend/tests/`（示例测试）

### 第2步：分析被测代码
扫描 `backend/app/`，梳理可测单元：

| 层 | 文件 | 测什么 |
|---|---|---|
| 核心逻辑 | `core/security.py` | 密码哈希/校验、JWT 生成与解析（roundtrip）、token 过期与无效签名 |
| API - 认证 | `api/auth.py` | 注册、重复注册报错、登录、token 错误登录、`/auth/me` 鉴权 |
| API - 聊天 | `api/chat.py` | 建会话/列表/删除、会话归属隔离（A 用户看不到 B 会话）、401 无 token |
| API - 知识库 | `api/knowledge.py` | 管理员权限、文档列表/详情/删除、分类增删 |
| 服务层 | `services/*.py` | 提示词构建、消息历史截断（最近20条）、引用格式化的纯逻辑部分（外部依赖打桩） |
| 模型层 | `models/*.py` | 字段默认值、关系级联（删除文档连带删除分块） |

### 第3步：编写测试
- 按 `templates/` 中示例的写法，每个被测单元一个 `test_*.py` 文件。
- API 测试统一用 `httpx.AsyncClient` + `ASGITransport`，配合 `conftest.py` 的 fixtures。
- 未覆盖的关键路径必须补测，特别是：
  - 会话归属隔离（多用户数据安全）
  - 401/403 鉴权边界
  - 文档上传→分块→向量的流程（RAG 服务全程 mock）
  - SQLite 并发写入（WAL 配置下多 session 并行插入不报 locked）

### 第4步：运行测试
运行本技能的脚本（可任意目录执行，脚本会自动定位 backend 目录并产出报告）：
```
C:\Users\13445\miniconda3\python.exe .opencode\skills\unit-test\scripts\run_tests.py
```
脚本会：① 自动安装缺失的测试依赖 ② 生成 `backend/tests/conftest.py` 与 `backend/pytest.ini`（若不存在）③ 清理旧测试库与报告 ④ 执行 pytest 并同时产出：
- `backend/reports/pytest_report.html`：测试结果 HTML 报告
- `backend/reports/coverage_html/`：代码覆盖率 HTML 报告
- 终端打印：通过/失败数、总耗时、覆盖率百分比

如需单独调试单个文件：
```
C:\Users\13445\miniconda3\python.exe -m pytest tests/test_auth_api.py -v
```

### 第5步：输出报告与总结
向用户交付：
1. **测试结果摘要**：总用例数、通过数、失败数、成功率、执行耗时。
2. **覆盖率摘要**：总覆盖率% + 各模块覆盖情况（重点标出低于 50% 的模块）。
3. **HTML 报告路径**（两个都要给）：
   - `backend/reports/pytest_report.html`
   - `backend/reports/coverage_html/index.html`
4. **失败项说明**：逐条列出失败用例与根因（测试bug/代码bug），已修复的说明修复内容。

## 报告格式说明
- pytest-html 使用 `--self-contained-html`，单文件，可直接双击浏览器打开。
- 若用户要求把报告放到网页服务，可提示用 `python -m http.server` 在 `backend/reports/` 目录起静态服务，或后续扩展技能脚本。

## 常见坑
- `aiosqlite` 与 pytest 的 event loop：`conftest.py` 的 fixture 是 `async def`，依赖 `pytest-asyncio`（`asyncio_mode = auto` 已配在 `pytest.ini`）。
- 使用测试数据库必须**在导入 `app.database` 之前**设置 `DATABASE_URL` 环境变量（`conftest.py` 已处理，勿改顺序）。
- 跑完一轮测试后清理 `backend/tests/test_bankkb.db` 与 `backend/.pytest_cache/` 可选；生产 `bankkb.db` 严禁触碰。
- coverage 统计以 `app/` 包为准（`--cov=app`），排除测试文件自身。