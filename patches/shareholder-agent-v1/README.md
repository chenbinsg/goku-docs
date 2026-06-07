# 股东会组织助理 Patch — v1

## 为什么部署后没有这个 Agent？

根因与商机情报员**不同**，这里只有数据层问题：

| 问题 | 说明 |
|------|------|
| **Agent 记录未 seed** | `event_agent` 类型已注册（代码层无问题），但这个 agent 的数据库记录只存在于 dev 环境，从未进入 `db/seed_data.sql`，全新部署的 DB 里没有它 |
| **Migration 静默失效** | `db/migrations/2026_05_04_shareholder_assistant_tools.sql` 用 `UPDATE WHERE id=d4b49ecc...`，在空 DB 上影响 0 行，没有任何报错。本 patch 已将其修复为 `INSERT ... ON DUPLICATE KEY UPDATE` |
| **路由逻辑依赖它存在** | `backend/app/routers/conversations.py` 里的 `_auto_bind_by_business_intent()` 按名字查找「股东会组织助理」来自动绑定 IR 事件请求。agent 不存在时自动绑定静默失败 |

**影响链**：用户在会话里说「组织股东会邀请」→ 系统找不到 agent → 自动绑定失败 → 任务被分配给通用 agent → IR 专用工具（`ira_*`）不可用 → 任务失败或返回错误答案

---

## 本 patch 包含的修复

1. **`db/migrations/2026_05_04_shareholder_assistant_tools.sql`**（已更新到 GitHub main）
   - 改为 `INSERT ... ON DUPLICATE KEY UPDATE`
   - 全新部署可直接运行此 migration 创建 agent
   - 已有 agent 的部署运行后会更新 tools/skills 到最新版本

2. **`agent/agent_definition.json`** — 完整 agent 定义（可通过 API 直接导入）

3. **`deploy.py`** — 一键部署脚本（支持新建 + 存量检查 + 强制更新）

---

## Agent 完整规格

| 项目 | 值 |
|------|----|
| **id（固定）** | `d4b49ecc-c254-4ca8-b5bc-a1c6250cb109` |
| **agent_type** | `event_agent` |
| **icon** | `CalendarOutlined` / `#c41d7f` |
| **max_steps** | 20 |
| **tools** | 28 个 ira_* 工具 + email_send + calendar_event + outlook_calendar |
| **skills** | 18 个（见下表） |

### Skills 清单（18 个）

| 分类 | Skills |
|------|--------|
| 活动核心 | `ir_event_planning`, `participant_coordination`, `event_progress_reporting`, `event_followup_report` |
| 邮件 | `email_template_management`, `email_campaign_management` |
| 投资者管理 | `investor_management`, `investor_grouping`, `bulk_investor_import`, `vip_investor_prioritization` |
| 沟通记录 | `communication_logging`, `follow_up_task_management` |
| 材料 & 合规 | `material_management`, `compliance_guardrail`, `approval_workflow`, `audit_logging` |
| 协作 | `teams_notification`, `meeting_scheduling` |

---

## 部署步骤

### 方案 A：运行 migration SQL（推荐，适合有 DB 访问权限的运维）

```bash
# 全新部署 -- 创建 agent
mysql -u root -p$DB_PASS aios \
  < db/migrations/2026_05_04_shareholder_assistant_tools.sql

# 验证
# 应显示 tool_count=28, skill_count=18
```

### 方案 B：deploy.py 脚本（适合只有 API 访问权限的场景）

```bash
pip install requests

# 检查 + 新建（如不存在）
python patches/shareholder-agent-v1/deploy.py \
  --host https://aios.example.com \
  --token "$ADMIN_JWT"

# 存量实例强制更新 tools/skills 到最新版本
python patches/shareholder-agent-v1/deploy.py \
  --host https://aios.example.com \
  --token "$ADMIN_JWT" \
  --force-patch
```

### 方案 C：UI 手动导入

AIOS UI → Agent Management → 导入 → 选择 `agent/agent_definition.json`

---

## 验证清单

- [ ] Agent Management 里能搜到「股东会组织助理」，状态 Active
- [ ] agent_type 显示为「活动组织Agent」
- [ ] tools 数量为 28，skills 数量为 18
- [ ] 在会话里输入「为Q3业绩说明会发送股东邀请邮件」，确认自动绑定到此 agent
- [ ] `ira_create_event` / `ira_queue_bulk_emails` / `ira_send_email_queue` 工具可正常调用
