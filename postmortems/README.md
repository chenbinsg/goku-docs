# 复盘记录 — 使用说明

本目录收录所有**反复出现或影响较大的问题**的根本原因分析与修复记录。

## 作用

| 受益方 | 用途 |
|--------|------|
| **Claude Code（AI 编程助手）** | 每次修改代码前读取，避免重蹈覆辙 |
| **AIOS Supervisor（自主演进）** | 作为长期记忆，识别重复模式，自动生成新条目 |
| **开发者** | 快速定位已知问题，查阅历史修复方案 |

## 自动生成机制

`backend/app/services/supervisor.py` 每天（由 Optimizer 日批次驱动）会：

1. 扫描过去 30 天内所有 `trigger_reason=FAILED` 的 `ImprovementProposal` 记录
2. 调用 LLM 聚类，找出 **3 条以上同根因** 的问题簇
3. 对每个新问题簇，自动生成结构化复盘文档写入本目录（`NNNN-slug.md`）
4. 更新下方的索引表

自动生成的条目状态标记为 **🔄 观察中**，需人工确认后改为 **✅ 已修复**。

相关代码：
- `backend/app/services/supervisor.py` — `scan_and_write_postmortems()`
- `backend/app/services/optimizer.py` — `run_optimizer_batch()` 末尾触发

## 触发规则

> **任何涉及以下模块的修改，必须先读本目录所有 `.md` 文件：**
> - Agent 头像 / 图标 / figure_url / icon 字段
> - LLM 健康检查 / 状态显示
> - 数据库 enum / migration
> - sync_builtin_packages / seed 脚本
> - workspace / uploads / icons 目录

## 文件命名规范

```
NNNN-kebab-case-title.md
```

- `NNNN`：4 位流水号（0001, 0002 …）
- 标题用英文 kebab-case，便于 grep

## 记录模板

```markdown
# [NNNN] 标题

> **首次发现**：YYYY-MM-DD
> **最近出现**：YYYY-MM-DD
> **状态**：✅ 已修复 / 🔄 观察中 / ❌ 未解决
> **关键词**：tag1, tag2

## 症状
用户看到什么现象。

## 根本原因
技术层面的真实原因（可多条）。

## 排查路径
如何一步步定位到根本原因。

## 修复方案
改了什么文件、什么逻辑。

## 防复发机制
代码层面或流程层面如何保证不再发生。

## 关联文件
- `path/to/file.py` — 说明

## 教训
一句话总结核心教训，供快速检索。
```

## 索引

| 编号 | 标题 | 状态 | 关键词 |
|------|------|------|--------|
| [0001](0001-agent-avatar-persistence.md) | Agent 头像持久化 | ✅ 已修复 | avatar, figure_url, icon, workspace, slug, sync |
| [0002](0002-llm-health-status-wrong-env.md) | LLM 状态显示不准 | ✅ 已修复 | llm, health, OPENAI_BASE_URL, OPENROUTER |
| [0003](0003-tasks-status-enum-case.md) | tasks.status enum 大小写错误 | ✅ 已修复 | enum, migration, TaskStatus, heartbeat |
| [0004](0004-left-panel-menu-items-inconsistent.md) | 左侧菜单项显示不一致 | ✅ 已修复 | menu, permissions, sessionStorage, SSO, usePermissions |
| [0005](0005-llm-health-runtime-env-drift.md) | LLM 状态变红——运行时 env 漂移 | ✅ 已修复 | llm, health, os.environ, runtime-drift, snapshot |
| [0006](0006-sidebar-rbac-leak-chat-page.md) | 非管理员进入 AI 对话页见到全部管理员菜单 | ✅ 已修复 | rbac, permissions, sidebar, ChatLayout, CollapsibleSidebar |
| [0007](0007-goku-router-no-guardian-process.md) | Goku-Router 无守护进程 | ✅ 已修复 | router, process, guardian |
| [0008](0008-vdi-extracted-to-vds-app.md) | VDI 批处理模块从 AIOS 提取到 VDS-App | ✅ 已完成 | vdi, extraction, vds-app, migration, sidebar |
| [0009](0009-mysql8-fk-collation-mismatch.md) | MySQL 8 外键 Collation 不兼容（error 3780） | ✅ 已修复 | mysql, collation, fk, migration, utf8mb4 |
