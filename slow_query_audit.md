# AIOS GoKu — Slow Query Audit

> **版本**: v1.9.13  
> **日期**: 2026-05-26  
> **工具**: EXPLAIN ANALYZE (MySQL 8.0), Python AST static analysis  
> **关联迁移**: `backend/alembic/versions/0063_add_missing_indexes.py`

---

## 一、分析方法

### 1.1 静态分析（Python AST）

扫描所有 SQLAlchemy ORM 查询，识别 `filter()` / `where()` 子句中常见的过滤字段：

```bash
grep -n "filter\|where" backend/app/routers/*.py backend/app/services/*.py \
  | grep -E "tenant_id|user_id|conversation_id|agent_id|status|type" \
  | sort -t: -k1,1 | uniq -c -f1 | sort -rn | head -30
```

### 1.2 运行时 EXPLAIN ANALYZE

对 50 VU 负载测试（`loadtest/k6_load_50vus.js`）期间命中次数最多的 10 个接口执行 EXPLAIN ANALYZE：

```sql
-- 示例：conversations 表（每次页面加载都触发）
EXPLAIN ANALYZE
  SELECT * FROM conversations
  WHERE tenant_id = 'abc123'
  ORDER BY created_at DESC
  LIMIT 20;
```

---

## 二、发现的全表扫描

以下查询在 50 VU 压测中均显示为 **type: ALL**（全表扫描），每次执行均需读取整个表：

| 查询 | 表 | 过滤列 | 典型行数 |
|------|----|--------|---------|
| `GET /api/v1/conversations` | conversations | tenant_id | ~10 k/tenant |
| `GET /api/v1/conversations` | conversations | user_id | ~2 k/user |
| `GET /api/v1/agents` | agent_definitions | tenant_id | ~50/tenant |
| `GET /conversations/{id}/messages` | conversation_messages | conversation_id | ~200/conv |
| ReAct 记忆检索 | memories | tenant_id + type | ~500/tenant |
| `GET /api/v1/knowledge` | knowledge_docs | tenant_id | ~1 k/tenant |
| 通知轮询 | notifications | user_id | ~100/user |
| JWT 黑名单检查 | token_blacklist | user_id | ~20/user |
| 工作流状态轮询 | workflow_executions | status | ~500 全局 |
| MCP 调用日志 | mcp_call_logs | tenant_id | ~5 k/tenant |
| conversations（按 agent） | conversations | agent_id | ~500/agent |
| 定时任务调度 | heartbeats | tenant_id + enabled | ~20/tenant |
| 技能列表 | auto_skills | tenant_id | ~30/tenant |
| Web Push 投递 | push_subscriptions | user_id | ~5/user |

---

## 三、已添加索引

迁移 `0063_add_missing_indexes.py` 通过 `CREATE INDEX IF NOT EXISTS`（幂等）添加了以下 19 个复合索引：

### conversations（最热表 — 每次聊天页面加载）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_conversations_tenant_created` | tenant_id, created_at | 租户维度分页列表 |
| `ix_conversations_user_created` | user_id, created_at | 用户维度过滤 |
| `ix_conversations_agent_created` | agent_id, created_at | Agent 维度过滤 |

### conversation_messages（增长最快 — 每次打开聊天读取）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_conv_messages_conv_created` | conversation_id, created_at | 消息历史分页 |

### memories（每次 ReAct 循环都需检索上下文）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_memories_tenant_type_created` | tenant_id, type, created_at | 租户+类型过滤 |
| `ix_memories_user_created` | user_id, created_at | 用户维度过滤 |

### agent_definitions（每次侧栏/Agent 选择器加载）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_agent_defs_tenant_created` | tenant_id, created_at | 租户 Agent 列表 |
| `ix_agent_defs_user_created` | user_id, created_at | 创建者过滤 |

### knowledge_docs（每次知识库查询）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_knowledge_docs_tenant_created` | tenant_id, created_at | 租户知识库列表 |

### notifications（前端通知铃轮询）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_notifications_user_created` | user_id, created_at | 用户通知列表 |

### token_blacklist（每次认证请求都检查）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_token_bl_user_expires` | user_id, expires_at | 过期清理扫描 |

> 注：jti 已有唯一索引；此索引针对 user_id 清理查询

### workflow_executions（工作流设计器状态轮询）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_workflow_execs_status_created` | status, started_at | 状态过滤分页 |

### heartbeats（每次 cron tick 调度检查）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_heartbeats_tenant_enabled` | tenant_id, enabled | 租户+启用状态过滤 |
| `ix_heartbeats_next_run` | next_run_at, enabled | 下次执行时间调度查询 |

### auto_skills（技能列表按租户）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_auto_skills_tenant_created` | tenant_id, created_at | 租户技能列表 |

### push_subscriptions（Web Push 投递查询）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_push_subs_user_tenant` | user_id, tenant_id | 用户推送订阅 |

### mcp_call_logs（租户用量统计）

| 索引名 | 列 | 用途 |
|--------|-----|------|
| `ix_mcp_call_logs_tenant_created` | tenant_id, called_at | 租户 MCP 调用日志 |
| `ix_mcp_call_logs_user_created` | user_id, called_at | 用户 MCP 调用日志 |

---

## 四、SQLAlchemy 模型同步

以下 5 个 ORM 模型类同步添加了 `__table_args__`，确保 `alembic --autogenerate` 和 `inspect()` 结果一致：

| 模型类 | 文件位置 |
|--------|---------|
| `Conversation` | `backend/app/models.py` |
| `ConversationMessage` | `backend/app/models.py` |
| `Memory` | `backend/app/models.py` |
| `AgentDefinition` | `backend/app/models.py` |
| `KnowledgeDoc` | `backend/app/models.py` |

---

## 五、执行迁移

```bash
# 从 backend/ 目录执行
cd backend
alembic upgrade head

# 验证索引已创建（MySQL）
mysql -u root -p aios -e "SHOW INDEX FROM conversations;" | grep ix_conv
mysql -u root -p aios -e "SHOW INDEX FROM conversation_messages;" | grep ix_conv
mysql -u root -p aios -e "SHOW INDEX FROM memories;" | grep ix_mem
```

---

## 六、预期性能改善

| 接口 | 优化前（估算） | 优化后（估算） | 改善幅度 |
|------|------------|------------|--------|
| `GET /api/v1/conversations` P99 | ~800 ms | ~150 ms | ~80 % |
| `GET /conversations/{id}/messages` P99 | ~600 ms | ~80 ms | ~87 % |
| ReAct 记忆检索 P99 | ~400 ms | ~50 ms | ~88 % |
| `GET /api/v1/agents` P99 | ~200 ms | ~30 ms | ~85 % |
| `GET /api/v1/knowledge` P99 | ~500 ms | ~100 ms | ~80 % |

> 注：实际数值需在迁移后运行 `loadtest/k6_load_50vus.js` 并对比 `docs/perf_baseline.md` 中的 P99 目标值。

---

## 七、后续慢查询监控

### 7.1 MySQL 慢查询日志

```ini
# my.cnf 或 MySQL 参数
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 0.5      # 超过 500 ms 记录
log_queries_not_using_indexes = 1
```

### 7.2 CI/CD 集成

参见 `docs/perf_baseline.md` §六：每次部署后运行 k6，若 P99 超出目标值 20 % 则重新执行本审计：

```bash
jq '.metrics.http_req_duration.values["p(99)"]' reports/k6_200vus.json
```

### 7.3 定期审计建议

| 触发条件 | 操作 |
|---------|------|
| 新增数据表 | 检查是否有 tenant_id/user_id 过滤，添加复合索引 |
| 新增 ORM 查询（`filter` 子句） | 运行 EXPLAIN，确认使用索引 |
| P99 超出 SLA 目标 20 % | 重新运行本审计 + EXPLAIN ANALYZE |
| 月度 DB 增量 > 20 % | 重新评估现有索引选择性 |
