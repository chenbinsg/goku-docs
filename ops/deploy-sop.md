# AIOS GoKu — 部署 SOP（Standard Operating Procedure）

> **适用版本**: v1.9.x+  
> **更新日期**: 2026-05-26  
> **适用场景**: 首次生产部署、新环境初始化

---

## 一、前置检查清单

在执行任何部署前，确认以下条件全部满足（✅ = 已确认）：

```
[ ] 1. 代码已合并至 main，CI 全绿（所有测试通过）
[ ] 2. .env 文件已配置：DATABASE_URL, SECRET_KEY, OPENAI_API_KEY
[ ] 3. MySQL 8.0 数据库实例可达，已创建目标 DB（aios）
[ ] 4. 服务器内存 ≥ 4 GB（500 VU 压测环境 ≥ 8 GB）
[ ] 5. 端口 8106（后端）、5106（前端）、3306（MySQL）已开放
[ ] 6. （可选）Redis 6+ 实例可达（多 worker 部署必需）
[ ] 7. （可选）Qdrant 实例可达（知识库向量搜索必需）
```

---

## 二、方案 A：Docker Compose 部署（推荐单机/测试环境）

### 2.1 环境配置

```bash
# 克隆仓库
git clone https://github.com/your-org/agent.git
cd agent

# 复制并编辑环境变量
cp .env.example .env
vim .env   # 至少填写 DATABASE_URL, SECRET_KEY, OPENAI_API_KEY
```

`.env` 最小配置：

```dotenv
DATABASE_URL=mysql+pymysql://aios:strongpassword@db:3306/aios
SECRET_KEY=your-64-char-hex-key   # openssl rand -hex 32
OPENAI_API_KEY=sk-...
REDIS_URL=redis://redis:6379/0    # 多 worker 必填
```

### 2.2 启动服务

```bash
# 构建并启动所有容器（后台模式）
docker compose up -d --build

# 查看启动日志
docker compose logs -f backend
```

`docker compose up` 会自动执行：
1. MySQL 数据库初始化
2. `alembic upgrade head`（所有迁移）
3. `python scripts/seed_agents.py`（Agent 种子数据）
4. uvicorn 后端（port 8106）
5. Vite 前端（port 5106）

### 2.3 验证部署

```bash
# 健康检查
curl -sf http://localhost:8106/health | jq .

# 期望响应
{
  "status": "ok",
  "version": "1.9.13",
  "db": "connected",
  "redis": "connected"
}

# 前端可访问
curl -sf http://localhost:5106 | head -5
```

### 2.4 停止服务

```bash
docker compose down          # 保留数据卷
docker compose down -v       # 删除数据卷（谨慎！会清空数据库）
```

---

## 三、方案 B：Kubernetes / Helm 部署（生产集群）

### 3.1 前置要求

- Kubernetes 1.26+
- Helm 3.12+
- Ingress Controller（nginx-ingress 推荐）
- Persistent Volume（MySQL 数据卷，≥ 20 Gi）
- Kubernetes Secret 已创建（见 3.2）

### 3.2 创建 Secrets

```bash
kubectl create namespace aios

kubectl create secret generic aios-env \
  --namespace aios \
  --from-literal=DATABASE_URL="mysql+pymysql://aios:pass@mysql:3306/aios" \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=OPENAI_API_KEY="sk-..." \
  --from-literal=REDIS_URL="redis://redis-master:6379/0"
```

### 3.3 Helm 安装

```bash
# 添加 AIOS Helm Chart（假设在本地 charts/ 目录）
helm install aios ./charts/aios \
  --namespace aios \
  --set image.tag=1.9.13 \
  --set backend.replicas=3 \
  --set frontend.replicas=2 \
  --set ingress.host=aios.example.com \
  --set ingress.tls.enabled=true
```

**关键 Chart 参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `image.tag` | `latest` | 后端/前端镜像 tag |
| `backend.replicas` | `2` | 后端 Pod 副本数 |
| `backend.resources.requests.memory` | `512Mi` | Pod 内存下限 |
| `backend.resources.limits.memory` | `2Gi` | Pod 内存上限 |
| `db.pool_size` | `20` | SQLAlchemy 连接池大小 |
| `db.max_overflow` | `40` | 连接池溢出上限 |
| `redis.enabled` | `true` | 启用 Redis SSE Pub/Sub |

### 3.4 验证 K8s 部署

```bash
# 检查 Pod 状态
kubectl get pods -n aios

# 查看后端日志
kubectl logs -n aios -l app=aios-backend --tail=50

# 端口转发测试
kubectl port-forward -n aios svc/aios-backend 8106:8106
curl http://localhost:8106/health | jq .
```

---

## 四、首次部署后验证

```bash
# 1. 数据库迁移状态
cd backend && alembic current
# 期望输出: <revision_id> (head)

# 2. Agent 种子数据
curl -H "Authorization: Bearer $TOKEN" http://localhost:8106/api/v1/agents | jq length
# 期望: ≥ 1（至少有默认 Agent）

# 3. 冒烟压测（无 TOKEN 校验的健康端点）
k6 run loadtest/k6_smoke.js -e BASE_URL=http://localhost:8106 -e TOKEN=dummy

# 4. 日志无 ERROR
docker compose logs backend 2>&1 | grep -c ERROR
# 期望: 0
```

---

## 五、常见问题

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| 后端启动后立即退出 | `DATABASE_URL` 格式错误或 DB 不可达 | 检查 `.env`，确认 MySQL 可连接 |
| `alembic upgrade` 报 `Can't locate revision` | `down_revision` 不连续 | `alembic history` 查看链路 |
| SSE 事件不到达 | 多 worker 但无 Redis | 设置 `REDIS_URL` 或改为单 worker |
| 前端显示 502 | 后端未启动 | `docker compose logs backend` 排查 |
| 知识库搜索返回空 | Qdrant 未配置 | 设置 `QDRANT_URL`，或忽略（BM25 仍工作） |
