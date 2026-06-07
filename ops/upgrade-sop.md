# AIOS GoKu — 升级 SOP（Standard Operating Procedure）

> **适用版本**: v1.9.x → v1.9.y（小版本升级）  
> **更新日期**: 2026-05-26  
> **适用场景**: 已有生产环境的版本升级

---

## 一、升级前检查清单

```
[ ] 1. 已阅读目标版本的 release notes（docs/release-notes-v*.md）
[ ] 2. 已备份数据库（见 §二）
[ ] 3. 已确认新版本的 ENV 变量变更（对比 .env.example diff）
[ ] 4. 维护窗口已通知用户（建议：低峰期 UTC 02:00–04:00）
[ ] 5. 回滚方案已准备（见 docs/ops/rollback-sop.md）
[ ] 6. CI 全绿，目标分支已打 tag（vX.Y.Z）
[ ] 7. 若本次版本包含 webhook 安全加固，已完成 docs/ops/workflow-webhook-rollout.md 中的 secret/签名联调
```

---

## 二、升级前备份

### 2.1 数据库备份

```bash
# 方式 A：mysqldump（简单，适合 <10 GB）
mysqldump -u root -p \
  --single-transaction \
  --routines \
  --triggers \
  aios > /backup/aios_$(date +%Y%m%d_%H%M%S).sql

# 方式 B：xtrabackup（物理备份，适合大库）
xtrabackup --backup --target-dir=/backup/aios_xtra_$(date +%Y%m%d)

# 验证备份文件非空
ls -lh /backup/aios_*.sql | tail -1
```

### 2.2 记录当前版本信息

```bash
# 记录当前代码版本
cat VERSION  # 例：1.9.12

# 记录当前迁移头
cd backend && alembic current
# 例：0062 (head)

# 保存到升级日志
echo "$(date) | pre-upgrade | version=$(cat ../VERSION) | alembic=$(alembic current)" \
  >> /var/log/aios/upgrade.log
```

---

## 三、方案 A：Docker Compose 升级

```bash
# 1. 拉取新代码
cd /opt/agent
git fetch origin
git checkout v1.9.13   # 目标 tag

# 2. 检查 .env 是否需要新变量
diff .env.example .env | grep "^<"   # 只在 .env.example 中存在的行

# 2.1 如果版本包含 webhook 安全加固，补齐新变量
# AIOS_ALLOW_INSECURE_WEBHOOKS=false
# AIOS_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS=300
# ENABLE_API_DOCS=   # 生产环境默认留空或 false

# 3. 停止当前服务（保留 DB 容器）
docker compose stop backend frontend

# 4. 拉取新镜像 / 重新构建
docker compose build --no-cache backend frontend

# 5. 运行数据库迁移（单独容器，不影响其他服务）
docker compose run --rm backend alembic upgrade head

# 6. 刷新 Agent 种子数据（幂等，安全重复执行）
docker compose run --rm backend python scripts/seed_agents.py

# 7. 启动新版本服务
docker compose up -d backend frontend

# 8. 观察日志 60 秒
docker compose logs -f backend --since 1m
```

---

## 四、方案 B：Kubernetes / Helm 升级

```bash
# 1. 更新镜像 tag（触发滚动更新）
helm upgrade aios ./charts/aios \
  --namespace aios \
  --set image.tag=1.9.13 \
  --wait \               # 等待所有 Pod Ready
  --timeout 5m

# 2. 监控滚动更新进度
kubectl rollout status deployment/aios-backend -n aios

# 3. 迁移（Job 方式，确保只运行一次）
kubectl apply -f charts/aios/templates/migration-job.yaml
kubectl wait --for=condition=complete job/aios-migrate -n aios --timeout=120s
kubectl logs -n aios job/aios-migrate

# 4. 种子数据刷新（Job 方式）
kubectl apply -f charts/aios/templates/seed-job.yaml
kubectl wait --for=condition=complete job/aios-seed -n aios --timeout=60s
```

---

## 五、升级后验证

执行以下所有检查，全部通过后方可关闭维护窗口：

```bash
# 1. 健康检查
curl -sf http://localhost:8106/health | jq .
# 期望：version 字段为新版本号，db/redis 均为 connected

# 2. 迁移状态
cd backend && alembic current
# 期望：(head)

# 3. 核心功能冒烟
k6 run loadtest/k6_smoke.js \
  -e BASE_URL=http://localhost:8106 \
  -e TOKEN=$TOKEN
# 期望：0% errors，所有 checks 通过

# 4. 50 VU 快速基准（可选，约 7 分钟）
k6 run loadtest/k6_load_50vus.js \
  -e BASE_URL=http://localhost:8106 \
  -e TOKEN=$TOKEN \
  -e CONV_ID=$CONV_ID \
  --out json=reports/k6_50vus_post_upgrade.json

# 5. 对比 P99（应 ≤ 升级前基准 × 1.2）
jq '.metrics.http_req_duration.values["p(99)"]' \
  reports/k6_50vus_post_upgrade.json

# 6. 日志错误率
docker compose logs backend --since 10m 2>&1 | grep -c "ERROR\|CRITICAL"
# 期望：0 或与升级前持平
```

---

## 六、数据库迁移注意事项

### 6.1 零停机迁移原则

AIOS 迁移遵循「先加后减」原则，以支持蓝绿部署：

| 操作 | 安全性 | 处理方式 |
|------|--------|---------|
| 新增列（有默认值或可空） | ✅ 安全 | 直接迁移，旧代码兼容 |
| 新增索引 | ✅ 安全 | `CREATE INDEX IF NOT EXISTS`（幂等） |
| 重命名列 | ⚠️ 危险 | 分两个版本：先加新列，再删旧列 |
| 删除列 | ⚠️ 危险 | 确认无代码引用后执行 |
| 修改列类型 | ⚠️ 危险 | 需要停服窗口 |
| 大表加索引（>10M行） | ⚠️ 慢 | 使用 `pt-online-schema-change` |

### 6.2 大表在线加索引

```bash
# 对超过 1000 万行的表，使用 pt-online-schema-change
pt-online-schema-change \
  --execute \
  --alter "ADD INDEX ix_conversations_tenant_created (tenant_id, created_at)" \
  D=aios,t=conversations
```

### 6.3 手动验证迁移

```bash
# 查看所有已应用迁移
cd backend && alembic history --verbose | head -20

# 验证迁移链完整性
alembic check
```

---

## 七、升级后记录

```bash
echo "$(date) | post-upgrade | version=$(cat ../VERSION) | alembic=$(cd backend && alembic current) | status=ok" \
  >> /var/log/aios/upgrade.log
```
