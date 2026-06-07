# AIOS GoKu — 回滚 SOP（Standard Operating Procedure）

> **适用版本**: v1.9.x  
> **更新日期**: 2026-05-26  
> **适用场景**: 升级后发现严重问题，需要快速回退到前一版本

---

## 一、回滚决策标准

满足以下**任一**条件，立即启动回滚：

| 触发条件 | 参考值 |
|---------|-------|
| 健康检查失败（`/health` 非 200） | 持续 > 2 分钟 |
| 端到端错误率超标 | > 5%（SLA：< 1%）|
| P99 延迟超标 | 只读 API > 3× 基准值 |
| 核心功能不可用 | 发消息 / 查 Agent 持续失败 |
| 数据库连接池耗尽 | `Too many connections` 错误 |
| 内存泄漏 | RSS 在 10 分钟内增长 > 500 MB |

**不应回滚的情况**：仅日志 WARNING 级别；已知的非关键 UI 问题；LLM API 速率限制（非 AIOS 本身问题）。

---

## 二、回滚前信息收集

在回滚前快速采集诊断信息（**目标：2 分钟内完成**）：

```bash
# 当前版本 & 迁移状态
cat VERSION
cd backend && alembic current

# 后端最近 5 分钟错误日志
docker compose logs backend --since 5m 2>&1 | grep -E "ERROR|CRITICAL|Exception" | tail -30

# 系统资源
docker stats --no-stream

# 保存日志供事后分析
docker compose logs backend --since 30m > /tmp/aios_incident_$(date +%Y%m%d_%H%M%S).log
```

---

## 三、方案 A：Docker Compose 回滚

### 3.1 代码回滚

```bash
cd /opt/agent

# 确认回滚目标版本
git log --oneline -5

# 切换到上一个稳定 tag（例如从 v1.9.13 → v1.9.12）
git checkout v1.9.12

# 停止新版本
docker compose stop backend frontend

# 重新构建旧版本镜像（或使用已缓存的）
docker compose build backend frontend
```

### 3.2 数据库迁移回滚

```bash
# 查看迁移历史，确认目标 revision
cd backend && alembic history | head -10
# 输出示例：
# 0063 -> (head): Add missing indexes
# 0062: Add supervisor improvement proposals
# 0061: ...

# 回滚到上一个 revision
alembic downgrade -1

# 或指定具体 revision
alembic downgrade 0062

# 验证回滚成功
alembic current
# 期望：0062
```

> ⚠️ **重要**：只有当新版本迁移包含「不兼容旧代码」的 schema 变更（删列、修改列类型）时才需要 `downgrade`。纯加索引类迁移（如 0063）不影响旧代码，可以**不回滚**数据库。

### 3.3 启动旧版本

```bash
# 启动旧版本服务
docker compose up -d backend frontend

# 等待 30 秒确认健康
sleep 30
curl -sf http://localhost:8106/health | jq .
```

---

## 四、方案 B：Kubernetes / Helm 回滚

### 4.1 快速 Helm 回滚（推荐）

```bash
# 查看 Helm 发布历史
helm history aios -n aios

# 回滚到上一个 revision
helm rollback aios -n aios

# 或指定具体 revision
helm rollback aios 3 -n aios

# 监控回滚进度
kubectl rollout status deployment/aios-backend -n aios
```

### 4.2 数据库 downgrade（如需要）

```bash
# 在一个 Pod 内执行 downgrade
kubectl exec -n aios deployment/aios-backend -- \
  alembic downgrade -1

# 验证
kubectl exec -n aios deployment/aios-backend -- \
  alembic current
```

### 4.3 验证回滚结果

```bash
# 检查镜像 tag 已还原
kubectl get deployment aios-backend -n aios \
  -o jsonpath='{.spec.template.spec.containers[0].image}'

# 健康检查
kubectl port-forward -n aios svc/aios-backend 8106:8106 &
curl -sf http://localhost:8106/health | jq .
kill %1
```

---

## 五、回滚后验证

回滚完成后，必须在 **10 分钟内**完成以下验证：

```bash
# 1. 健康检查
curl -sf http://localhost:8106/health | jq .
# 期望：version 为旧版本号，db/redis = connected

# 2. 迁移状态
cd backend && alembic current
# 期望：旧版本的 head revision

# 3. 冒烟测试
k6 run loadtest/k6_smoke.js \
  -e BASE_URL=http://localhost:8106 \
  -e TOKEN=$TOKEN
# 期望：0% errors

# 4. 关键功能手工验证
#   - 打开聊天页面，发一条消息
#   - 确认 Agent 列表可加载
#   - 确认知识库搜索可用

# 5. 错误率恢复
docker compose logs backend --since 5m 2>&1 | grep -c "ERROR"
# 期望：与升级前持平或更低
```

---

## 六、从备份恢复数据库（最坏情况）

> 仅在 `alembic downgrade` 无法解决数据损坏时使用

```bash
# 停止所有服务（避免写入）
docker compose stop backend

# 找到最新备份
ls -lh /backup/aios_*.sql | tail -3

# 恢复
mysql -u root -p aios < /backup/aios_20260526_020000.sql

# 验证行数（与备份前对比）
mysql -u root -p aios -e "
  SELECT 'conversations' tbl, COUNT(*) n FROM conversations
  UNION SELECT 'memories', COUNT(*) FROM memories
  UNION SELECT 'agent_definitions', COUNT(*) FROM agent_definitions;
"

# 重新启动
docker compose up -d backend
```

---

## 七、事后分析（Post-Mortem）

回滚完成后 **24 小时内**完成事后分析，记录到 `docs/incidents/` 目录：

```markdown
# Incident Report — v1.9.XX Rollback

**日期**: YYYY-MM-DD  
**持续时间**: XX 分钟  
**影响范围**: 全量用户 / 部分租户  

## 根因
...

## 时间线
- HH:MM 升级开始
- HH:MM 发现问题（症状描述）
- HH:MM 启动回滚
- HH:MM 服务恢复

## 改进措施
- [ ] 在 staging 环境增加此场景的测试覆盖
- [ ] 更新 pre-upgrade 检查清单
```

---

## 八、快速参考卡（撕下来贴在屏幕旁）

```
=== AIOS 紧急回滚速查 ===

Docker Compose:
  git checkout <上一个tag>
  docker compose stop backend frontend
  alembic downgrade -1  （仅 schema 变更需要）
  docker compose up -d backend frontend
  curl http://localhost:8106/health

Kubernetes:
  helm rollback aios -n aios
  kubectl rollout status deployment/aios-backend -n aios

验证:
  curl http://localhost:8106/health | jq .version
  k6 run loadtest/k6_smoke.js -e BASE_URL=... -e TOKEN=...
```
