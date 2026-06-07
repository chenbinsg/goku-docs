# Goku-AIOS 生产部署与安全加固记录

本文记录 2026-05 腾讯云部署过程中遇到的问题、已落地的源码加固，以及生产安装时必须执行的加固步骤。所有密钥值均不应写入仓库或 PR。

## 本次源码加固

- SSE `/api/v1/tasks/{task_id}/events` 在建立事件流前校验 JWT 对应的 active user，并确认该用户有权访问目标 task。
- WebSocket `subscribe_task`、`typing.task_id`、`subscribe_conversation` 在订阅/广播前校验 task 或 conversation 的 owner 与 tenant scope，避免知道 ID 即可监听他人实时事件。
- 增加 `TRUSTED_HOSTS` 支持，在生产环境限制可接受 Host header。
- Nginx 增加 `Permissions-Policy`，并将 `/metrics`、`/docs`、`/redoc`、`/openapi.json` 限制为内网访问。

## 部署时遇到的问题

- 发布目录与 PR 工作区不要混用：线上部署目录包含临时修复和运行态文件，本 PR 使用干净 clone 分支提交，避免把部署残留带进源码。
- `/chat` 曾返回通用 1006 错误。排查到线上容器存在数据库 schema/enum 兼容、Presidio DLP 运行依赖、LLM provider timeout/circuit breaker 等多因素问题；生产升级前必须先跑 Alembic，再做健康检查和最小聊天请求。
- OpenAI 官方 provider 曾出现超时或 circuit open。Qwen 当前走 OpenRouter-compatible 的 ngrok gateway，是否为本地模型取决于 ngrok 后端，不属于 OpenAI 官方服务。
- `/metrics`、OpenAPI docs 以及 Router 管理/健康接口曾暴露在公网路径下；需要由 Nginx 与云安全组共同限制。
- Docker 宿主端口需要收敛。AIOS/Router 后端、管理前端、数据库、Redis 不应直接绑定公网 `0.0.0.0`，公网入口只保留 80/443，经反代进入服务。
- 腾讯云 CLI 与 GitHub 凭据属于操作者本机状态，不应写入仓库。部署完成后应轮换本次聊天中出现过的所有云厂商、GitHub、OpenAI 密钥。

## 生产安装步骤

1. 拉取版本并准备环境：

```bash
git checkout v1.9.4
cp .env.example .env
```

2. 生成并填写生产密钥：

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"  # SECRET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # GOKU_SECRET_KEY
```

3. 至少设置以下生产环境变量：

```dotenv
APP_ENV=production
PUBLIC_BASE_URL=https://aios.yourdomain.com
ALLOWED_ORIGINS=https://aios.yourdomain.com
TRUSTED_HOSTS=aios.yourdomain.com
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=strict
SECRET_KEY=<32+ chars random value>
GOKU_SECRET_KEY=<stable Fernet key>
ADMIN_RESET_TOKEN=<random one-time admin reset token>
AGENT_DLP_FAIL_CLOSED=true
```

4. 数据库升级与启动：

```bash
docker compose pull
docker compose up -d db redis
docker compose run --rm backend alembic upgrade head
docker compose up -d
```

5. 验证：

```bash
curl -fsS https://aios.yourdomain.com/health
curl -i https://aios.yourdomain.com/docs
curl -i https://aios.yourdomain.com/metrics
```

公网访问 docs/metrics 应返回 403 或仅允许内网/运维 IP。随后用普通用户创建任务，并确认只能订阅自己的 SSE/WS 事件。

## 基础设施加固清单

- 云安全组：公网只开放 80/443；SSH 仅允许固定运维 IP；数据库、Redis、后端、前端容器端口仅内网可达。
- TLS：使用腾讯云 CLB/证书或 Nginx 终止 HTTPS，启用 TLS 1.2/1.3 和 HSTS。
- 反代：所有应用只经 Nginx 暴露；docs/metrics/admin-only 路径用内网 allowlist 或 VPN 保护。
- Secrets：所有 AK/SK、GitHub token、OpenAI key、provider key 迁移到环境变量或云 Secret Manager；聊天、日志、PR 中出现过的 token 立即轮换。
- Sandbox：避免业务容器直接持有 Docker socket。优先使用独立 sandbox host、rootless runtime、socket proxy 或 gVisor/Kata，并限制网络出站。
- 备份：MySQL 开启自动快照和恢复演练；备份账号最小权限；备份加密。
- 审计：启用 Nginx access log、应用 JSON log、云审计、登录失败告警、异常 5xx/LLM timeout 告警。

## 2026-06 Webhook / Connector P0-P1 加固补充

### 新的默认策略

- `AIOS_ALLOW_INSECURE_WEBHOOKS=false`
  - 缺 secret、缺签名、缺 JWT 的 inbound webhook 默认拒绝。
  - 仅允许在本地或显式调试场景临时打开；生产环境不要启用。
- `ENABLE_API_DOCS=`
  - 留空时，生产环境默认关闭 `/docs`、`/redoc`、`/openapi.json`。
  - 非生产环境默认开启；如果需要强制开启生产 docs，必须显式设为 `true` 并由反代层做 IP/VPN 限制。
- `AIOS_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS=300`
  - workflow webhook 的时间窗校验，默认 300 秒，最小 30 秒。

### workflow webhook 新要求

- 每个 workflow 的 `webhook` trigger 必须单独配置 secret，未配置时不能启用。
- 请求必须携带：
  - `X-AIOS-Timestamp`
  - `X-AIOS-Signature`
- 签名算法：

```text
signature = "sha256=" + HMAC_SHA256(secret, f"{timestamp}.{raw_body}")
```

- 平台会校验：
  - secret 是否存在
  - timestamp 是否在允许时间窗内
  - HMAC 是否匹配
  - 请求是否为 replay

### 升级后的运维动作

1. 检查现有 workflow 中所有 webhook trigger 是否已补 secret。
2. 检查 Feishu / WeChat Work / Teams / WhatsApp 的 webhook secret、token、JWT 配置是否齐全。
3. 验证 connector `send/test` 和 email queue 相关接口是否只对管理员开放。
4. 在生产入口确认 `/docs` `/redoc` `/openapi.json` 不再对公网直接开放。

完整的 rollout 步骤与检查表见：
- [P1 Workflow Webhook Rollout Checklist](./ops/workflow-webhook-rollout.md)
