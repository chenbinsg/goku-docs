# [0003] tasks.status enum 大小写错误导致心跳任务连续失败

> **首次发现**：2026-05-27  
> **最近出现**：2026-05-27  
> **状态**：✅ 已修复（Migration 0059 已合并）  
> **关键词**：enum, migration, TaskStatus, heartbeat, agent_probe_daily, PENDING

---

## 症状

```
心跳任务连续失败 5 次
任务名称：agent_probe_daily
错误信息：'pending' is not among the defined enum values.
Enum name: taskstatus. Possible values: PENDING, PLANNING, EXECUTING...
```

心跳告警邮件发到 ALERT_EMAIL_TO，任务彻底无法创建。

---

## 根本原因

Migration `0047_baseline_schema.py` 建表时用了**大写** enum 值：

```sql
sa.Column('status', sa.Enum('PENDING', 'PLANNING', 'EXECUTING', ...))
```

但 Python `TaskStatus` 枚举的值是**小写**：

```python
class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    PLANNING = "planning"
```

MySQL 拒绝写入 `"pending"`（DB 只接受 `"PENDING"`）→ 所有 task 创建失败。

---

## 修复方案

Migration `0059_fix_taskstatus_enum_case.py`：

```python
def upgrade():
    op.execute("ALTER TABLE tasks MODIFY COLUMN status VARCHAR(50)")
    op.execute("UPDATE tasks SET status = LOWER(status) WHERE status != LOWER(status)")
    op.execute("ALTER TABLE tasks MODIFY COLUMN status ENUM('pending','planning',...)")
```

---

## 防复发机制

- Migration 已合并到主干
- 生产环境部署前必须运行 `alembic upgrade head`（`make deploy` / `docker-compose up db-migrate`）

---

## 关联文件

- `backend/alembic/versions/0047_baseline_schema.py` — 问题来源
- `backend/alembic/versions/0059_fix_taskstatus_enum_case.py` — 修复 migration
- `backend/app/models.py` — `TaskStatus` 枚举定义
- `backend/app/tasks/heartbeat.py` — 心跳任务执行与告警逻辑

---

## 教训

> **建表 migration 中的 Enum 值必须与 Python 枚举的 `.value`（非 `.name`）完全一致；上线前用 `alembic check` 验证 schema 是否与 ORM 模型同步。**
