# 0009 · MySQL 8 外键 Collation 不兼容（error 3780）

**日期**：2026-05-30
**版本**：v1.9.15（migration 0070）
**影响范围**：新迁移文件中含 FK 约束的建表语句

---

## 症状

`./start.sh` 时迁移报错，应用无法正常完成 DB 升级：

```
pymysql.err.OperationalError: (3780, "Referencing column 'tenant_id' and referenced
column 'id' in foreign key constraint 'channel_accounts_ibfk_1' are incompatible.")
```

---

## 根本原因

数据库存在 **collation 双轨**：

| 来源 | Collation |
|------|-----------|
| 旧表（tenants / users / conversations / tasks）的 `id` 列 | `utf8mb4_unicode_ci` |
| 数据库 DEFAULT collation | `utf8mb4_0900_ai_ci` |

MySQL 8.0.17+ 要求 FK 两端列的字符集和 collation **完全一致**。
`alembic` 生成的 `sa.String(36)` 没有显式指定 collation，新列继承 DB 默认值 `utf8mb4_0900_ai_ci`，与旧表 PK 的 `utf8mb4_unicode_ci` 不一致 → 报 3780。

---

## 修复方案

在所有 `op.create_table()` 调用中加入表级 MySQL 选项：

```python
_MYSQL_OPTS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

op.create_table(
    "my_new_table",
    sa.Column("id",        sa.String(36), nullable=False),
    sa.Column("user_id",   sa.String(36), nullable=False),
    sa.Column("tenant_id", sa.String(36), nullable=True),
    ...
    sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    sa.PrimaryKeyConstraint("id"),
    **_MYSQL_OPTS,   # ← 显式指定 collation，覆盖 DB 默认值
)
```

`tenant_id` 不加 FK（只加索引）：`tenant_id` 是分区/隔离键，索引已满足查询需求，不需要强制 FK 约束。

---

## 防复发规则

**凡新建迁移且建表中有 FK 约束，必须在 `op.create_table()` 末尾加：**

```python
mysql_charset="utf8mb4",
mysql_collate="utf8mb4_unicode_ci",
```

或统一用 `_MYSQL_OPTS = {...}` 展开，保持一致。

---

## 关联文件

- `backend/alembic/versions/0070_unicall_channel_gateway.py` — 修复示例
- `docs/复盘记录/0003-tasks-status-enum-case.md` — 类似的迁移定义规范问题
