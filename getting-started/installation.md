# Goku Platform — 安装指南

**版本**: v1.9.8  
**最后更新**: 2026-05-24

---

## 目录

1. [系统要求](#1-系统要求)
2. [本地安装（macOS / Linux）](#2-本地安装macos--linux)
3. [Docker Compose 安装（推荐生产环境）](#3-docker-compose-安装推荐生产环境)
4. [环境变量说明](#4-环境变量说明)
5. [本地 LLM 部署（llama-server / Qwen）](#5-本地-llm-部署llama-server--qwen)
6. [数据库文件说明](#6-数据库文件说明)
7. [首次登录与初始配置](#7-首次登录与初始配置)
8. [升级到新版本](#8-升级到新版本)
9. [停止与重启](#9-停止与重启)
10. [常见问题排查](#10-常见问题排查)
11. [邮件收件箱处理配置](#11-邮件收件箱处理配置)

---

## 1. 系统要求

### 本地运行

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Python | 3.11 | 3.12 |
| Node.js | 18 | 20+ |
| npm | 9 | 最新稳定版 |
| MySQL | 8.0 | 8.0 LTS |
| 操作系统 | macOS 12 / Ubuntu 20.04 | macOS 14 / Ubuntu 22.04 |

### Docker 运行

| 组件 | 版本 |
|------|------|
| Docker Engine | 24.0+ |
| Docker Compose | v2.20+ |

> **macOS 专属功能**（麦克风采集、日历工具）仅在本地模式下可用，Docker 模式暂不支持。

---

## 2. 本地安装（macOS / Linux）

### 步骤 1 — 解压安装包

```bash
tar -xzf goku-v1.9.29.tar.gz
cd agent
```

### 步骤 2 — 配置环境变量

```bash
cp backend/.env.example backend/.env
```

用文本编辑器打开 `backend/.env`，填写以下**必填**项：

```ini
# 数据库连接
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/你的数据库名

# 应用密钥（随机字符串，32位以上）
SECRET_KEY=生成方法见下方

# LLM 提供商（三选一）
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
AGENT_WORKSPACE=/path/to/aios/workspace
TOOL_PROBE_REPORT_EMAIL=admin@example.com
AGENT_PROBE_REPORT_EMAIL=admin@example.com
LOG_ANALYSIS_REPORT_EMAIL=admin@example.com
IR_DAILY_REPORT_EMAIL=admin@example.com
```

如需启用 Microsoft 365 / Outlook 邮件、日历和会议室预订工具，继续填写：

```ini
OUTLOOK_CLIENT_ID=Azure 应用 Client ID
OUTLOOK_CLIENT_SECRET=Azure 应用 Client Secret
OUTLOOK_TENANT_ID=Azure Tenant ID
OUTLOOK_MAILBOX=日历/邮箱所有者邮箱
OUTLOOK_CALENDAR_MAILBOX=日历所有者邮箱
OUTLOOK_CALENDAR_TIMEZONE=Tokyo Standard Time
# Optional: override default meeting room resource mailboxes
# OUTLOOK_ROOM_MAP_JSON={"Tokyo":"meeting-room-a@your-domain.com","Beijing":"meeting-room-b@your-domain.com","Singapore":"meeting-room-c@your-domain.com"}
```

Microsoft Entra ID 中建议授予并管理员同意以下 Microsoft Graph Application 权限：
`Mail.Read`、`Mail.Send`、`Calendars.ReadBasic.All`、`Calendars.ReadWrite`、`Place.Read.All`。

生成 `SECRET_KEY`：

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 步骤 3 — 创建数据库并导入数据

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS 你的数据库名 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 方式A：全量恢复（推荐，包含系统配置、工具、模型等所有数据）
mysql -u root -p 你的数据库名 < db/full_dump.sql

# 方式B：Alembic baseline + 内置 package 同步（干净安装）
cd backend
DATABASE_URL=mysql+pymysql://root:密码@127.0.0.1:3306/你的数据库名 alembic upgrade head
python scripts/sync_builtin_packages.py
```

### 步骤 4 — 安装 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 步骤 5 — 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### 步骤 6 — 启动

```bash
./start.sh
```

启动后访问：
- **前端界面**: http://localhost:5106
- **后端 API 文档**: http://localhost:8106/docs

---

## 3. Docker Compose 安装（推荐生产环境）

### 步骤 1 — 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填写 API Key 等必填项
```

修改 `docker-compose.yml` 中的默认密码：

```yaml
environment:
  MYSQL_ROOT_PASSWORD: "你的安全密码"
  MYSQL_DATABASE: "aios"
```

同时在 `backend/.env` 中更新 `DATABASE_URL` 以匹配：

```ini
DATABASE_URL=mysql+pymysql://root:你的安全密码@mysql:3306/aios
```

### 步骤 2 — 首次启动并导入数据

```bash
# 仅启动数据库
docker compose up -d mysql
sleep 20

# 使用 Alembic baseline 初始化 schema 和必需基础数据
docker compose run --rm db-migrate

# 刷新内置 package 资产
docker compose run --rm db-sync

# 启动全部服务
docker compose up -d
```

### 步骤 3 — 验证运行状态

```bash
docker compose ps
curl http://localhost/health
```

所有服务显示 `Up` 状态即表示安装成功。

---

## 4. 环境变量说明

### LLM 配置（三选一）

```ini
# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...

# Anthropic Claude
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...

# 本地模型（Ollama / llama-server）
LLM_PROVIDER=openai            # 使用 OpenAI-compatible 接口
OPENAI_BASE_URL=http://localhost:8080/v1
OPENAI_API_KEY=local           # 本地服务无需真实 Key
LLM_MODEL=qwen2.5-14b          # 与 --alias 一致
LLM_TIMEOUT=300                # 本地推理较慢，建议 300 秒
```

### 多模型故障转移（v1.0.4 新增）

配置备用模型，主模型不可用时自动切换，无需重启服务：

```ini
# 备用模型列表（逗号分隔，按优先级排序）
LLM_FALLBACK_MODELS=gpt-4o,claude-sonnet-4-6
# 对应的 Provider（顺序与上面对应）
LLM_FALLBACK_PROVIDERS=openai,anthropic

# 断路器调优（通常无需修改默认值）
LLM_CB_FAILURE_THRESHOLD=5    # 连续失败几次触发熔断（默认 5）
LLM_CB_COOLDOWN_SECONDS=60    # 熔断冷却时间，秒（默认 60）
LLM_CB_SUCCESS_THRESHOLD=2    # 半开状态需要几次成功才恢复（默认 2）
```

### LLM 超时与可靠性（v1.2.5 新增）

```ini
# LLM 调用超时时间（秒）；本地模型推理较慢，建议 300；云端 API 可用 120（默认）
LLM_TIMEOUT=300
```

### 心跳可靠性（v1.0.4 新增）

```ini
# 最大并发执行数，超出时排队等待（默认 4）
HEARTBEAT_MAX_WORKERS=4
# 失败后自动重试次数（默认 2，间隔 30s/60s 递增）
HEARTBEAT_MAX_RETRIES=2
# 重试基础等待时间，秒（默认 30）
HEARTBEAT_RETRY_DELAY_SECONDS=30
# 超过此分钟数未触发的任务视为漏跑，启动后补跑一次（默认 10）
HEARTBEAT_CATCHUP_THRESHOLD_MINUTES=10
# 心跳扫描间隔，秒（默认 60）
HEARTBEAT_SCAN_INTERVAL_SECONDS=60
# 连续失败告警收件人（留空则不发告警邮件）
ALERT_EMAIL_TO=admin@yourcompany.com
```

### 定时任务时区（v1.9.2 新增）

Cron 表达式触发时间以 **`APP_TIMEZONE`** 为准。优先级：数据库 `SystemConfig` → 环境变量 → 默认值。

```ini
# 系统时区（与"系统管理 → 系统设置"中的 APP_TIMEZONE 保持一致）
# 支持所有 IANA 时区名，例如：Asia/Tokyo、Asia/Shanghai、UTC
APP_TIMEZONE=Asia/Shanghai
```

> **注意**：此环境变量作为回退值；正式环境建议通过 UI（系统管理 → 系统设置）设置，支持不重启生效。

### 可选集成

```ini
# SMTP 邮件发送
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=你@yourcompany.com
SMTP_PASS=
SMTP_SSL=false

# Microsoft 365 / Outlook 收件（Graph API）
OUTLOOK_CLIENT_ID=Azure应用ClientID
OUTLOOK_CLIENT_SECRET=Azure应用Secret
OUTLOOK_TENANT_ID=Azure租户ID
OUTLOOK_MAILBOX=你@yourcompany.com

# 企业微信（WeCom）双向接入
WECHAT_CORP_ID=ww...
WECHAT_CORP_SECRET=...
WECHAT_AGENT_ID=...
WECHAT_ENCODING_AES_KEY=...
WECHAT_TOKEN=...

# 飞书 Webhook
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/...
FEISHU_WEBHOOK_SECRET=签名密钥

# Teams / LINE 通知
TEAMS_WEBHOOK_URL=https://...
LINE_CHANNEL_SECRET=...
LINE_CHANNEL_ACCESS_TOKEN=...

# AIBI 企业分析（需内网/VPN）
AIBI_BASE_URL=http://your-aibi-host:8080
AIBI_TOKEN=your-aibi-token

# 麦克风与字幕（仅 macOS 本地模式）
MICROPHONE_ENABLED=true
SUBTITLE_CHUNK_SECONDS=4

# 日历（仅 macOS）
CALENDAR_DEFAULT=我的日历

# Agent 沙箱
SANDBOX_MODE=subprocess        # subprocess（默认）| docker
AGENT_WORKSPACE=/path/to/workspace
```

---

## 5. 本地 LLM 部署（llama-server / Qwen）

AIOS 支持通过 [llama.cpp](https://github.com/ggerganov/llama.cpp) 的 `llama-server` 在本机运行量化模型。以下以 **Qwen2.5-14B-Instruct Q4_K_M** 为例。

### 5.1 安装 llama-server（macOS）

```bash
brew install llama.cpp
```

### 5.2 下载模型

将模型文件（`.gguf` 格式）存放于本机，例如 `~/models/QWen/`。

### 5.3 启动脚本

创建 `~/models/QWen/start_server.sh`（已包含推荐的内存优化参数）：

```bash
#!/bin/bash
MODEL=~/models/QWen/qwen2.5-14b-instruct-q4_k_m-00001-of-00003.gguf

exec /opt/homebrew/bin/llama-server \
  --model "$MODEL" \
  --alias qwen2.5-14b \
  --ctx-size 8192 \          # 与 AIOS 系统提示 Token 预算匹配（见§Token预算）
  --n-gpu-layers 99 \        # Metal GPU 全量卸载（Apple Silicon）
  --threads 8 \
  --parallel 1 \
  --embeddings \
  --pooling mean \
  --cache-type-k q8_0 \      # KV 缓存量化，节省 ~50% 显存
  --cache-type-v q8_0 \
  --host 0.0.0.0 \
  --port 8080 \
  --log-disable
```

```bash
chmod +x ~/models/QWen/start_server.sh
~/models/QWen/start_server.sh    # 前台运行；Ctrl+C 停止
```

### 5.4 停止

```bash
pkill -f llama-server
```

### 5.5 验证

```bash
curl http://localhost:8080/health   # → {"status":"ok"}
```

### 5.6 内存参考（Apple Silicon 16GB）

| 模型 | ctx-size | KV cache | 显存占用 | 可用余量 |
|------|---------|---------|---------|---------|
| Qwen2.5-14B Q4_K_M | 8192 | q8_0 | ~9.1 GB | ~6.9 GB |
| Qwen2.5-14B Q4_K_M | 12288 | f16 | ~12.5 GB | 不足，OOM |

> **建议**：16GB 机器使用 `--ctx-size 8192` + `--cache-type-k q8_0 --cache-type-v q8_0`。
> 32GB 及以上可考虑 `--ctx-size 16384`。

---

## 6. 数据库文件说明

| 文件 | 内容 |
|------|------|
| `db/schema.sql` | 历史 DDL 快照；新安装以 Alembic baseline 为准 |
| `db/seed_data.sql` | 历史基础数据快照；必需基础数据已进入 Alembic baseline |
| `db/full_dump.sql` | 全量数据（推荐用于完整恢复） |

### 当前数据库表结构（v1.9.8）

| 表名 | 说明 |
|------|------|
| `users` | 用户账号，含 `department` 和 `team_id`（v1.9.8 新增，迁移 0055）字段 |
| `user_departments` | 用户-部门多对多关联（支持一人多部门） |
| `departments` | 部门主数据，预定义规范部门名（v1.9.6 新增，迁移 0052） |
| `teams` | 团队主数据，每个团队隶属一个部门（v1.9.8 新增，迁移 0055） |
| `agent_access_policies` | Agent ACL 策略表，DefaultDeny 模式（v1.9.8 新增，迁移 0056/0057） |
| `roles` | RBAC 角色与权限 |
| `user_roles` | 用户-角色关联 |
| `tenants` | 多租户配置 |
| `tasks` | Agent 任务记录 |
| `agent_sessions` | Agent 执行会话（v1.2.2 新增 6 个并发字段，见下） |
| `agent_definitions` | Agent 定义；含 `visibility`、`allowed_roles` 字段（v1.9.6 新增，迁移 0051） |
| `user_agent_favorites` | 用户收藏的 Agent（v1.9.6 新增，迁移 0051） |
| `conversations` | 对话会话 |
| `messages` | 对话消息 |
| `workflows` | 工作流 DAG 定义 |
| `workflow_executions` | 工作流执行记录 |
| `tools` | 工具注册表 |
| `plugins` | 插件注册表 |
| `models` | 模型配置 |
| `memories` | 长期记忆 |
| `knowledge_docs` | 知识库文档 |
| `approvals` | 人工审批记录 |
| `incoming_emails` | 来信处理队列（邮件自动处理功能，v1.9.3 新增） |
| `email_archive` | 已处理邮件归档（无邮件正文，仅元数据，永久保留） |
| `audit_logs` | 不可变审计日志 |
| `heartbeats` | 定时任务配置（v1.0.4 新增 3 字段） |
| `notifications` | 通知消息 |
| `alert_rules` | 监控告警规则 |
| `system_configs` | 系统配置键值对 |
| `token_blacklist` | JWT 黑名单 |

#### heartbeats 表字段变更（v1.0.4，Migration 0009）

| 新增字段 | 类型 | 说明 |
|---------|------|------|
| `consecutive_failures` | INT DEFAULT 0 | 连续失败次数，成功后归零；≥3 触发告警邮件 |
| `last_error` | TEXT | 最近一次执行的错误信息，方便排查 |
| `cron_error` | TEXT | Cron 表达式解析错误信息；非空时任务已被自动禁用 |

#### agent_sessions 表字段变更（v1.2.2 / Migration 0026，Project Wukong）

| 新增字段 | 类型 | 说明 |
|---------|------|------|
| `caller_id` | VARCHAR(128) | 请求发起方 ID（如用户 ID 或电话号码），可为空 |
| `channel` | VARCHAR(50) | 接入渠道（web / line / telegram / phone 等），可为空 |
| `queued_at` | DATETIME | 请求进入并发队列的时间戳，可为空 |
| `answered_at` | DATETIME | 请求获得槽位、开始执行的时间戳，可为空 |
| `continuation_of` | VARCHAR(36) | 外键→`agent_sessions.id`，标记本会话是哪个会话的延续，可为空 |
| `instance_slot` | INT | 执行时使用的槽位编号（如 1、2、3），可为空 |

> 以上字段全部可为空（nullable），**升级时不影响现有数据**。  
> 完整的字段定义请查看 `db/schema.sql`。

---

## 7. 首次登录与初始配置

### 默认账号

| 用户名 | 密码 | 权限 |
|--------|------|------|
| `admin` | `Admin@123` | 超级管理员 |

> **安装完成后请立即修改默认密码！**

### 建议的初始配置步骤

1. **修改 admin 密码** → 右上角头像 → **个人中心** → 修改密码
2. **配置 LLM 模型** → 左侧菜单 → AI 能力 → 模型管理 → 添加你的 API Key
3. **设置 Agent 身份** → 系统 → Agent 灵魂 → 填写角色定位和个性设置
4. **预定义部门** → 系统管理 → **部门管理** → 新建部门（避免后续命名不一致）
5. **创建团队**（v1.9.8 新增）→ 侧边栏 → **组织架构**（`/org`）→ 选择部门 → 「新建团队」
6. **创建普通用户** → 系统管理 → 用户管理 → 新建用户（部门从上一步列表中选择，可选择所属团队）
7. **配置 Agent 访问策略**（v1.9.8 新增，可选）→ AI 能力 → 代理管理 → 编辑 Agent → 「🔐 访问策略」Tab → 按用户/团队/部门授权
8. **配置消息通道**（可选）→ 扩展 → 消息连接器 → 填写飞书/Teams/LINE/WhatsApp/Discord Webhook

---

## 8. 升级到新版本

```bash
# 1. 解压新版本包
tar -xzf aios-V1.2.5.tar.gz

# 2. 备份当前数据库
mysqldump -u root -p 你的数据库名 > backup-$(date +%Y%m%d).sql

# 3. 应用数据库迁移
cd agent-新版本/backend
source ../.venv/bin/activate
DATABASE_URL=mysql+pymysql://root:密码@127.0.0.1:3306/你的数据库名 alembic upgrade head

# 4. 安装新依赖
pip install -r requirements.txt
cd ../frontend && npm install && cd ..

# 5. 重启
./stop.sh && ./start.sh
```

### v1.9.8 升级注意事项

- **Teams 表（Migration 0055）**：新增 `teams` 表（`id`、`name`、`description`、`department_id`、`tenant_id`、`created_at`），`users` 表新增 `team_id VARCHAR(36)` 可空外键。运行 `alembic upgrade head` 自动完成，现有用户 `team_id` 为 NULL，不影响已有数据。
- **Agent 访问策略表（Migration 0056）**：新增 `agent_access_policies` 表，实现 DefaultDeny 精细 ACL（字段：`principal_type`、`principal_id`、`can_view`、`can_use`、`can_config`、`granted_by`、`expires_at`）。现有 Agent 和用户数据不受影响。
- **策略表 tenant_id 可空修复（Migration 0057）**：将 `agent_access_policies.tenant_id` 改为可空，使跨租户全局策略可以正确存储。
- **DefaultDeny 生效范围**：迁移完成后，`visibility='private'` 的 Agent 对非创建者/非管理员立即变为不可见（DefaultDeny）。如需为现有私有 Agent 授权，请在「🔐 访问策略」Tab 逐一添加策略，或运行以下语句批量为所有用户授予 public Agent 的 `can_view`：
  ```sql
  -- 仅示例，按需修改
  INSERT INTO agent_access_policies (id, agent_id, principal_type, principal_id, can_view, can_use, can_config, granted_by)
  SELECT UUID(), id, 'tenant', tenant_id, 1, 1, 0, user_id
  FROM agent_definitions WHERE visibility = 'private';
  ```
- **完整升级流程**：
  ```bash
  cd backend
  alembic upgrade head          # 应用 0055, 0056, 0057
  python scripts/export_agents.py  # 可选：更新 seed 文件
  ```

### v1.9.6 升级注意事项

- **部门主数据表**：新增 `departments` 表（Migration 0052），运行 `alembic upgrade head` 自动创建，并自动 seed 现有 users / agent_definitions 中已使用的部门名（INSERT IGNORE，幂等安全）。
- **Agent 访问控制**：`agent_definitions` 表新增 `visibility VARCHAR(20)` 和 `allowed_roles JSON` 字段（Migration 0051），现有 Agent 按旧逻辑自动迁移：`department IS NULL` → `visibility='public'`，否则 → `visibility='department'`。
- **用户收藏**：新增 `user_agent_favorites` 关联表（同 Migration 0051）。
- **连接器配置写穿**：后端启动时自动将数据库 `CONNECTOR_*` 配置同步到 `os.environ`，无需手动配置环境变量；现有环境变量不被覆盖（只补不覆）。
- **新增消息渠道**：连接器概览页新增 WhatsApp Business 和 Discord Bot 卡片，在对应的「连接器配置」页填写 Token 后自动显示「已配置」。
- **个人中心**：所有用户登录后可通过右上角头像 → **个人中心**（`/profile`）修改自己的密码，无需联系管理员。
- **数据库迁移**：运行 `make deploy`（或 `alembic upgrade head`）即可完成 0051、0052 两个迁移，现有数据不受影响。

### v1.9.3 升级注意事项

- **邮件收件箱处理**：新增 `incoming_emails` 和 `email_archive` 两张表（Migration 0042），运行 `alembic upgrade head` 自动创建。
- **SMTP 发件**：如需启用邮件自动发送，在 `.env` 中配置 `SMTP_HOST / SMTP_USER / SMTP_PASS`（详见§11.1）。
- **Agent 编辑表单**：新增「📬 邮件收件箱」Tab，仅对已保存 Agent 可用（新建 Agent 需先保存）。
- **邮件收件箱队列管理页**：新增 `/email-queue` 管理页面，运营人员可集中查看所有来信状态、手动分配并派发给 Agent、丢弃垃圾邮件。左侧菜单「邮件收件箱队列」入口右侧显示待处理邮件数徽章。
- **邮件队列 API**：新增以下接口（供运维脚本使用）：
  - `GET /api/v1/email-queue` — 列表（支持 `status` / `assigned_agent` / `include_rejected` 过滤）
  - `GET /api/v1/email-queue/stats/summary` — 各状态数量统计
  - `GET /api/v1/email-queue/{id}` — 单封邮件详情（含正文）
  - `POST /api/v1/email-queue/{id}/dispatch` — 手动派发给指定 Agent
  - `PATCH /api/v1/email-queue/{id}/assign` — 仅更新分配关系
  - `DELETE /api/v1/email-queue/{id}` — 丢弃（status → rejected）
- **APScheduler 新增任务**：后端启动时自动注册两个新调度任务：  
  - `email_queue_heartbeat`（每 10 分钟）  
  - `email_cleanup_nightly`（每日 02:00 UTC）  
  - 日志中出现 `Email queue heartbeat scheduler started` 即表示正常。
- **技术支持 Agent 工具集调整**：`technical_support` 基础类型现使用 `submit_email_draft`（草稿审批后发送）替代 `email_send`（直接发送），确保所有回复经员工审阅后方可发出。已存在的技术支持 Agent 在下次运行 `make deploy` 后自动生效。

### v1.9.2 升级注意事项

- **定时任务时区统一**：心跳调度引擎现在读取 `SystemConfig.APP_TIMEZONE`（可在系统管理 → 系统设置中修改）来解析 Cron 表达式，不再依赖服务器 OS 时区。  
  - 若 OS 时区与 `APP_TIMEZONE` 不同，任务触发时间会随此次升级发生偏移，请检查并调整 Cron 表达式。  
  - 建议升级后在系统设置中确认 `APP_TIMEZONE` 值是否与预期一致。
- **代码质量修复**：修复多处 ruff lint 警告（F401 / F541 / E712），不影响功能。
- **数据库迁移**：无新增迁移文件，直接运行 `alembic upgrade head` 即可（幂等安全）。

### v1.2.7 升级注意事项

- **Agent 基础类型重命名**：`subagent_config.py` 中 7 种基础类型去除了 `_agent` 后缀，并合并了 2 种评审类型：
  - `comm_agent` → `customer_service`
  - `ops_monitor_agent` → `ops`
  - `pm_agent` → `project_manager`
  - `language_agent` → `translator`
  - `image_agent` → `designer`
  - `presales_agent` → `presales`
  - `tech_support_agent` → `technical_support`
  - `requirements_agent` + `arch_agent` → 合并为 `reviewer`
  
  **升级步骤**：运行 `make deploy`（含迁移 + seed 重播），数据库 `agent_definitions.agent_type` 字段会自动更新。如有自定义脚本或监控规则中硬编码了旧类型名，需一并更新。
- **并发配置 Scale API**：动态调整并发时，请使用新类型名，如 `/api/v1/agent-instances/scale/customer_service`（原 `comm_agent`）。
- **认知中枢（Cognitive Hub）**：Agent 知识管理全面启用，支持自动提取、手动添加、语义注入三条路径。
- **工作流国际化 + HTTP 节点**：工作流编辑器支持三语切换，新增 HTTP 请求节点（青色），可直接调用外部 REST API。
- **数据库迁移**：无新增迁移文件，直接运行 `alembic upgrade head` 即可（幂等安全）。

### v1.2.5 升级注意事项

- **Token 预算优化**：系统提示词已压缩（3373→1595 tokens），工具结果注入由 4000 字符上限调整为 1500 字符，Auto-Skill workflow_md 注入限制为 800 字符。升级后 Agent 响应速度在 8K 上下文模型（含本地 Qwen）上会明显改善。
- **LLM_TIMEOUT**：`.env` 新增 `LLM_TIMEOUT=300` 配置项，使用本地推理服务时建议设置。
- **Agent 工具集精简**：部分 Agent 的 `allowed_tools` 已根据 Token 预算重新裁剪，移除了非必要的重型工具（如 `browser_action`、`email_read`、`analyze_image` 等），如有业务需要可通过 Agent 管理界面手动恢复。
- **数据库迁移**：Migration 0026 为 `agent_sessions` 表新增 6 个可空字段（Wukong 并发管理），现有数据不受影响。

### v1.2.2 升级注意事项（Project Wukong）

- **数据库迁移**：`agent_sessions` 表新增 6 个可空字段。运行 `alembic upgrade head` 自动完成迁移，现有数据不受影响。
- **并发管理为纯内存**：AgentRegistry 为进程内单例，重启后槽位状态重置（正常行为）。如需跨进程/多节点并发管理，请关注后续 Wukong v2 版本（Redis 后端）。
- **并发上限默认值**：各 Agent 类型的默认并发槽位数已预设（见 `subagent_config.py`），生产环境可通过 `/api/v1/agent-instances/scale/{type}` 接口动态调整，无需重启。
- **安装后侧边栏**：AI 能力子菜单下新增「⚡ 并发运行状态」入口，首次登录后需刷新页面才可见（浏览器缓存）。

### v1.0.9 升级注意事项

- Outlook 会议室预订必须真正调用 `outlook_calendar(action=”book_room”)` 并返回 Outlook event id 后，Agent 才会报告”已预订”。
- 内置 `email_read` 是标准邮箱读取工具，支持 Graph/IMAP 的邮件列表、读取、搜索、标记、移动、删除和附件下载。
- 启动时会自动执行保守 workspace 清理，只删除旧截图、probe 临时文件和过期 e2e 报告，不删除业务报告、skills、导出包或普通用户文件。

---

## 11. 邮件收件箱处理配置

> **v1.9.3 新增**：Agent 自主处理来信、草稿审批后发送的完整流程。

### 11.1 SMTP 发件配置

邮件回复功能通过 SMTP 发送，在 `backend/.env` 中填写：

```ini
# SMTP 发件（邮件回复审批后自动发送）
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=你@yourcompany.com
SMTP_PASS=应用密码或账号密码
SMTP_SSL=false                       # 使用 STARTTLS 时填 false
SMTP_FROM=你@yourcompany.com         # 留空则等于 SMTP_USER
```

### 11.2 邮件路由规则（全局）

路径：**系统管理 → 通信渠道 → 邮件收件箱处理规则**

| 字段 | 说明 |
|------|------|
| 收件箱地址 | 监听的邮箱地址，如 `cs@yourcompany.com` |
| 分配 Agent | 该地址的邮件由哪个 Agent 处理（下拉选择 slug） |
| 全局主题屏蔽词 | 命中即跳过，如 "通知" "reimbursement" |
| 全局主题白名单 | 命中即强制处理（优先于屏蔽词），如 "urgent" |
| 全局发件人黑名单 | 精确匹配发件人地址 |
| 邮件头过滤 | 自动过滤群发/系统通知类邮件（推荐开启） |
| LLM 智能分类 | 对规则无法判断的邮件调用 LLM 做意图分类（每封约 $0.001） |

### 11.3 per-Agent 收件箱配置

路径：**代理管理 → 点击编辑 Agent → 📬 邮件收件箱 Tab**

| 字段 | 说明 |
|------|------|
| 启用邮件自动处理 | 开关；关闭时 Agent 不处理来信 |
| 监听邮箱地址 | 覆盖全局路由；该 Agent 只处理发至这些地址的邮件 |
| 巡检间隔 | 心跳检查频率（1 / 5 / 10 / 30 / 60 分钟） |
| 主题过滤词 | Agent 专属屏蔽词，命中则跳过 |
| 发件人黑名单 | Agent 专属发件人黑名单 |

> **说明**：配置存储于 `system_configs`，键名格式 `agent_inbox_{slug}`。

### 11.4 来信处理流程

```
邮件服务器
   ↓ email_watcher 拉取（每 5 min）
3 级过滤（邮件头 → 关键词 → LLM）
   ↓ 通过
incoming_emails 表（状态: new）
   ↓ 心跳触发（每 10 min）
Agent ReAct 循环
   1. fetch_pending_emails — 领取邮件，状态 → processing
   2. 理解意图 + 搜索知识库
   3. submit_email_draft — 提交草稿，创建审批，状态 → draft_ready
   ↓
审批中心（operation=email_reply）
   → 批准 → SMTP 发送，状态 → sent
   → 驳回 → 状态 → rejected
   ↓
14 天后归档至 email_archive，从 incoming_emails 删除
```

### 11.5 邮件收件箱队列管理页（运维操作）

路径：**左侧菜单 → 邮件收件箱队列**（`/email-queue`）

运营 / 运维人员通过此页面对来信进行人工干预，无需直接操作数据库。

**手动派发（当自动路由未匹配时）**：

1. 在「分配给」列选择目标 Agent
2. 弹窗选择「立即派发」→ 创建任务，邮件状态变为 `processing`
3. 或选择「仅分配，不派发」→ 等待下次心跳自动触发

**批量运维场景**：

```bash
# 查询所有 new 状态邮件（API 方式）
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8106/api/v1/email-queue?status=new&size=50"

# 查询各状态数量
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8106/api/v1/email-queue/stats/summary"

# 手动派发某封邮件给指定 Agent
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_slug":"technical-support"}' \
  "http://localhost:8106/api/v1/email-queue/{email_id}/dispatch"
```

### 11.6 常见问题

| 现象 | 解决方法 |
|------|---------|
| Agent 未处理新邮件 | 检查 `agent_inbox_{slug}` 系统配置是否启用；心跳间隔是否合理 |
| SMTP 发送失败 | 查看审批详情页错误提示；检查 `SMTP_HOST/USER/PASS` 配置 |
| 邮件被误过滤 | 查看 `email_triage` 日志；在白名单中添加关键词 |
| incoming_emails 表积压 | 在 `/email-queue` 管理页查看卡在 `processing` 状态的邮件；重新派发或手动将 status 改回 `new` |
| 归档任务未运行 | 确认 APScheduler 已启动；查看 `email_cleanup_nightly` 日志 |
| 邮件收件箱队列徽章不更新 | 前端每 30 秒轮询 `/stats/summary`；检查网络或重新登录 |
| 已拒绝邮件在「全部」标签消失 | 正常行为：拒绝邮件默认隐藏，切换到「已拒绝」标签查看 |

---

## 9. 停止与重启

```bash
# 本地模式
./stop.sh    # 停止
./start.sh   # 启动

# Docker 模式
docker compose down    # 停止
docker compose up -d   # 启动
docker compose restart # 重启（保留数据）
```

---

## 10. 常见问题排查

| 现象 | 解决方法 |
|------|---------|
| 后端无法启动 | 查看 `backend.log`；检查 `DATABASE_URL` 是否正确，MySQL 是否运行 |
| 前端空白页 | 查看 `frontend.log`；在 `frontend/` 目录执行 `npm install` |
| LLM 报错 | 检查 `backend/.env` 中的 API Key 是否填写正确 |
| 任务一直 pending | 重启后端（心跳调度器随进程启动）；若重启后仍有问题，检查 `heartbeats.cron_error` 字段是否有值 |
| 心跳任务 cron_error | Cron 表达式有误，任务已自动禁用；在界面修正表达式后重新启用 |
| 心跳连续失败告警邮件 | 查看 `heartbeats.last_error` 字段获取具体错误，修复后任务恢复正常会自动归零计数 |
| 主模型不可用/切换备用 | 检查 `LLM_FALLBACK_MODELS` 是否配置；查看后端日志中的 `Circuit breaker` 字样 |
| 日历工具不可用 | 仅 macOS 本地模式支持；在系统设置 → 隐私中授权日历访问 |
| 麦克风工具不可用 | 在 `backend/.env` 设置 `MICROPHONE_ENABLED=true` |
| MCP 服务器连接失败 | 在「MCP 管理」页面检查 Server 配置，执行连接测试并查看探活结果 |
| 数据库字段缺失错误 | 运行 `alembic upgrade head` 应用全部迁移 |
| 并发运行状态页面为空 | 正常：AgentRegistry 懒加载，提交第一个任务后对应 Agent 类型才会出现 |
| 重启后并发状态清零 | 正常：AgentRegistry 为进程内内存结构，重启后槽位自动重建 |
| 槽位全满、请求排队超时 | 使用 Scale API 提高该 Agent 类型的 `max_concurrent`；或检查是否有任务卡死未释放 |
| 并发页显示槽位但无实例 | 空闲槽位不显示在「运行中」列表中，属正常现象；点击卡片可看完整槽位表 |
| 请求 Token 数超出上下文限制 | 使用 `python scripts/token_analysis.py` 分析各 Agent 的 Token 预算；按报告建议裁剪 `allowed_tools` 或缩短 Custom Prompt |
| 本地 LLM 超时（120s 超时） | 在 `.env` 设置 `LLM_TIMEOUT=300`；并重启后端 |
| 本地 LLM OOM / 内存不足 | 降低 `--ctx-size`（推荐 8192）；添加 `--cache-type-k q8_0 --cache-type-v q8_0` 减少 KV 缓存占用 |
| 邮件 Agent 未处理来信 | 检查「邮件收件箱」Tab 是否启用；检查 email_queue_heartbeat 心跳任务是否运行 |
| SMTP 回复发送失败 | 审批详情页有错误提示；检查 SMTP_HOST/USER/PASS 环境变量 |
| incoming_emails 积压 | 有邮件卡在 processing 状态；将其改回 new 或直接重置 status='error' |

---

*如需技术支持，请查看项目 README 或联系系统管理员。*
