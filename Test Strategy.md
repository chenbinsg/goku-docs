# AIOS 后端测试方案

> 版本：v1.9.6 | 更新日期：2026-05-23

---

## 一、测试环境要求

### 1.1 依赖服务

| 服务 | 版本要求 | 说明 |
|------|----------|------|
| Python | ≥ 3.11 | 运行时环境 |
| MySQL | ≥ 8.0 | 测试专用数据库 `aios_test` |
| Redis | 可选 | 仅多 worker 部署下必须 |

> **注意**：测试套件使用 MySQL 特有类型（`MEDIUMTEXT`、`JSON`），**不支持 SQLite**。

### 1.2 测试数据库初始化

```bash
# 登录 MySQL，创建测试数据库（一次性操作）
mysql -u root -p
```

```sql
CREATE DATABASE IF NOT EXISTS aios_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

默认连接串（见 `backend/conftest.py`）：

```
mysql+pymysql://root:123456@127.0.0.1:3306/aios_test
```

如需自定义，设置环境变量：

```bash
export TEST_DATABASE_URL="mysql+pymysql://<user>:<pass>@<host>:3306/aios_test"
```

### 1.3 Python 依赖安装

```bash
pip install -r backend/requirements.txt
pip install pytest pytest-cov
```

### 1.4 必要环境变量

测试框架（`backend/conftest.py`）已内置以下默认值，本地开发无需手动设置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | 指向 `aios_test` | 自动注入 |
| `SECRET_KEY` | `test-secret-key-at-least-32-chars-long!!` | JWT 签名 |
| `REDIS_URL` | `""` (空，禁用) | 测试不需要 Redis |
| `ADMIN_RESET_TOKEN` | `test-reset-token` | 管理员重置接口 |
| `ALLOW_PUBLIC_REGISTRATION` | `false` | 关闭公开注册 |

---

## 二、运行测试

所有命令均在**项目根目录**（`/Users/chenbin/agent/`）执行。

### 2.1 运行全量测试

```bash
pytest
```

预期结果：**≥ 498 passed，≤ 11 skipped，0 failed**

### 2.2 运行单个文件

```bash
# 示例：只跑认证模块测试
pytest backend/tests/test_auth_router.py

# 示例：只跑安全回归
pytest backend/tests/test_p0_security_regression.py
```

### 2.3 运行单个 Test Case

```bash
# 格式：pytest <文件>::<函数名>
pytest backend/tests/test_auth_router.py::test_login_success
pytest backend/tests/test_departments.py::test_create_department_superuser
```

### 2.4 测试报告

三种报告已配置为**每次运行自动生成**（无需额外参数），统一输出到 `reports/` 目录。

```bash
pytest      # 运行后自动生成全部报告
```

| 报告类型 | 文件路径 | 用途 |
|---------|---------|------|
| **测试结果 HTML** | `reports/test_report.html` | 每条 case 的 pass/fail/skip 明细，可归档 |
| **覆盖率 HTML** | `reports/coverage_html/index.html` | 按文件/行查看哪些代码被覆盖 |
| **覆盖率 XML** | `reports/coverage.xml` | 供 CI / SonarQube / Codecov 消费 |
| 覆盖率终端摘要 | 控制台输出 | 快速查看，不落盘 |

```bash
# macOS 打开报告
open reports/test_report.html
open reports/coverage_html/index.html
```

> `reports/` 已加入 `.gitignore`，不会随代码提交。归档时手动保存该目录即可。

### 2.5 常用参数

| 参数 | 作用 |
|------|------|
| `-v` | 显示每条 test 的详细结果（已在 `pyproject.toml` 中默认开启） |
| `--tb=short` | 失败时只显示简短 traceback |
| `-x` | 遇到第一个失败立即终止 |
| `-k "keyword"` | 按函数名关键词过滤，例如 `-k "auth or login"` |
| `-m "mark"` | 按 pytest.mark 过滤 |
| `--no-header -q` | 静默模式，只输出 pass/fail 统计 |
| `-s` | 不捕获 stdout，便于调试 print 输出 |

### 2.6 按优先级分组运行

```bash
# P0 安全回归（最高优先级，每次发布前必跑）
pytest backend/tests/test_p0_security_regression.py -v

# P1 资产暴露 + 集成测试
pytest backend/tests/test_p1_asset_exposure_regression.py \
       backend/tests/test_p1_integration.py \
       backend/tests/test_p1_shell_execute_regression.py -v

# P2 内部作用域回归
pytest backend/tests/test_p2_internal_scope_regression.py -v

# 核心 API（认证 / 用户 / 部门 / 角色）
pytest backend/tests/test_auth_router.py \
       backend/tests/test_users_router.py \
       backend/tests/test_departments.py -v
```

---

## 三、测试文件目录

### 3.1 安全与权限（最高优先级）

| 文件 | Tests | 覆盖范围 |
|------|------:|----------|
| `test_p0_security_regression.py` | 6 | 注册封禁、超管防提权、审批授权链、管理员令牌保护 |
| `test_p1_shell_execute_regression.py` | 2 | Shell 执行：允许简单命令、拦截复合/危险语法 |
| `test_p1_asset_exposure_regression.py` | 3 | 工作区资产暴露：拦截 HTML/JS，允许 SVG/图片 |
| `test_p2_internal_scope_regression.py` | 3 | 任务/会话作用域隔离、跨租户访问防护 |
| `test_realtime_auth.py` | 4 | 实时 SSE 接口的身份认证守卫 |

### 3.2 核心 API

| 文件 | Tests | 覆盖范围 |
|------|------:|----------|
| `test_auth_router.py` | 14 | 登录/登出/注册/密码修改/管理员重置 |
| `test_users_router.py` | 22 | 用户 CRUD、角色 CRUD、权限边界（超管保护） |
| `test_departments.py` | 13 | 部门 CRUD、未授权访问、重名校验 |
| `test_org_api.py` | 37 | 组织树、批量分配 CSV/JSON、Agent 摘要 |
| `test_health.py` | 1 | `/api/v1/health` 健康检查响应结构 |

### 3.3 Agent 与执行引擎

| 文件 | Tests | 覆盖范围 |
|------|------:|----------|
| `test_p1_integration.py` | 4 | 并发限流（503）、任务速率限制、Executor 执行与取消 |
| `test_agent_registry.py` | 12 | 并发配置、Slot 获取释放、Agent 注册表 |
| `test_conversation_agent_binding_guards.py` | 3 | 工具能力问题识别、显式 agent_id 路由绕过自动绑定 |
| `test_conversation_timeout_policy.py` | 4 | 超时策略校验 |
| `test_final_answer_delivery_guards.py` | 4 | 最终答案守卫（禁止在工具调用中伪造完成） |
| `test_skill_loop.py` | 11 | Skill 执行循环 |
| `test_parallel_execution.py` | 13 | 并行任务执行 |

### 3.4 工具与集成

| 文件 | Tests | 覆盖范围 |
|------|------:|----------|
| `test_cli.py` | 54 | CLI 命令集 |
| `test_mcp_server_connection_binding.py` | 50 | MCP 服务器连接绑定 |
| `test_mcp_external_connections.py` | 35 | MCP 外部连接 |
| `test_skill_packs.py` | 34 | Skill Pack 安装/加载 |
| `test_hybrid_search.py` | 33 | BM25 + 向量混合检索 |
| `test_file_parser_server.py` | 28 | 文件解析服务（PDF/Word/Excel） |
| `test_openrouter_provider.py` | 24 | OpenRouter 模型目录、多厂商分布 |
| `test_outlook_calendar_tool.py` | 9 | Outlook 日历工具 |
| `test_calendar_routing.py` | 2 | 日历路由 |
| `test_flight_booking_final_answer_guard.py` | 3 | 机票预订守卫 |
| `test_flight_travel_mcp_server.py` | 2 | 机票查询 MCP 服务 |
| `test_room_booking_final_answer_guard.py` | 3 | 会议室预订守卫 |

### 3.5 其他功能

| 文件 | Tests | 覆盖范围 |
|------|------:|----------|
| `test_user_preferences.py` | 22 | 用户偏好设置 |
| `test_cost_export.py` | 19 | 费用导出 |
| `test_llm_provider_tool_normalization.py` | 3 | LLM 工具参数标准化 |
| `test_baiwu_daily_report_tool.py` | 2 | 百务日报工具 |
| `test_baiwu_monitor_source_coverage.py` | 6 | 百务监控源覆盖率 |
| `test_workspace_cleanup.py` | 2 | 工作区清理 |
| `test_workspace_username.py` | 10 | 工作区用户名隔离 |
| `test_file_parser_s3_integration.py` | 7 | 文件解析 S3 集成 |

### 3.6 已跳过（需更新）

| 文件 | 原因 |
|------|------|
| `test_ira_email_delivery_tools.py`（3 tests）| `ira_tools._request` 已移除，待重构 |
| `test_openrouter_provider.py` 中 `TestProviderAvailable` | `_provider_available` 已从 `model_router` 移除 |

---

## 四、测试隔离机制

测试框架使用 **SAVEPOINT（嵌套事务）** 实现每个 test case 的数据库隔离：

```
测试开始
  └─ BEGIN（外层事务）
       └─ SAVEPOINT（内层）
            └─ [测试执行：db.add / db.flush]
       └─ ROLLBACK TO SAVEPOINT（测试结束后自动清理）
  └─ ROLLBACK（外层）
```

- **每个 test 结束后，所有写入自动回滚**，无需手动清理数据
- 所有 test 共享同一 MySQL `aios_test` 库，表结构在 session 开始时由 `Base.metadata.create_all` 一次性创建
- FastAPI TestClient 的 `get_db` 依赖被替换为 conftest 的 `db` fixture，保证 HTTP 层与数据库层使用同一 session

**核心 Fixtures（`backend/conftest.py`）：**

| Fixture | 作用域 | 说明 |
|---------|--------|------|
| `engine` | session | 整个测试会话共用一个 SQLAlchemy Engine |
| `db` | function | 每个 test 独立的隔离 Session（SAVEPOINT） |
| `client` | function | FastAPI TestClient，`get_db` 已注入 `db` |
| `admin_user` | function | 返回或创建 `test_admin` 超管用户 |
| `admin_token` | function | 生成 admin JWT（`sub` = `user.id`，UUID 格式） |
| `auth_headers` | function | `{"Authorization": "Bearer <token>"}` |

---

## 五、常见问题

### Q1：测试提示 `Access denied for user 'root'@'localhost'`

MySQL 用户名或密码不匹配，通过环境变量覆盖：

```bash
export TEST_DATABASE_URL="mysql+pymysql://your_user:your_pass@127.0.0.1:3306/aios_test"
pytest
```

### Q2：提示 `Can't connect to MySQL server`

确保 MySQL 已启动：

```bash
# macOS (Homebrew)
brew services start mysql

# Linux (systemd)
sudo systemctl start mysql
```

### Q3：`aios_test` 数据库不存在

```sql
CREATE DATABASE aios_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Q4：报错 `Table 'aios_test.xxx' doesn't exist`

首次运行时框架会自动建表。如果表结构与模型不同步，先删库重建：

```sql
DROP DATABASE aios_test;
CREATE DATABASE aios_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

然后重新运行 `pytest`。

### Q5：某个 test 意外污染了其他 test 的数据

检查该 test 是否：
1. 调用了 `db.commit()`（禁止在测试中 commit，应使用 `db.flush()`）
2. 直接使用了新建的 engine/session 而非 conftest 的 `db` fixture

### Q6：想在本机快速验证某个模块，不跑全量

```bash
# 只跑认证相关
pytest -k "auth or login or password" -v

# 只跑安全回归（P0 + P1 + P2）
pytest -k "p0 or p1 or p2" -v
```

### Q7：测试耗时过长

全量 508 个 test 正常约 **70-90 秒**（含 MySQL 建连开销）。如需加速：

```bash
# 并行执行（需安装 pytest-xdist）
pip install pytest-xdist
pytest -n auto
```

> 注意：并行模式下 SAVEPOINT 隔离仍然有效，但需确保 MySQL 连接数充足。

---

## 六、CI/CD 集成参考

### GitHub Actions 示例

```yaml
name: Backend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: 123456
          MYSQL_DATABASE: aios_test
        ports:
          - 3306:3306
        options: --health-cmd="mysqladmin ping" --health-interval=10s --health-timeout=5s --health-retries=3

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r backend/requirements.txt pytest pytest-cov

      - name: Run tests
        env:
          TEST_DATABASE_URL: mysql+pymysql://root:123456@127.0.0.1:3306/aios_test
        run: pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

---

## 七、覆盖率现状

运行时通过 `pyproject.toml` 排除外围模块（Telegram/WhatsApp Bot、Scheduler、外部集成等），**关注核心业务代码覆盖率**：

| 模块 | 覆盖率 | 说明 |
|------|------:|------|
| `routers/models_router.py` | ~99% | 模型能力查询 |
| `routers/departments.py` | ~96% | 部门管理 |
| `routers/auth.py` | ~73% | 认证接口 |
| `routers/users.py` | ~69% | 用户管理 |
| `routers/agents.py` | ~24% | Agent 管理（待补充） |
| `routers/conversations.py` | ~33% | 对话接口（待补充） |
| `routers/tasks.py` | ~24% | 任务接口（待补充） |

目标：核心路由模块整体行覆盖率 ≥ 80%（规划于 v1.9.7）。
