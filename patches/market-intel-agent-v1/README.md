# 商机情报员 Patch — v1

## 为什么部署后没有这个 Agent？

根因是**双重遗漏**：

| 问题 | 说明 |
|------|------|
| **代码层：agent type 未注册** | `backend/app/agent/subagent_config.py` 的 `SUBAGENT_TYPES` 里没有 `market_intel_agent` 条目。AIOS API 的 `POST /api/v1/agents` 会校验 `agent_type` 必须在注册列表中，否则返回 `400 Unknown base agent type`。所以即使手动在 UI 里创建也会失败。 |
| **数据层：没有 seed 记录** | `db/seed_data.sql` 里只 seed 了 tools/roles/plugins 等，`agent_definitions` 表从不 seed。对应的 agent_definition.json 只有 `bank-reconciliation-agent` 有打包，`商机情报员` 一直缺失。 |

**本 patch 包含**：
1. 代码修复（已提交到 GitHub main）：在 `subagent_config.py` 注册 `market_intel_agent` 类型
2. `agent/agent_definition.json`：完整 agent 定义，可通过 API 导入
3. `skills/baiwu-opportunity-intelligence/`：SKILL.md + 11 个 references 文件（product map、buyer maps、search playbook、quality gate 等）
4. `deploy.py`：一键部署脚本

---

## 部署步骤

### 前提条件

**后端必须先更新**。本次代码修复已合并到 `main` 分支（commit `feat(agent): register market_intel_agent type`）。如果你的部署镜像是这个 commit 之前的版本，需先重新拉取并重新部署后端。

验证方法：
```bash
# 调用 agent types 端点，确认 market_intel_agent 出现在列表里
curl -sH "Authorization: Bearer <token>" https://aios.example.com/api/v1/agents/types | grep market_intel
```

### 一键部署

```bash
# 安装依赖
pip install requests

# 获取管理员 JWT（从 AIOS 登录界面或数据库）
export TOKEN="eyJ..."

# 运行 patch deployer
python deploy.py \
  --host https://aios.example.com \
  --token "$TOKEN"

# 多租户环境，指定 tenant_id
python deploy.py \
  --host https://aios.example.com \
  --token "$TOKEN" \
  --tenant-id <tenant_uuid>
```

### 手动导入（备用方案）

如果 deploy.py 无法使用，可以手动通过 API：

```bash
curl -X POST https://aios.example.com/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @agent/agent_definition.json
```

或通过 AIOS UI：**Agent Management → 导入 → 选择 `agent/agent_definition.json`**

---

## Agent 能力说明

| 项目 | 内容 |
|------|------|
| **agent_type** | `market_intel_agent` |
| **核心工具** | `baiwu_daily_report`（结构化日报，覆盖运营商/银行/金融科技/采购/竞对）|
| **辅助工具** | `web_search` / `web_fetch` / `browser_action`（深挖单条线索）|
| **情报工具** | `send_market_report`（市场信号）/ `knowledge_search`（历史线索）|
| **max_steps** | 30（日报模式需要多轮搜索）|
| **timeout** | baiwu_daily_report 单次最长 900s |
| **并发** | max_concurrent=3，queue=5，queue_timeout=900s |

### 绑定的 Skill

`baiwu-opportunity-intelligence` — 定义了完整的搜索策略、来源优先级、线索资格判断框架、质量门槛，以及百悟产品线映射、中国运营商/银行分支地图、竞对分析框架。

---

## 验证清单

部署完成后，在 AIOS UI 里：

- [ ] **Agent Management** → 搜索"商机情报员"，确认 agent 存在且状态为 Active
- [ ] **工具列表** → 确认 `baiwu_daily_report` 在 allowed_tools 里
- [ ] **创建任务** → 输入「生成今日商机日报」，确认 agent 正常执行 `baiwu_daily_report`
- [ ] **邮件发送**（可选）→ 在任务里传入 `email_to` 参数，确认日报邮件正常发送

---

## Patch 文件清单

```
patches/market-intel-agent-v1/
├── README.md                          ← 本文件
├── deploy.py                          ← 一键部署脚本
├── agent/
│   └── agent_definition.json          ← 完整 agent 定义
└── skill-refs/
    └── baiwu-opportunity-intelligence/
        ├── SKILL.md                   ← 主 Skill 文件（触发条件、工具序列、reasoning rules）
        └── references/
            ├── baiwu-product-map.md         ← 百悟产品线详细映射
            ├── china-bank-branch-map.md     ← 银行/分支行买方池地图
            ├── china-operator-tender-map.md ← 三大运营商招标来源地图
            ├── competitor-landscape.md      ← 梦网科技 & Twilio 竞对分析框架
            ├── fintech-collections-map.md   ← 金融科技/催收/外呼买方池
            ├── opportunity-qualification.md ← 线索资格判断 9 维度框架
            ├── query-matrix.md              ← 查询矩阵（搜索词 × 产品线 × 买方类型）
            ├── report-quality-gate.md       ← 报告质量门控规则
            ├── report-template.md           ← 商机日报标准模板
            ├── search-playbook.md           ← 多轮搜索执行序列
            └── source-directory.md          ← 权威来源目录（优先/次级/禁用）
```
