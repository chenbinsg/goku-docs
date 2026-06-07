# Roadmap：Stateful Agent Runtime（状态驱动 Agent 运行时）

> 状态：In Progress · 创建：2026-06-05 · 最后更新：2026-06-06 · Owner：TBD  
> 目标分支：`main`（PoC 已合并）

---

## 1. 背景与目标

### 1.1 背景

当前 AIOS 已具备以下能力：

- Agent 执行器：`backend/app/agent/executor.py`
- 工作流引擎：`backend/app/services/workflow_engine.py`
- 审批与审计：`backend/app/services/approval.py`、`backend/app/routers/audit.py`
- RBAC / tenant 隔离
- 多渠道入口与工具调用

这些能力足以支持企业级 Agent 落地，但对于 **“强状态业务”** 仍缺一层统一运行时范式。

典型强状态场景包括：

- 报销申请
- 采购申请
- 合同审批
- 工单处理
- 退款审核
- 客服补件流程

这类场景的关键特征不是“照着固定流程一路跑完”，而是：

1. 每一步都需要先读取外部系统当前状态
2. 只能在当前状态下选择“允许执行的动作”
3. 执行动作后进入新状态
4. 再重新观察状态，选择下一步

也就是说，Agent 不应该“背完整流程图”，而应该：

> 看当前状态，再选下一步。

### 1.2 目标

为 AIOS 增加一套统一的 **状态驱动 Agent Runtime**，让 Agent 在处理企业业务时遵循：

```text
Observe State → List Allowed Actions → Validate Payload → Execute One Action
→ Refresh State → Repeat / Stop / Escalate
```

目标效果：

- 降低 Agent 选错路的概率
- 避免错误状态沿后续步骤传播
- 让审批、确认、审计和风险控制自然接入
- 为企业业务系统提供更稳的 Agent 承接方式

---

## 2. 问题定义

### 2.1 当前范式的局限

当前 AIOS 的执行路径更接近：

```text
用户输入 → LLM 决策 → 工具调用 → 继续推演
```

这种范式适合：

- 知识问答
- 通用工具编排
- 报告生成
- 研发辅助

但在强状态业务里，有 4 个明显风险：

**① 状态读取不是一等公民**  
Agent 可以直接“想下一步”，但不一定强制先读取外部系统当前状态。

**② 动作集合不受当前状态严格约束**  
Agent 可能基于工具说明自行推断，而不是基于后端返回的 `allowed actions` 做选择。

**③ 高风险动作缺少统一的动作级防护**  
虽然 AIOS 已有审批与 RBAC，但当前没有统一的“动作守卫层（Action Guard）”把状态、动作、审批联动起来。

**④ 错误路径会扩散**  
一旦 Agent 误判了当前状态，后续每一步都可能建立在错误前提上，最终改变外部系统真实状态。

### 2.2 目标业务范式

未来目标应该是：

```text
外部系统返回：
- current_state
- available_actions
- action_schema
- constraints

Agent 只能：
- 从 available_actions 里选
- 用 action_schema 校验 payload
- 执行一个动作
- 再重新读取状态
```

---

## 3. 目标架构

### 3.1 运行时主循环

```text
┌──────────────────────────────┐
│ 1. 读取当前业务状态          │
│    get_state(entity_id)      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ 2. 获取允许动作集合          │
│    list_available_actions()  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ 3. Agent 选择下一步          │
│    choose(action)            │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ 4. Action Guard              │
│ - schema 校验                │
│ - approval / confirm         │
│ - risk policy                │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ 5. 执行动作                  │
│    execute_action()          │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ 6. 刷新状态                  │
│    get_state()               │
└──────────────┬───────────────┘
               │
       continue / stop / escalate
```

### 3.2 核心抽象

新增统一业务动作协议：

```python
class StatefulBusinessAdapter(Protocol):
    def get_state(self, entity_id: str, *, actor: ActorContext) -> StateSnapshot: ...
    def list_available_actions(self, entity_id: str, *, actor: ActorContext) -> list[ActionSpec]: ...
    def execute_action(self, entity_id: str, action_name: str, payload: dict, *, actor: ActorContext) -> ActionResult: ...
```

### 3.3 关键数据结构

#### StateSnapshot

```json
{
  "entity_id": "expense-123",
  "current_state": "draft",
  "state_version": "2026-06-05T12:00:00Z",
  "summary": {
    "invoice_uploaded": false,
    "approval_status": null
  }
}
```

#### ActionSpec

```json
{
  "name": "upload_invoice",
  "label": "上传发票",
  "description": "为当前报销单上传发票附件",
  "risk_level": "medium",
  "requires_confirmation": false,
  "requires_approval": false,
  "idempotent": true,
  "payload_schema": {
    "type": "object",
    "properties": {
      "file_id": { "type": "string" }
    },
    "required": ["file_id"]
  },
  "expected_next_state": "invoice_uploaded"
}
```

#### ActionResult

```json
{
  "success": true,
  "action_name": "submit_for_approval",
  "result_code": "submitted",
  "message": "报销单已提交审批",
  "external_reference": "approval-789"
}
```

---

## 4. 与 AIOS 现有能力的对接点

### 4.1 Agent Executor

文件：
- `backend/app/agent/executor.py`

新增职责：

- 支持 `stateful_loop` 模式
- 每个 mutating step 前强制通过 Action Guard
- 每次动作执行后刷新状态
- 出现状态异常时停止并上报

### 4.2 Workflow Engine

文件：
- `backend/app/services/workflow_engine.py`

使用方式：

- Workflow 不再预先写死“完整路径”
- 可以定义“观察节点 / 动作节点 / 审批节点 / 重试节点”
- 更适合作为状态循环的外层 orchestration

### 4.3 审批中心

文件：
- `backend/app/services/approval.py`
- `backend/app/routers/approvals.py`

新增用法：

- `ActionSpec.requires_approval == true` 时，执行动作前自动挂起审批
- 审批通过后恢复执行

### 4.4 审计日志

文件：
- `backend/app/routers/audit.py`
- `auth.log_audit_action(...)`

需要记录：

- previous_state
- action_name
- payload_summary
- next_state
- actor
- route_source
- confidence / reason

---

## 5. 分阶段路线图

## Phase 0 — 设计与样板场景（0.5–1 周）

目标：把概念变成统一契约，不急着做通用平台。

### 工作项

1. 定义核心协议
   - `StateSnapshot`
   - `ActionSpec`
   - `ActionResult`
   - `StatefulBusinessAdapter`

2. 选一个样板场景
   - 优先推荐：报销申请 / 采购审批

3. 梳理该场景的状态机
   - `draft`
   - `invoice_uploaded`
   - `submitted`
   - `pending_approval`
   - `approved`
   - `rejected`
   - `supplement_required`

4. 为每个状态定义 allowed actions

### Deliverable

- 设计文档
- 一份样板状态机图
- 一份动作 schema 清单

---

## Phase 1 — Runtime 最小可用版（1–1.5 周）

目标：让 AIOS 具备最小的状态驱动循环执行能力。

### 工作项

1. 新增服务模块
   - 建议文件：`backend/app/services/stateful_runtime.py`

2. 提供主循环接口

```python
run_stateful_step_loop(
    adapter: StatefulBusinessAdapter,
    entity_id: str,
    instruction: str,
    *,
    actor: ActorContext,
    max_steps: int = 10,
) -> StatefulExecutionResult
```

3. 在 executor 中增加一个新执行分支
   - 普通任务继续原逻辑
   - 状态驱动任务走 `stateful_loop`

4. 每一步都先 `get_state()` 再决策

### Deliverable

- 最小可运行 runtime
- 一套单元测试

---

## Phase 2 — Action Guard 与风险控制（1 周）

目标：把“动作可执行”这件事做成平台级能力。

### 工作项

1. 新增 `ActionGuard`
   - schema 校验
   - allowed action 校验
   - idempotency / retry policy
   - irreversible flag

2. 动作风险级别分层
   - `low`
   - `medium`
   - `high`
   - `critical`

3. 动作级执行策略
   - auto
   - confirm_required
   - approval_required
   - human_only

4. 与现有审批中心集成

### Deliverable

- Action Guard 服务
- 风险策略映射
- 高风险动作阻断或挂审批

---

## Phase 3 — 审计与可观测性（0.5–1 周）

目标：让团队看清“Agent 为什么走这条路”。

### 工作项

1. 增加状态转换审计日志
2. 增加 step timeline
3. 增加异常分类
   - stale_state
   - invalid_action
   - payload_validation_failed
   - external_state_mismatch
   - approval_blocked

4. 在任务详情里展示：
   - 当前状态
   - 上一步动作
   - 当前允许动作
   - 最近失败原因

### Deliverable

- 状态驱动执行审计面板
- 新增日志字段

---

## Phase 4 — 首个业务适配器落地（1–2 周）

目标：做一个真实可用的业务 Agent。

### 推荐优先级

1. 报销申请 Agent
2. 采购审批 Agent
3. 工单流转 Agent

### 工作项

1. 实现样板适配器
   - `get_state`
   - `list_available_actions`
   - `execute_action`

2. 把该适配器接到：
   - executor
   - workflow
   - approval
   - audit

3. 加入真实集成测试

### Deliverable

- 一个端到端可演示场景

---

## Phase 5 — Simulation / Dry Run（0.5–1 周）

目标：先看路，再执行。

### 工作项

1. 支持 dry-run mode
2. 返回“当前允许动作 + 推荐下一步 + 预期状态”
3. 提供管理端测试入口

### Deliverable

- 模拟执行模式
- 不改外部系统状态的演练入口

---

## Phase 6 — 产品化与推广（1 周+）

目标：从样板能力变成平台能力。

### 工作项

1. 管理后台支持动作策略配置
2. 文档沉淀
3. rollout checklist
4. 第二个、第三个业务适配器接入

### Deliverable

- 平台级 State + Actions 能力
- 多业务场景可复用

---

## 6. 技术设计原则

### 6.1 只允许从 allowed actions 中选

Agent 不能自由从所有工具中选动作。  
对强状态业务，只能从后端返回的 `available_actions` 中挑选。

### 6.2 每个 mutating action 后必须 refresh state

禁止：

```text
基于旧状态连续推演 3 步
```

必须：

```text
执行一步 → 重读状态 → 再选下一步
```

### 6.3 动作语义必须结构化

不能依赖按钮文案或自然语言猜测动作含义。  
每个动作必须有明确：

- action name
- business meaning
- payload schema
- risk level
- expected next state

### 6.4 高风险动作默认不自动执行

如：

- 提交审批
- 取消申请
- 删除记录
- 发起付款
- 最终确认

默认至少需要：

- confirm
或
- approval

### 6.5 出现状态不一致时立即停机上报

如果：

- `expected_next_state` 与实际返回不一致
- 外部系统状态缺字段或无法解释
- 动作执行成功但状态未变化

则运行时必须：

- 立即停止 loop
- 记录 transition mismatch
- 把对象转入人工处理或调试模式

---

## 7. 当前实现进展（最后更新：2026-06-06，第二次修订）

### ✅ Phase 0–6（已完成）

**核心契约与数据结构**（`stateful_contract.py`，179 行）
- `StateSnapshot` / `ActionSpec` / `ActionResult` / `StatefulActionDecision`
- `StatefulExecutionResult` / `StateTransitionRecord`
- `StatefulObjectAdapter` Protocol + `StatefulAdapterBase` ABC

**Runtime 主循环**（`stateful_runtime.py`，512 行）
- `run_stateful_step_loop()`：多步循环，每步 refresh state
- `run_stateful_single_step()`：单步执行，含 guard 判断
- 已支持止损：`state_mismatch`、`action_failed`、`no_available_actions`、`max_steps_reached`
- 已支持挂起：`approval_required`、`confirmation_required`、`human_only`

**Action Guard**（`action_guard.py`，192 行）
- `ActionGuard.require_allowed_action()`：拒绝不在 allowed set 中的动作
- `ActionGuard.validate_payload()`：schema 校验
- `ActionGuard.resolve_policy()`：4 级策略解析（ActionSpec 默认 → tenant DB → global DB → wildcard DB）
- `ActionGuardViolation` 异常分类

**Adapter Registry**（`stateful_adapter_registry.py`，67 行）
- `StatefulAdapterRegistry.register_adapter()` / `create()` / `list_kinds()`
- 默认注册：`approval`、`ticket`、`reimbursement` 三种 adapter
- `get_stateful_adapter_registry()` 全局单例

**三个业务适配器**
- `stateful_approval_adapter.py`（240 行）：审批流，6 个状态，完整 allowed actions
- `stateful_ticket_adapter.py`（360 行）：工单流转，多状态机，含 demo 数据创建
- `stateful_reimbursement_adapter.py`：报销申请流，6 个状态，8 个动作（DB 持久化）
- `stateful_procurement_adapter.py`：采购申请，7 状态，9 动作（DB 持久化）
- `stateful_contract_review_adapter.py`：合同审批，6 状态，7 动作（DB 持久化）
- `stateful_incident_adapter.py`：运维事故，6 状态，8 动作（DB 持久化）

**Debug API**（`stateful_runtime_debug.py`）
- `GET /approvals/{id}/state`、`/simulate`、`/step`
- `GET /tickets/{id}/state`、`/simulate`、`/step`、`POST /tickets/demo`
- `GET /reimbursements/{id}/state`、`/step`、`POST /reimbursements/demo`
- `GET /procurements/{id}/state`、`/step`、`POST /procurements/demo`
- `GET /contracts/{id}/state`、`/step`、`POST /contracts/demo`
- `GET /incidents/{id}/state`、`/step`、`POST /incidents/demo`
- `GET /history/{kind}/{entity_id}`：单实体历史 timeline
- `GET /needs-review`：人工介入队列

**调试前端面板**
- `ApprovalStatefulDebug.tsx`：当前状态、允许动作、单步执行、transition timeline、summary diff
- `TicketStatefulDebug.tsx`：工单调试面板

**测试覆盖**（9 个测试文件，51+ 个测试）
- `test_stateful_runtime.py`：guard 拒绝、payload 校验、state refresh、approval 挂起、mismatch 止损
- `test_stateful_approval_adapter.py`：approval 适配器全流程
- `test_stateful_ticket_adapter.py`：ticket 适配器全流程
- `test_stateful_reimbursement_adapter.py`（11 个测试）：报销全流程 + 边界场景
- `test_stateful_procurement_adapter.py`（11 个测试）：采购全流程 + 边界场景
- `test_stateful_contract_review_adapter.py`（11 个测试）：合同审批全流程 + 边界场景
- `test_stateful_incident_adapter.py`（12 个测试）：事故管理全流程 + 边界场景
- `test_stateful_runtime_debug_router.py`：debug API 端点
- `test_stateful_executor_integration.py`：Executor 集成测试（含 registry 6 adapter 断言）

### ✅ Phase 7 — 接入主 AgentExecutor（已完成）

**`executor.py` 新增 stateful 分支：**
- `_is_stateful_runtime_task()`：检测 task_context 中的 `stateful_runtime` 配置
- `_execute_stateful_runtime()`：stateful loop 完整执行路径
- `_build_stateful_llm_decision()`：LLM 基于 state + allowed_actions 做结构化决策
- `_parse_stateful_decision_content()`：解析 LLM 输出的 JSON 决策
- `_stateful_decision_provider_from_context()`：支持 bypass（测试用）/ LLM 两种决策模式

**触发方式：** 在 `task_context` 中设置：
```json
{
  "stateful_runtime": {
    "kind": "approval",
    "entity_id": "expense-123",
    "mode": "loop"
  }
}
```

### ✅ Phase 8 — Adapter Registry（已完成）

`stateful_adapter_registry.py` 已提供统一解析入口，Executor 与 debug API 均通过 registry 获取 adapter，无硬编码分支。

### ✅ Phase 9 — Decision Contract（已完成）

LLM 决策输入为结构化 prompt（state + allowed_actions + payload_schema + policy hints），输出为标准 JSON：
```json
{"action_name": "approve", "payload": {"comment": "..."}, "reason": "..."}
```
Executor 对决策结果做 action 合法性校验 + payload schema 校验。

### ✅ Phase 10 — 异常处理与止损（已完成，2026-06-06）

- Runtime 层面的失败分类：`stale_state`、`action_failed`、`state_mismatch`、`no_available_actions`
- Guard 层面的拒绝：`action_not_allowed`、`payload_invalid`
- `stop_on_state_mismatch` 参数控制遇到不一致时的止损行为
- `non_idempotent_retry_blocked`：已实现，`stateful_runtime.py:205`；非幂等动作二次尝试时立即阻断
- `needs_human_review` 标记：已实现；mismatch / guard violation / non-idempotent retry 均自动置位
- **`allow_idempotent_retry` 开关**：已实现（migration 0084）；默认 `False`（阻断），管理员可通过 Phase 12 策略面对特定 entity_kind/action 设为 `True` 允许重试

### ✅ Phase 11 — 观测性与回放（已完成，2026-06-06）

- `persist_transitions()` 方法（`stateful_runtime.py:406`）：将每次状态转移写入 `stateful_transitions` DB 表
- `StatefulTransition` ORM 模型（`models.py:367`）：记录 before_state / action / after_state / policy_mode / reason / mismatch flag
- Executor 在任务结束时调用 `persist_transitions()`（`executor.py:641`）
- `ApprovalStatefulDebug.tsx` / `TicketStatefulDebug.tsx` 已渲染 transition timeline + summary diff
- **跨任务历史审计 UI 已完成**：`GET /stateful-policies/audit/transitions` 支持按 entity_kind / entity_id / task_id / needs_human_review / stop_reason 筛选，分页，最大 500 条
- `StatefulTransitionAudit.tsx`：管理员专属审计页面，可查询任意 entity 的跨任务完整状态转移历史，含 mismatch 标记、policy mode 标签、展开行详情

### ✅ Phase 12 — 管理与策略面（已完成，2026-06-06）

- `StatefulActionPolicy` ORM 模型（`models.py:341`）：支持 tenant / entity_kind / action_name 三维配置
- `routers/stateful_policies.py`：完整 CRUD API，含审计日志
- `action_guard.py:resolve_policy()`：4 级优先级覆盖（ActionSpec 默认 → tenant-specific → global → wildcard）
- `StatefulPolicyAdmin.tsx`：管理员前端配置页面
- **`allow_idempotent_retry` 字段已加入策略 CRUD**（`PolicyCreate` / `PolicyUpdate` / `_serialize`）

### ✅ Phase 13 — 多业务对象扩展（已完成）

已完成：
- ✅ `stateful_reimbursement_adapter.py`：报销申请全流程，6 状态，8 动作，**真实 DB 持久化**（`Reimbursement` ORM + migration 0085）
- ✅ `stateful_procurement_adapter.py`：采购申请，7 状态，9 动作（draft → pending_approval → approved → po_issued → received）
- ✅ `stateful_contract_review_adapter.py`：合同审批，6 状态，7 动作（draft → under_review → approved → signed）

待扩展（下一阶段）：
- incident / ops workflow（运维工单）

---

### 里程碑状态

| 里程碑 | 验收标准 | 状态 |
|--------|---------|------|
| **M1 — PoC 成立** | approval + ticket 跑通 stateful loop，debug API 可用 | ✅ 已达成 |
| **M2 — 接入主执行器** | 至少 1 类 agent 通过 AgentExecutor 跑 stateful loop，无需手工点 debug API | ✅ 已达成 |
| **M3 — 生产可用** | 具备 mismatch 止损、transition audit、策略控制自动执行范围 | ✅ 已达成（2026-06-06） |
| **M4 — 平台化** | 新业务对象接入只需写 adapter，无需修改主执行器 | ✅ 已达成（Registry 机制） |
| **M5 — 业务覆盖** | 3 个以上真实业务对象接入，transition audit 可跨任务查询 | ✅ 已达成（reimbursement + procurement + contract_review） |

---

### 当前最优先项（下一阶段）

✅ 已全部完成（两个轮次）：
1. ~~跨任务历史审计 UI~~ — `StatefulTransitionAudit.tsx` + `GET /audit/transitions`
2. ~~全局 replay / retry policy 配置~~ — `allow_idempotent_retry` 字段 + migration 0084
3. ~~Phase 13 第一个真实业务对象~~ — `ReimbursementStatefulAdapter`（报销申请，DB 持久化）
4. ~~per-agent 策略粒度~~ — `agent_id` 维度加入策略体系（8 级优先级查找）
5. ~~procurement adapter~~ — `ProcurementStatefulAdapter`（7 状态，9 动作）
6. ~~contract review adapter~~ — `ContractReviewStatefulAdapter`（6 状态，7 动作）

**本轮次继续完成（可选项）：**

1. ~~incident / ops workflow adapter~~ — `IncidentStatefulAdapter`（6 状态，8 动作）
2. ~~per-agent policy 前端~~ — `StatefulPolicyAdmin.tsx` 增加 `agent_id` 字段 + `allow_idempotent_retry` 开关
3. ~~procurement / contract / incident DB 持久化~~ — `ProcurementRequest` + `ContractReview` + `Incident` ORM + migration 0086

---

## 8. 从 PoC 到通用 Agent 行为的实施路线图

下面这部分是当前最重要的 roadmap。目标不再是“证明能做”，而是把它接入 AIOS 主执行路径，变成平台能力。

### Phase 7 — 接入主 AgentExecutor ✅ 已完成

目标：让 stateful runtime 从 debug-only 模式进入真实 agent 执行链路。

#### 工作项

1. 在 `AgentExecutor` 增加 stateful 分支
   - 文件：`backend/app/agent/executor.py`
   - 新增执行模式：
     - 普通 ReAct 任务：继续现有逻辑
     - `stateful_loop` 任务：走状态驱动执行

2. 定义任务级路由入口
   - 在 task / agent 配置里增加：
     - `runtime_mode = "standard" | "stateful"`
     - `stateful_object_type`
     - `stateful_entity_id`

3. 接入 decision provider
   - LLM 不再自由从全部工具里选
   - 只能基于：
     - `current_state`
     - `available_actions`
     - `action_schema`
     - `policy summary`
     做决策

4. 每次 mutating action 后强制 refresh
   - 任何状态变化动作执行后，必须重新读取最新状态

#### Deliverable

- Executor 中真实可用的 `stateful_loop`
- 至少 1 个 agent type 可在生产代码路径中使用

---

### Phase 8 — 通用 Adapter Registry ✅ 已完成

目标：不要让每个业务对象都靠硬编码分支接入。

#### 工作项

1. 新增 adapter registry
   - 建议文件：`backend/app/services/stateful_registry.py`

2. 标准化 adapter 元数据
   - `object_type`
   - `display_name`
   - `risk_profile`
   - `supports_simulation`
   - `supports_human_override`

3. 提供统一解析入口

```python
resolve_adapter(object_type: str) -> StatefulBusinessAdapter
```

4. Executor 与 debug API 都走 registry，而不是手写 if/else

#### Deliverable

- `ApprovalStatefulAdapter` / `TicketStatefulAdapter` 注册化
- 新对象接入只需新增 adapter + 注册，不改主循环

---

### Phase 9 — 通用 Decision Contract ✅ 已完成

目标：让 LLM 决策受约束，而不是靠自然语言自由发挥。

#### 工作项

1. 统一 LLM 决策输入结构
   - `state`
   - `allowed_actions`
   - `payload_schema`
   - `policy hints`
   - `recent transition history`

2. 统一决策输出结构

```json
{
  "action_name": "approve",
  "payload": { "comment": "looks good" },
  "reason": "invoice uploaded and no missing docs"
}
```

3. executor 中增加决策校验
   - action 必须在 allowed set 中
   - payload 必须满足 schema
   - reason 必须可审计

#### Deliverable

- 结构化 decision protocol
- stateful agent prompt / planner contract

---

### Phase 10 — 异常处理与路由止损 ✅ 已完成

目标：把这套能力从 happy path 拉到生产可靠性。

#### 工作项

1. 明确失败分类
   - `stale_state`
   - `action_not_allowed`
   - `payload_invalid`
   - `external_state_mismatch`
   - `non_idempotent_retry_blocked`

2. 增加止损策略
   - mismatch 立即停机
   - 某些动作禁止自动重试
   - 关键动作失败后转人工

3. 增加 replay / retry strategy
   - 只允许对 idempotent action 重试
   - 高风险动作默认不可自动重放

4. 增加 “人工接管” 标记
   - executor 发现异常后，可把对象标成：
     - `needs_human_review`

#### Deliverable

- 生产级失败处理策略
- 不一致状态下的可控停机行为

---

### Phase 11 — 观测性与回放 ✅ 已完成

目标：不仅能跑，还要能解释“为什么这么跑”。

#### 工作项

1. 状态驱动 transition log 持久化
   - `before_state`
   - `selected_action`
   - `payload_summary`
   - `after_state`
   - `policy_mode`
   - `reason`

2. 加入任务详情或专用调试页
   - timeline
   - summary diff
   - mismatch tag

3. 支持 replay / audit review
   - 可复现某次 route 选择

#### Deliverable

- 平台级 transition audit
- 调试与解释能力从 PoC 页面推广到系统能力

---

### Phase 12 — 管理与策略面 ✅ 已完成

目标：让它真正成为平台能力，而不是开发者专用功能。

#### 工作项

1. 新增 action policy admin 配置
   - `auto`
   - `confirm_required`
   - `approval_required`
   - `human_only`

2. 增加 tenant / agent 级开关
   - 哪些 agent 可启用 stateful runtime
   - 哪些业务对象允许自动执行

3. 增加策略覆盖机制
   - 全局默认策略
   - adapter 默认策略
   - tenant override

#### Deliverable

- 可配置的 stateful policy center
- 管理员可控，不靠代码改策略

---

### Phase 13 — 多业务对象扩展 ✅ 已完成

目标：从两个参考对象扩展到真正的企业业务覆盖。

#### 已接入业务对象（6 个 adapters 注册于 Registry）

1. ✅ approval — 审批申请（DB 持久化）
2. ✅ ticket — 工单处理（DB 持久化）
3. ✅ reimbursement — 报销申请（DB 持久化，migration 0085）
4. ✅ procurement — 采购申请（7 状态，9 动作）
5. ✅ contract_review — 合同审批（6 状态，7 动作）
6. ✅ incident — 运维事故（6 状态，8 动作，含 escalate / reopen）

#### 验收标准 ✅

- 新对象接入无需改 executor 主逻辑 ✅
- 只需：定义状态 / allowed actions / payload schema / 实现 adapter ✅

---

## 9. 当前推荐推进顺序

从今天这个 PoC 状态出发，建议顺序如下：

1. Phase 7：接入主 `AgentExecutor`
2. Phase 8：Adapter Registry
3. Phase 9：Decision Contract
4. Phase 10：异常处理与止损
5. Phase 11：观测性与回放
6. Phase 12：管理与策略面
7. Phase 13：扩展更多业务对象

原因很简单：

- 现在最缺的不是更多 demo
- 而是把现有 PoC 接进真正的 agent 执行主链

---

## 10. 里程碑定义

### M1 — PoC 成立 ✅ 已达成

验收：

- approval + ticket 都能跑通 stateful loop ✅
- debug API / debug panel 可用 ✅

### M2 — 接入主执行器 ✅ 已达成（2026-06-06）

验收：

- 至少 1 类 agent 通过 `AgentExecutor` 跑 stateful loop ✅
- 不需要手工点 debug API ✅
- `test_stateful_executor_integration.py` 覆盖全路径 ✅

### M3 — 生产可用 ✅ 已达成（2026-06-06）

验收：

- 具备 mismatch 止损 ✅（`stop_on_state_mismatch` + `needs_human_review`）
- 有 transition audit ✅（`persist_transitions()` + `StatefulTransition` DB 表）
- 可通过策略控制自动执行范围 ✅（`StatefulActionPolicy` + admin UI）

### M4 — 平台化 ✅ 已达成

验收：

- 新业务对象接入只需写 adapter ✅（Registry 机制）
- 无需修改主执行器 ✅

---

## 11. 当前结论（2026-06-06，第三次修订）

**M1–M5 全部达成，所有业务适配器均已 DB 持久化。**

> AIOS 已具备完整的状态驱动 Agent Runtime：  
> 止损、audit 持久化、跨任务 audit UI、策略管理（含 per-agent 粒度）、idempotent-retry 开关均已上线。  
> 六个业务适配器（approval / ticket / reimbursement / procurement / contract_review / incident）  
> 全部注册于 Registry，全部支持 DB 持久化，可通过 AgentExecutor 驱动。

~~所有可选项均已完成~~：
1. ~~procurement / contract DB 持久化~~ — `ProcurementRequest` + `ContractReview` ORM + migration 0086
2. ~~incident adapter DB 持久化~~ — `Incident` ORM + migration 0086

---

## 7. 成功指标

### 业务成功指标

- 强状态业务的自动执行成功率提升
- 错误路径传播率下降
- 人工介入集中在高风险动作，而不是低级状态判断错误

### 技术成功指标

- 每个 mutating action 都有完整审计链
- 不允许未授权动作绕过 Action Guard
- 每个场景至少有一组状态机测试

### 产品成功指标

- 可以复用到多个业务系统
- 新适配器只需要实现 3 个接口即可接入

---

## 8. 不建议一开始就做的事情

以下方向建议后置：

1. 通用可视化状态机设计器
2. 所有业务系统统一建模
3. 完全自动化高风险动作
4. 用 prompt 约束替代结构化动作协议

先做一条通路，比先做一个大全平台更重要。

---

## 9. 推荐下一步

建议立刻开始的顺序：

1. 确定样板场景（报销 / 采购 / 工单）
2. 定义状态与动作协议
3. 做 runtime 最小循环
4. 接入 Action Guard
5. 做第一条业务闭环

最小可行目标：

> 在 AIOS 中做出一个“不会背死流程、而是根据当前状态选择下一步”的报销申请 Agent。

---

## 10. 相关代码位置

现有强相关文件：

- `backend/app/agent/executor.py`
- `backend/app/services/workflow_engine.py`
- `backend/app/services/approval.py`
- `backend/app/routers/approvals.py`
- `backend/app/routers/audit.py`
- `backend/app/routers/conversations.py`

建议新增：

- `backend/app/services/stateful_runtime.py`
- `backend/app/services/action_guard.py`
- `backend/app/schemas/stateful_actions.py`

---

## 11. 一句话结论

AIOS 完全适合做这种 **“看当前状态，再选下一步”** 的企业 Agent。  
真正需要补的，不是更复杂的 prompt，而是：

- 状态建模
- 允许动作协议
- 动作守卫
- 状态刷新循环
- 高风险动作治理

这套能力一旦做出来，会成为 AIOS 相对通用 Agent 平台的一个很强差异化点。
