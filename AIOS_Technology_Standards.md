# AIOS 综合技术标准

**版本**: V1.6（综合版）  
**发布日期**: 2026-06-02  
**适用系统**: AIOS v1.7.0+  
**文档状态**: 正式发布

> 本文档由以下三份独立标准合并而成：  
> — 《智能体 Agent 相关企业技术标准》V1.3  
> — 《MCP 服务器接入技术标准》V1.4  
> — 《AIOS Tool Package Specification》V1.1.0  

---

## 目录

### Part A — Agent 技术标准
1. [SubAgent 技术标准](#一-subagent-技术标准)
2. [Agent 并发与调度标准](#二-agent-并发与调度标准)
3. [Agent Tools 技术标准](#三-agent-tools-技术标准)
4. [Agent 安全与审计标准](#四-agent-安全与审计标准)
5. [LLM 上下文 Token 预算管理标准](#五-llm-上下文-token-预算管理标准)
6. [提示词 / 工具 / Skills 三级规模标准](#六-提示词--工具--skills-三级规模标准)
7. [Agent 基础类型命名规范](#七-agent-基础类型命名规范)
8. [开放 API 技术标准](#八-开放-api-技术标准)
9. [Zombie 任务检测与重试标准](#九-zombie-任务检测与重试标准)
10. [对话历史隔离规范](#十-对话历史隔离规范)

### Part B — MCP 服务器接入标准
11. [MCP 模块概述](#十一-mcp-模块概述)
12. [服务器接入模型](#十二-服务器接入模型)
13. [服务器配置规范](#十三-服务器配置规范)
14. [能力同步规范](#十四-能力同步规范)
15. [调用方授权规范](#十五-调用方授权规范)
16. [内置 MCP Server 开发规范](#十六-内置-mcp-server-开发规范)
17. [MCP 安全标准](#十七-mcp-安全标准)
18. [MCP 管理 API 一览](#十八-mcp-管理-api-一览)
19. [外部连接管理](#十九-外部连接管理)
20. [内置 file-parser MCP Server](#二十-内置-file-parser-mcp-server)

### Part C — Skill Pack 规范 & 编码标准
21. [Skill Pack 格式规范](#二十一-skill-pack-格式规范)
22. [后端编码标准](#二十二-后端编码标准)
23. [前端编码标准](#二十三-前端编码标准)

### 附录
- [附录 A：环境变量速查](#附录-a环境变量速查)
- [附录 B：修订记录](#附录-b修订记录)

---

# Part A — Agent 技术标准

## 一、SubAgent 技术标准

### 1.1 Agent 分层架构

AIOS 采用**三层 Agent 结构**：

```
用户对话层（Named Agent）
    └─ 基础类型层（Base Type / agent_type）
            └─ 工具执行层（Tool Registry）
```

| 层级 | 说明 | 配置位置 |
|------|------|---------|
| Named Agent | 面向用户的具名 Agent，绑定一个 base type | `agent_definitions` 表 / seeds/ |
| Base Type | 定义工具集、最大步数、系统提示模板、并发配额 | `subagent_config.py` |
| Tool | 原子能力单元，继承 `BaseTool`，注册到 `ToolRegistry` | `agent/tools/*.py` |

### 1.2 base type 定义规范

每个 base type 必须在 `SUBAGENT_TYPES` 字典中完整声明以下字段：

| 字段 | 类型 | 是否必填 | 说明 |
|------|------|---------|------|
| `tools` | list[str] | 必填 | 工具名称列表（A2A 工具系统自动附加） |
| `max_steps` | int | 必填 | 单任务最大 ReAct 步数，建议 10–25 |
| `icon` | str | 必填 | Ant Design 图标组件名或 emoji |
| `color` | str | 必填 | HEX 颜色值，用于 UI 区分 |
| `label` | str | 必填 | 中文显示名称 |
| `prompt_suffix` | str | 必填 | 角色专属提示词（英文优先） |
| `default_model` | str\|None | 必填 | 指定模型（None = 全局默认） |

### 1.3 工具声明原则

| 原则 | 说明 |
|------|------|
| **最小权限** | base type 只声明该类型业务实际需要的工具 |
| **A2A 工具自动附加** | `send_agent_message`、`receive_agent_messages`、`list_active_agents` 由系统自动追加 |
| **Token 预算约束** | `allowed_tools` 合计 Schema Token 数**不得超过 4000 tokens**（8K 上下文） |
| **重型工具限制** | 单工具 Schema Token > 300 的工具每个 Agent 最多包含 **3 个** |
| **强制 allowed_tools** | 分配了重型工具的 Agent **必须**显式声明 `allowed_tools` |
| **定期审计** | 新增/修改工具后，运行 `python scripts/token_analysis.py` |

### 1.4 Named Agent 与 base type 绑定规范

- Named Agent 通过 `agent_type` 字段引用一个 base type
- 可通过 `allowed_tools` 覆盖 base type 工具集（子集）
- 可通过 `system_prompt_override` 添加业务专属提示词
- 可通过 `model_override` 覆盖默认模型
- **禁止**：创建与已有 base type 功能高度重复的新 base type

### 1.5 种子文件（Seeds）规范

所有生产 Named Agent 须在 `backend/seeds/agents/{slug}.json` 有对应 seed 文件：

```json
{
  "id": "uuid",
  "slug": "meaningful-english-slug",
  "name": "Agent中文名",
  "agent_type": "customer_service",
  "figure_url": "/icons/xxx.svg"
}
```

- `slug` 使用有语义的英文连字符格式（禁止 `agent-1` 等通用编号）
- `agent_type` 须为 `SUBAGENT_TYPES` 中的有效键
- 通过 `make seed-agents` 幂等写入数据库

---

## 二、Agent 并发与调度标准

### 2.1 并发槽位机制（Project Wukong）

每个 base type 拥有独立的**槽位池**，通过 `_CONCURRENCY_CONFIG` 配置：

| 字段 | 说明 |
|------|------|
| `max_concurrent` | 最大同时运行实例数 |
| `queue_capacity` | 请求等待队列最大容量 |
| `queue_timeout_sec` | 队列等待超时（秒） |
| `overflow_action` | `"queue"` / `"reject"` / `"callback"` |

### 2.2 默认并发配置

| 分类 | Base Type | 最大并发 | 队列容量 | 超时（秒） |
|------|-----------|---------|---------|-----------|
| 通用高吞吐 | `general`, `explorer` | 8–10 | 20–30 | 120 |
| 通用高吞吐 | `writer`, `translator` | 8 | 15 | 120 |
| 代码/审核 | `coder`, `reviewer` | 5 | 10 | 180 |
| 客服/销售 | `customer_service`, `presales` | 5 | 10 | 300 |
| 数据/分析 | `data_analyst`, `finance` | 5 | 10 | 300 |
| 安全/法务 | `security`, `legal` | 3 | 5 | 300 |
| 媒体/设计 | `designer`, `report_agent` | 3 | 5 | 600 |
| 未配置类型 | （默认） | 5 | 10 | 300 |

### 2.3 运行时调整 API

```bash
POST /api/v1/agent-instances/scale/{type}    # 动态扩容
GET  /api/v1/agent-instances/status          # 查看槽位状态
DELETE /api/v1/agent-instances/queue/{type}/{request_id}  # 取消排队
```

**减容行为**：只移除空闲槽位，不强制中断正在运行的请求。

---

## 三、Agent Tools 技术标准

### 3.1 类定义规范

```python
from app.agent.tools.base import BaseTool

class MyTool(BaseTool):
    name        = "tool_name"         # 全局唯一，snake_case
    description = "一句话说明工具做什么、输入什么、输出什么。≤500字符"
    parameters  = {
        "type": "object",
        "properties": {
            "param_a": {"type": "string", "description": "..."}
        },
        "required": ["param_a"]
    }

    async def execute(self, params: dict, ctx: dict) -> dict:
        # 返回 {"result": ..., "error": None} 或 {"result": None, "error": "..."}
        ...
```

**description 约束**：

| 要求 | 上限 |
|------|------|
| description 字符数 | ≤ 500 字符 |
| description + parameters 合计 Token | ≤ 400 tokens |
| 禁止内容 | 示例输入/输出、代码片段、内部实现细节 |

**`BaseTool` 类级属性**：

| 属性 | 默认值 | 说明 |
|------|--------|------|
| `permission_level` | `0` | 0=公开, 1=需认证, 2=需审批, 3=仅管理员 |
| `requires_approval` | `False` | True 时执行前暂停等待人工审批 |
| `specialized` | `False` | True 时排除于默认工具池 |
| `timeout` | `60` | 每次调用超时（秒） |
| `rate_limit` | `None` | `(calls, window_seconds)` 滑动窗口限速 |

### 3.2 工具注册规范

```python
from app.agent.tool_registry import registry
registry.register(MyTool())
```

### 3.3 工具分类标准

| 分类 | 示例工具 |
|------|---------|
| 文件操作 | `file_read`, `file_write`, `file_edit` |
| 网络与搜索 | `web_search`, `web_fetch`, `http_request` |
| 代码执行 | `code_execute`, `shell_execute` |
| 邮件与日历 | `email_send`, `email_read`, `outlook_calendar` |
| 知识与记忆 | `knowledge_search`, `memory_search` |
| Agent 协作（A2A） | `send_agent_message`, `spawn_subagent` |

### 3.4 错误处理规范

- 工具必须捕获所有异常，返回 `{"result": None, "error": "错误描述"}` 而非 raise
- 错误信息须包含：问题类型 + 相关参数值（脱敏）+ 建议下一步
- 禁止：在 error 中暴露 API Key、密码、数据库连接串

### 3.5 工具调用结果规范

- 工具返回值注入 LLM 时强制截断至 **1500 字符**
- 大结果采用"摘要 + 文件"模式：`result` 返回摘要，`output_file` 保存完整数据

### 3.6 Auto-Skill workflow_md 注入规范

| 要求 | 说明 |
|------|------|
| **长度上限** | ≤ 800 字符（系统强制截断） |
| **格式** | 有序步骤列表，每步 ≤ 30 字，聚焦"做什么" |
| **禁止内容** | 示例数据、代码片段、工具参数详情 |

---

## 四、Agent 安全与审计标准

### 4.1 RBAC 权限模型

| 级别 | 名称 | 可执行操作 |
|------|------|----------|
| 0 | 访客 | 只读访问，无法发起任务 |
| 1 | 普通用户 | 发起对话、创建任务 |
| 2 | 高级用户 | 管理工作流、知识库 |
| 3 | 管理员 | 用户管理、Agent 配置、系统设置 |

### 4.2 人工审批拦截规范

以下操作必须触发审批，等待人工批准：
- 删除文件或数据库记录
- 发送邮件（外发到非内部域名）
- 执行写入型 Shell 命令
- 金额操作（退款、转账）
- 修改用户账号状态

审批请求有效期 **24 小时**，超时自动失效。

### 4.3 数据脱敏规范（DLP）

- 工具调用日志中，API Key、密码、信用卡号须自动脱敏（替换为 `[REDACTED]`）
- 审计日志不可修改、不可删除
- Agent 不得在输出中包含明文密钥

### 4.4 沙箱执行规范

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `subprocess`（默认） | 隔离子进程，共享宿主网络 | 开发/内网环境 |
| `docker` | 完全隔离容器，独立网络 | 生产/高安全要求 |

通过 `SANDBOX_MODE` 环境变量切换。

### 4.5 审计日志标准

| 字段 | 说明 |
|------|------|
| `action` | 操作类型（login / create_task / update_agent …） |
| `user_id` | 操作者 ID |
| `resource_type` | 资源类别 |
| `resource_id` | 资源 UUID |
| `detail` | JSON 格式操作详情 |
| `ip_address` | 来源 IP |
| `created_at` | UTC 时间戳 |

---

## 五、LLM 上下文 Token 预算管理标准

### 5.1 上下文组成（8K 基准）

```
┌─────────────────────────────────────────────────────┐
│  固定组件                                             │
│  ├─ 系统提示词              ~1,595 tokens            │
│  ├─ Agent Custom Prompt    varies                   │
│  ├─ 工具 Schema 合计        varies                   │
│  └─ Workspace 注入          ~699 tokens              │
├─────────────────────────────────────────────────────┤
│  可变组件（有上限控制）                                 │
│  ├─ Auto-Skill workflow_md  ≤ 600 tokens            │
│  ├─ RAG 知识库文档          ≤ 500 tokens             │
│  ├─ 记忆（Memories）        ≤ 300 tokens             │
│  ├─ 对话历史               ≤ 400 tokens             │
│  ├─ 用户消息                ≤ 20 tokens              │
│  └─ 工具调用结果            ≤ 750 tokens             │
├─────────────────────────────────────────────────────┤
│  最大可用上下文              8,192 tokens             │
└─────────────────────────────────────────────────────┘
```

### 5.2 分级告警阈值

| 状态 | 条件 | 含义 |
|------|------|------|
| 🟢 **OK** | 剩余 headroom ≥ 500 tokens | 正常 |
| 🟡 **TIGHT** | 0 < headroom < 500 tokens | 警告：实际负载稍高即可能溢出 |
| 🔴 **OVERFLOW RISK** | headroom < 0 tokens | 禁止：请求必定被 LLM 拒绝 |

### 5.3 诊断工具

```bash
python scripts/token_analysis.py             # 全量分析
python scripts/token_analysis.py --tools     # 仅工具 Schema 大小
python scripts/token_analysis.py --agent <id>
python scripts/token_analysis.py --ctx 32768 # 自定义上下文限制
python scripts/token_analysis.py --json      # JSON 输出（CI/CD 集成）
```

**CI/CD 集成要求**：修改 `prompts.py`、`tools/*.py`、`subagent_config.py` 时，CI 必须运行 Token 分析确保无 🔴。

> ⚠ **CJK 注意**：中/日文每字约 1 token（英文为 0.25 token/字符）。

---

## 六、提示词 / 工具 / Skills 三级规模标准

### 6.1 CJK Token 成本修正

| 语言 | 字符/Token（实测） |
|------|-------------------|
| 英文 | ~3.9–5.4 chars/tok |
| 中文 | ~1.6–1.8 chars/tok |
| 日文 | ~1.4–2.0 chars/tok |

### 6.2 Agent 专属提示词规模标准（`system_prompt_override`）

| 等级 | Token 上限 | CJK 参考字符 | UI 色带 |
|------|-----------|-------------|--------|
| 🟢 Optimal | ≤ 200 tok | ≤ 350 字 | 绿色 |
| 🟡 Moderate | 201–400 tok | 351–680 字 | 黄色 |
| 🟠 Tight | 401–550 tok | 681–940 字 | 橙色 |
| 🔴 Critical | > 550 tok | > 940 字 | 红色 |

**编写原则**：聚焦角色定位、专业边界、禁止行为三要素；优先用英文撰写（节省约 60% Token）。

### 6.3 单工具 Schema Token 分级

| 等级 | Schema Token 数 | 处理要求 |
|------|----------------|---------|
| 🟢 轻量 | ≤ 150 tok | 无限制 |
| 🟡 中型 | 151–300 tok | 每 Agent 最多 8 个 |
| 🟠 重型 | 301–500 tok | 每 Agent 最多 3 个，必须显式 `allowed_tools` |
| 🔴 超重 | > 500 tok | 强烈建议拆分；每 Agent 限 1 个 |

**已知超重工具**（Qwen2.5-14B 实测）：

| 工具名 | Schema Tokens |
|--------|--------------|
| `email_read` | 956 |
| `ticket_ops` | 871 |
| `email_send` | 777 |
| `grep_search` | 677 |

### 6.4 Skills（Auto-Skill）workflow_md 规模

| 等级 | 字符上限 | 含义 |
|------|---------|------|
| 🟢 精简 | ≤ 300 字符 | 理想 |
| 🟡 适中 | 301–600 字符 | 可接受 |
| 🟠 偏大 | 601–800 字符 | 已达系统截断上限 |
| 🔴 超标 | > 800 字符 | 系统强制截断，超出部分丢失 |

关键步骤必须放在前 300 字符内；最多注入 3 个 Skill。

---

## 七、Agent 基础类型命名规范

### 7.1 命名原则

| 原则 | 正例 | 反例 |
|------|------|------|
| 不使用 `_agent` 后缀 | `customer_service` | `customer_service_agent` |
| 全小写下划线 | `project_manager` | `ProjectManager` |
| 语义明确 | `translator` | `language_agent` |
| 禁止通用编号 | `reviewer` | `agent-2` |

### 7.2 当前标准 Base Type 清单（共 29 种）

#### 通用基础
| Base Type | 中文标签 | 核心职能 |
|-----------|---------|---------|
| `general` | 通用Agent | 通用问答、信息整理 |
| `explorer` | 探索Agent | 只读调研、信息采集 |
| `writer` | 写作Agent | 内容创作、文档编写 |
| `coder` | 编码Agent | 代码开发、测试 |
| `reviewer` | 审核Agent | 文档审核、需求分析、架构评审 |

#### 业务专业
| Base Type | 中文标签 | 核心职能 |
|-----------|---------|---------|
| `customer_service` | 通讯Agent | 全渠道客服 |
| `technical_support` | 技术支持 | PSP/API 技术支持 |
| `presales` | 售前支持 | 方案设计、竞品分析 |
| `translator` | 语言Agent | 中日英翻译 |
| `designer` | 图画Agent | 图像生成、视觉设计 |
| `project_manager` | 项目管理 | IT 项目规划与交付 |
| `ops` | 运维监控 | 基础设施监控、故障响应 |

#### 数据与财务
| Base Type | 中文标签 | 核心职能 |
|-----------|---------|---------|
| `data_analyst` | 数据分析 | 数据分析、BI 查询 |
| `finance` | 财务Agent | 财务分析、预算 |
| `bank_reconciliation_agent` | 银行对账 | 银行流水对账 |
| `report_agent` | 业务报告 | 月度业务报告 |

#### 管理与支持
| Base Type | 中文标签 | 核心职能 |
|-----------|---------|---------|
| `hr` | 人力资源 | HR 管理、招聘 |
| `legal` | 法务Agent | 合同审查、合规 |
| `security` | 安全审计 | 安全审计、合规检查 |
| `scheduler` | 日程管理 | 日程安排、会议协调 |
| `coordinator` | 协调管理 | 跨部门协调 |

### 7.3 已废弃类型

| 废弃类型 | 替代类型 |
|---------|---------|
| `comm_agent` | `customer_service` |
| `ops_monitor_agent` | `ops` |
| `pm_agent` | `project_manager` |
| `language_agent` | `translator` |
| `image_agent` | `designer` |
| `requirements_agent` | `reviewer` |

### 7.4 新增 Base Type 审批流程

1. 必要性论证（现有类型无法满足）
2. 工具清单审查（Token 预算合规）
3. 命名合规检查（§7.1 原则）
4. 并发配置（`_CONCURRENCY_CONFIG` 声明）
5. 种子文件（至少一个 Named Agent seed JSON）
6. 文档更新（更新本标准 §7.2 清单）

---

## 八、开放 API 技术标准

### 8.1 认证机制

开放 API 使用 **Bearer API Key** 认证，格式：`goku_` 前缀 + 32 字符 URL-safe token。

| 要素 | 规范 |
|------|------|
| 存储 | 仅存储 SHA-256 哈希值，原文不落库 |
| 展示 | 仅展示前 8 字符前缀 |
| 传输 | 必须通过 HTTPS |
| 轮换 | 建议每 90 天；高权限 Key 每 30 天 |

### 8.2 限速标准

| 参数 | 最小值 | 最大值 | 默认值 |
|------|--------|--------|--------|
| QPS | 1 | 1000 | 10 |
| 月度 Token 配额 | 0 | 无上限 | 100,000 |

超出 QPS：`429 Too Many Requests`，`Retry-After` Header 说明等待时间。

### 8.3 外部 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/external/v1/chat` | POST | 提交任务，返回 `task_id` |
| `/api/external/v1/tasks/{id}` | GET | 轮询任务状态 |
| `/api/external/v1/tasks/{id}/events` | GET | SSE 流式订阅 |

### 8.4 Webhook 回调规范

| 要素 | 规范 |
|------|------|
| 触发条件 | 任务进入终态（completed / failed / cancelled） |
| 方法 | HTTP POST，`Content-Type: application/json` |
| 超时 | 10 秒；不重试（fire-and-forget） |
| Payload | `{ task_id, status, result, error, updated_at }` |

---

## 九、Zombie 任务检测与重试标准

### 9.1 Zombie 定义

满足以下**全部条件**：
- 任务状态：`pending` 或 `in_progress`
- 最后心跳时间：距当前 > **300 秒**
- 未处于终态（completed / failed / cancelled）

### 9.2 自动重试规则

```
检测到 Zombie
  → 将原任务标记为 FAILED（error: "zombie_timeout"）
  → 若 retry_count < ZOMBIE_MAX_RETRIES（默认 3）
      → 创建新 Task，_retry_count += 1，立即 dispatch
  → 否则 → 记录日志，不再重试
```

### 9.3 配置项

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `ZOMBIE_TIMEOUT_SECONDS` | `300` | 心跳超时阈值（秒） |
| `ZOMBIE_MAX_RETRIES` | `3` | 最大自动重试次数 |
| `ZOMBIE_CHECK_INTERVAL` | `120` | 检测间隔（秒） |

---

## 十、对话历史隔离规范

### 10.1 规范目的

防止 Agent 将历史会话中已完成的工具调用重复执行于当前任务，消除"历史污染"。

### 10.2 强制隔离规则

| 规则 | 说明 |
|------|------|
| **历史隔离 system boundary** | 在 history messages 前后各插入 `role: system` 边界消息 |
| **禁止重复执行** | 历史工具调用结果仅供参考，严禁重新执行 |
| **当前任务优先** | 当前轮次的用户消息为唯一驱动源 |

### 10.3 LLM messages 组织顺序

```
1. system（全局提示词 + Agent 专属提示词）
2. system [HISTORY_START]
3. history messages（历史轮次 user/assistant 交替消息）
4. system [HISTORY_END]
5. user（当前用户消息）
```

边界消息示例：
```python
{"role": "system", "content": "[CONVERSATION_HISTORY_START] The following messages are prior conversation context for reference only. Do NOT re-execute any tool calls shown below."}
{"role": "system", "content": "[CONVERSATION_HISTORY_END] Now process the current user request above."}
```

---

# Part B — MCP 服务器接入标准

## 十一、MCP 模块概述

MCP Server 模块让平台接入外部或内置的 MCP 服务器，把暴露的能力纳入统一管理，经授权后供 AI Tool、Agent 调用。

模块由 8 张数据表支撑：

| 表 | 用途 |
|---|---|
| `mcp_servers` | 连接 / 认证 / 同步 / 风控配置 |
| `mcp_capabilities` | 从服务器同步来的能力 |
| `mcp_resources` | 从服务器同步来的资源 |
| `mcp_prompts` | 从服务器同步来的 prompt |
| `mcp_permissions` | 服务器级权限授予 |
| `mcp_health_records` | 健康探测时间序列（append-only） |
| `mcp_call_logs` | 能力调用日志（append-only） |
| `mcp_capability_authorizations` | 调用方 → 能力的授权 + 配额 |

迁移文件：`backend/alembic/versions/0030_*` ~ `0037_*`。

---

## 十二、服务器接入模型

### 12.1 连接方式（connection_type）

| 值 | 说明 |
|---|---|
| `stdio` | 子进程，标准输入输出通信。最常用 |
| `http` | Streamable HTTP 端点 |

### 12.2 两类 stdio 服务器

**外部服务器** — 通过 `npx` / `uvx` / `docker` 拉起第三方 MCP 包。

**内置服务器** — 平台自带，代码在 `backend/app/agent/mcp/servers/`：
```
${VENV_PYTHON} -m app.agent.mcp.servers.<module>
```
现有内置：`db_query_server` / `reconciliation_db_server` / `clickhouse_server` / `flight_travel_server` / `ira_server` / `bank_recon_server` / `storage_s3_server` / `file_parser_server`。

### 12.3 启动命令变量替换

| 变量 | 解析为 |
|---|---|
| `${VENV_PYTHON}` | 当前 venv 解释器 |
| `${REPO_ROOT}` | 仓库根目录 |
| `${BACKEND_DIR}` | `backend/` 源码目录 |
| `${AGENT_WORKSPACE}` | Agent 工作区目录 |

**规范**：内置服务器启动命令必须用 `${VENV_PYTHON}`；`PYTHONPATH` 由 `mcp_runtime` 自动注入，不得手填进 `env_config`。

### 12.4 可纯配置接入 vs 需要开发的判定

`start_command` 是自由文本、`http` 连接方式接受任意远程 MCP 端点，因此**没有写死的"支持服务白名单"**。一个服务能否**只靠管理页配置**接入，由它的**凭证形态**决定：

| 档位 | 条件 | 接入方式 |
|---|---|---|
| **零配置** | 不需要任何外部凭证 | 选预置 / 填 `start_command` 即可。例：filesystem、fetch、memory、time、puppeteer、sqlite（本地）|
| **配凭证即用** | 密钥是 7 种外部连接类型之一，**或**是厂商前缀专用键 | 前者绑「外部连接」，后者直填 `env_config`。例：github / slack / postgres（连接）、brave-search（`BRAVE_API_KEY` 直填）、s3 / mysql（内置 server + 连接）|
| **需开发** | 密钥既非 7 类连接、又非厂商前缀键；**或**无 npx 包 / HTTP 端点可通话 | 加连接类型注入分支，或写内置 Python server。例：ClickHouse（`database` 类但需新增 `clickhouse_server.py`）|

**前端预置模板**（`frontend/src/pages/mcp/ServerDrawer.tsx` 的 `PRESETS`，11 条）：filesystem / fetch / memory / time / puppeteer / sqlite（零凭证）、github / slack / postgres / brave-search（带凭证）、bank-recon（内置 Python）。

**两个运行前提**：

1. **npm 可达**：`npx -y <pkg>` 首次启动按需拉包，内网隔离环境会在 spawn 期失败。镜像内置 Node 20 + npx（见 `backend/Dockerfile`）。
2. **包名真实**：`@modelcontextprotocol/server-*` 随上游改名 / 归档，配置前须确认 npm 上仍按此名发布。

---

## 十三、服务器配置规范

### 13.1 mcp_servers 关键字段

| 字段 | 说明 |
|---|---|
| `name` / `code` | 显示名 / 稳定外部标识（`code` 全局唯一） |
| `connection_type` | `stdio` / `http` |
| `start_command` | stdio 启动命令（含 `${VAR}` 模板） |
| `auth_type` / `auth_secret` | 认证方式 / 密文 |
| `env_config` | 子进程环境变量 JSON（密文，禁止包含外部系统 secret） |
| `status` | `enabled` / `disabled` |
| `allow_agent_auto_invoke` | 风控开关 |

### 13.2 密文字段规范

- `env_config` 与 `auth_secret` 经 Fernet（密钥来自 `GOKU_SECRET_KEY`）加密后入库
- 外部系统凭证（AWS key、API token 等）统一存 `mcp_external_connections.secret_json`，通过 `env_config.connection_id` 绑定
- 日志、错误信息均不得记录密文或解密后的 secret

---

## 十四、能力同步规范

1. **测试连接**：拉起/连接服务器，执行探测（stdio 跑 `tools/list`），记录 `mcp_health_records`
2. **同步能力**：拉取 `tools/list` / `resources/list` / `prompts/list`，与 DB diff 后写入对应表
3. **能力状态**：`active` / `inactive`。上游移除的能力**标记为 `inactive` 而非删除**（历史调用日志仍可解析）

---

## 十五、调用方授权规范

### 15.1 授权模式（默认拒绝）

| 模式 | 含义 |
|---|---|
| `required`（默认） | **默认拒绝**；只有显式授权行 enabled 才允许调用 |
| `public` | **全部可用**；`mcp_capability_blacklists` 里的条目可拒绝 |

两条调用路径都强制走授权检查链：
- **Agent 路径**：`MCPToolWrapper.execute` → `principal_type='agent'`
- **AI Tool 路径**：`POST /api/v1/ai-tools/{tool_id}/invoke` → `principal_type='ai_tool'`

**默认对话不能直接调 MCP 能力**——必须路由到具体 Agent 并给该 Agent 显式授权。

### 15.2 配额与速率

- **总配额**：`quota_*` 字段，限制一个周期内所有调用方合计次数
- **速率上限**：`rate_*` 字段，限制每分钟突发调用次数（独立于总配额）
- 周期重置为**惰性**：下次调用时若窗口已过期才重置

### 15.3 调用检查链错误码

| 错误码 | 含义 |
|---|---|
| `MCP_CAPABILITY_NOT_AUTHORIZED` | 无授权 |
| `MCP_AUTHORIZATION_DISABLED` | 授权被停用 |
| `MCP_AUTHORIZED_QUOTA_EXCEEDED` | 单授权配额耗尽 |
| `MCP_CAPABILITY_QUOTA_EXCEEDED` | 能力总配额耗尽 |
| `MCP_CAPABILITY_RATE_EXCEEDED` | 速率上限耗尽 |

### 15.4 Agent 侧的两个额外门槛（授权之外）

授权通过 ≠ Agent 就能用。`MCPToolWrapper`（`backend/app/agent/mcp/tool_wrapper.py`）
作为 BaseTool 还带两条运行时约束：

| 约束 | 取值 | 影响 |
|---|---|---|
| **工具池可见性** | `specialized=False` | MCP 能力默认进默认工具池；但 Agent 若设了 `allowed_tools` 白名单，**必须显式包含 `{server_code}__{capability_name}`**，否则被 `executor` 的 `allowed_tools` 过滤掉（[executor.py](../backend/app/agent/executor.py) 的 3a 段），授权了也不可见 |
| **人工审批** | `requires_approval=True`、`permission_level=2` | **每次 MCP 工具调用都先走审批流**（`tool_registry._wait_for_approval`：建 `Approval` 行 → 发 `need_approval` 事件 → 轮询，fail-closed）。内置与外部 server **一视同仁**——类级默认无条件开启，wrapper 未按 server 来源区分 |

> 规范：MCP 工具的 `requires_approval` 是 `MCPToolWrapper` 类级硬默认，
> 不随 server 是内置 / 外部而变。如需放开某类 MCP 工具免审批，应在 wrapper
> 层显式建模（如覆写 `should_require_approval`），不要靠"内置就豁免"的隐含假设。

---

## 十六、内置 MCP Server 开发规范

新增内置 MCP 服务器时：

1. **位置**：`backend/app/agent/mcp/servers/<name>_server.py`
2. **框架**：`mcp.server.fastmcp.FastMCP`

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("<server-name>")

@mcp.tool()
def some_capability(...) -> dict:
    """能力说明（会作为 capability description 同步出去）。"""
    ...

def main() -> None:
    mcp.run()

if __name__ == "__main__":
    main()
```

3. **传输**：stdio。启动命令 `${VENV_PYTHON} -m app.agent.mcp.servers.<module>`
4. **配置**：一切配置从 `os.environ` 读取，不写死；缺必填项应在启动期 `raise`
5. **预置模板**：在 `frontend/src/pages/mcp/ServerDrawer.tsx` 的 `PRESETS` 加一条
6. **冒烟测试**：`qa/smoke/` 下提供 smoke 脚本

---

## 十七、MCP 安全标准

1. 凭证只入 `env_config` / `auth_secret`（密文），绝不写死在代码
2. 密文字段解密后绝不经 API 返回
3. 内置服务器对一切外部输入做校验与 sanitize；路径类输入须拒绝 `..` 穿越
4. 调用方授权默认拒绝，授权 + 配额检查不可绕过
5. 能力的删除走 `inactive` 标记还是物理删除，取决于是否还有历史日志解析需求

---

## 十八、MCP 管理 API 一览

`/api/v1/mcp-servers` 前缀：

| 方法 + 路径 | 用途 |
|---|---|
| `GET /` `GET /stats` `GET /{id}` | 列表 / 统计 / 详情 |
| `POST /` `PUT /{id}` `DELETE /{id}` | 增 / 改 / 软删 |
| `POST /{id}/enable` `POST /{id}/disable` | 启用 / 停用 |
| `POST /{id}/test` | 测试连接 |
| `POST /{id}/sync` | 同步能力 |
| `GET /{id}/capabilities` | 能力列表 |
| `PATCH /{id}/capabilities/{cid}/quota` | 设置能力总配额 |
| `GET /{id}/call-logs` | 调用日志 |

调用入口：`POST /api/v1/ai-tools/{tool_id}/invoke`。

---

## 十九、外部连接管理（External Connections）

### 19.1 与 MCP Server 的关系

| 角色 | 表 | 边界含义 |
|---|---|---|
| MCP Server 实例 | `mcp_servers` | 授权边界（不变） |
| 外部连接配置 | `mcp_external_connections` | 凭证集中托管，通过 `env_config.connection_id` 绑定 |

### 19.2 支持的连接类型与注入 env vars

| type | 主要 env vars |
|---|---|
| `s3` | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `S3_ALLOWED_BUCKETS` |
| `sftp` | `SFTP_HOST` / `SFTP_USERNAME` / `SFTP_PASSWORD` or `SFTP_PRIVATE_KEY` |
| `url` | `URL_ALLOWED_DOMAINS` / `URL_AUTHORIZATION_HEADER` |
| `local_path` | `LOCAL_ALLOWED_DIRS` |
| `database` | `DB_TYPE` / `DB_HOST` / `DB_PASSWORD` |
| `github` | `GITHUB_TOKEN` / `GITHUB_ALLOWED_REPOS` |
| `slack` | `SLACK_BOT_TOKEN` / `SLACK_ALLOWED_CHANNELS` |

### 19.3 `env_config` 边界（V1.2 起）

`env_config` 禁止保存**被外部连接注入器接管的**凭证字段。判定规则是
**精确匹配、大小写不敏感**（`k.upper() in FORBIDDEN_ENV_CONFIG_FIELDS`，
见 `mcp_servers.py`），**不是前缀 / 子串通配**。禁止集合含：

- 7 类连接各自的 env（`AWS_ACCESS_KEY_ID` / `SFTP_PASSWORD` / `DB_PASSWORD` /
  `GITHUB_TOKEN` / `SLACK_BOT_TOKEN` …）
- 裸通用名（`TOKEN` / `API_KEY` / `ACCESS_TOKEN` / `PASSWORD` /
  `PRIVATE_KEY` / `AUTHORIZATION` / `AUTH_SECRET` / `X-API-KEY`）

`env_config` **允许**：
- `connection_id`（选中的连接 code）
- 本实例运行参数（TTL / 超时等非敏感字段）
- **厂商前缀专用密钥**：因为是精确匹配，像 `BRAVE_API_KEY`、`NOTION_API_KEY`、
  `GITLAB_TOKEN` 这类带前缀的键**不在禁止集合内**，可直接填入（保存自动 Fernet
  加密）。这是 brave-search 等"无对应连接类型但有专用 key"的服务的合规接入路径。

> 触发禁止字段返回 `MCP_ENV_SECRET_FIELD_NOT_ALLOWED`。新增连接类型时
> （见 `_inject_connection_env`），须同步把它 OWN 的 env 名加进禁止集合，
> 防止管理员绕过连接、把凭证直接粘进 `env_config`。

---

## 二十、内置 file-parser MCP Server

### 20.1 定位

**只负责解析文件**，不连接任何外部系统（S3 / SFTP / DB / GitHub）。不保存、不接收任何外部系统密钥。

### 20.2 三种 source type

| type | 字段 | 获取方式 |
|---|---|---|
| `download_url` | `url` | HTTP 下载（SSRF 防护，100MB 上限） |
| `managed_file_ref` | `file_ref` | 读 `GOKU_FILE_BASE/managed/<ref>` |
| `conversation_upload` | `file_id` | 读 `GOKU_FILE_BASE/conversations/<id>` |

### 20.3 支持格式

| 类别 | 格式 |
|---|---|
| 表格 | `csv` / `xlsx` / `xls` |
| 结构化 | `json` / `jsonl` / `xml` |

**不支持** PDF / 图片 / OCR。column_key 永远 `col_N`，绝不用 header 文本。

### 20.4 四个 capability

| capability | 作用 |
|---|---|
| `parse_file_profile` | 解析整体结构（profile），返回 total_rows / column_stats / sample |
| `get_file_profile` | cache-first 返回 profile |
| `get_file_samples` | 指定 sheet 从 start_row 取样（≤200） |
| `read_file_chunk` | 分块读；返回 records + next_cursor + has_more |

---

# Part C — Skill Pack 规范 & 编码标准

## 二十一、Skill Pack 格式规范

### 21.1 文件结构

标准工具包是 ZIP 文件，扩展名 `.aios-skill`：

```
<skill-id>-<version>.aios-skill
├── manifest.json       # 必须 - 包元数据
├── tools/
│   └── <tool_name>.py  # 必须 - 工具实现文件
├── tests/
│   └── test_*.py       # 可选 - 单元测试
└── README.md           # 可选 - 使用说明
```

### 21.2 命名约定

| 元素 | 格式 | 示例 |
|------|------|------|
| 包文件名 | `{skill-id}-{version}.aios-skill` | `media-generation-tools-1.0.0.aios-skill` |
| skill-id | `kebab-case` | `media-generation-tools` |
| tool_name | `snake_case` | `generate_video_local` |
| version | Semantic Versioning | `1.0.0` |

### 21.3 manifest.json 必填字段

```json
{
  "id": "skill-id",              // kebab-case，全局唯一
  "name": "Skill 人类可读名称",
  "version": "1.0.0",
  "description": "一句话描述",
  "aios_version_min": "1.0.0",
  "tools": [
    {
      "name": "tool_name",
      "file": "tools/tool_name.py"
    }
  ]
}
```

### 21.4 安装与管理

```bash
# CLI 安装
aios-cli skill install skill_packs/my-skill-1.0.0.aios-skill

# 列出可用技能包
python skill_packs/install_skill_pack.py --list

# UI 安装
/skills 页面 → 上传 .aios-skill 文件
```

### 21.5 安全审计要求

平台在安装时必须：
1. 校验 `manifest.json` schema
2. 扫描工具代码（拒绝 `subprocess.call(shell=True)` 等高风险模式）
3. 检查依赖声明与实际 import 是否一致
4. 记录安装审计日志

---

## 二十二、后端编码标准

### 22.1 架构原则

**路由职责分离**：Goku Router 负责所有 LLM 提供商路由；`model_router.py` 仅作透传，不包含熔断器或提供商选择逻辑。

**租户隔离**：所有数据库查询**必须**按 `tenant_id` 过滤：
```python
db.query(models.Agent).filter(models.Agent.tenant_id == tenant_id).all()
```

**模型能力检测**：禁止字符串前缀判断：
```python
# ❌ 错误
if model.startswith("claude"): ...

# ✅ 正确
from app.services.model_capabilities import get_capabilities
caps = get_capabilities(model_name)
if caps.supports_thinking: ...
```

**Datetime 处理**：以**朴素 UTC** 格式存储。不使用 `.astimezone()` 或带时区的 datetime。`main.py` 的全局编码器自动追加 `Z`。

### 22.2 Router 结构

- `backend/app/routers/` 中每个领域一个文件
- 前缀格式：`/api/v1/{domain}`

### 22.3 Pydantic Schema

- PATCH/PUT 使用 `model_dump(exclude_unset=True)`
- 分别定义 `Create`、`Update`、`Out` Schema
- ORM 序列化使用 `from_attributes = True`

### 22.4 数据库迁移

- 在 `backend/alembic/versions/` 中使用顺序编号（`NNNN_description.py`）
- 务必实现 `downgrade()`
- 每次部署前运行 `make migrate`（`alembic upgrade head`）

### 22.5 代码规范

```bash
ruff check .      # 检查（line-length=100，target=py311）
ruff format .     # 格式化
pytest            # 运行所有测试
```

---

## 二十三、前端编码标准

### 23.1 国际化（i18n）

所有用户可见字符串必须在三个语言文件（en / zh / ja）中都有对应键，使用 `useTranslation()` hook。

### 23.2 API 客户端

使用 `src/api/index.ts` 中的 `api`（已处理 Base URL、JWT、Token 刷新）。`src/api/request.ts` 为原始 Axios 实例，仅用于 ChatPage 等全路径调用。

### 23.3 权限控制

```tsx
// 正确方式 — 从 sessionStorage 缓存同步读取，无闪烁
const { hasPermission, isSuperuser } = usePermissions()
if (hasPermission('system.config.write')) { /* 显示管理项 */ }
```

### 23.4 模型能力

```tsx
const caps = useModelCapabilities(selectedModel)
if (caps.supports_thinking) { /* 显示思考开关 */ }
```

### 23.5 状态管理

使用 Zustand Stores（`useAuthStore`、`useChatStore`、`useThemeStore`）。全局状态禁止使用 React Context。

### 23.6 安全规范

- 除 `/auth/login`、`/health` 外，所有 API 端点均需 JWT 验证
- 具有破坏性效果的工具必须设置 `approval_required = True`
- 禁止记录 API Key、Token 或密码

---

## 附录 A：环境变量速查

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | 必填 | `mysql+pymysql://user:pass@host:3306/aios` |
| `SECRET_KEY` | 必填 | JWT 签名密钥 |
| `OPENAI_API_KEY` | 必填 | 可指向任何 OpenAI-compatible 端点 |
| `OPENAI_BASE_URL` | 可选 | 覆盖 LLM 网关地址（Goku Router） |
| `AGENT_MAX_STEPS` | `20` | 全局最大 ReAct 步数 |
| `LLM_TIMEOUT` | `120` | LLM 调用超时（秒） |
| `SANDBOX_MODE` | `subprocess` | 沙箱模式：subprocess / docker |
| `REDIS_URL` | 可选 | 设置后启用跨进程 SSE 和 Redis 事件总线 |
| `ZOMBIE_TIMEOUT_SECONDS` | `300` | Zombie 任务心跳超时（秒） |
| `ZOMBIE_MAX_RETRIES` | `3` | Zombie 任务最大重试次数 |
| `SUPERVISOR_ENABLED` | `true` | 是否启用自主演进 Supervisor |
| `GOKU_ROUTER_URL` | 可选 | Goku Router 地址；设置后从 Router 拉取模型目录 |
| `DLP_ENABLED` | `true` | 是否启用 PII 自动脱敏 |

---

## 附录 B：修订记录

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| V1.0 | 2026-04-01 | 初版，建立 Agent 基础四章框架 |
| V1.1 | 2026-04-28 | 新增并发管理规范，修订 §1.3 |
| V1.2 | 2026-05-17 | 整合补丁；新增 §5–§7；统一 base type 命名 |
| V1.3 | 2026-05-19 | 新增 §8–§10：开放 API、Zombie 任务、对话历史隔离 |
| V1.4 | 2026-05-28 | **综合版**：合并 MCP 接入标准（含外部连接、file-parser）、Skill Pack 规范、后端/前端编码标准；删除三份独立标准文件 |
| V1.5 | 2026-06-02 | 新增 §12.4「可纯配置接入 vs 需开发」判定 + 预置模板清单；§19.3 改为精确匹配规则并说明厂商前缀键合规直填；补全 §12.2 内置 server 清单 |
| V1.6 | 2026-06-02 | 新增 §15.4「Agent 侧两个额外门槛」：MCP 工具 `requires_approval=True` 默认人工审批（内置/外部一视同仁）+ `allowed_tools` 白名单须含 `{server}__{cap}` |

---

*本标准由 AIOS 核心研发团队维护。如有疑问，请联系系统管理员。*
