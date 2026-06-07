# Roadmap：Router Agent — 每条消息的智能 Agent 路由

> 状态：Draft · 创建：2026-05-29 · Owner：TBD  
> 目标分支：`feature/router-agent`

---

## 1. 背景与问题

### 1.1 现有路由的架构缺陷

当前系统的 Agent 绑定逻辑分散在 `routers/conversations.py` 里，采用「**对话级黏性绑定**」策略：

```
消息到来 → 精确名字匹配 / 关键词规则 / cosine > 0.33 → conv.agent_id 持久化
```

三个核心问题：

**① 绑定粒度太粗（Conversation-level Stickiness）**  
一个 30 轮的会话，前 10 轮谈财务、中 10 轮问技术、后 10 轮要起草邮件，全程被第一条消息的绑定锁死。Release 逻辑只覆盖搜索/地点/日历/能力问题四种场景，覆盖不了实际的 topic shift。

**② Threshold 0.33 精度不足**  
Cosine similarity 是语言空间距离，不是业务语义理解。同一语言域（如「请帮我处理一下这份文件」）下，多个 Agent 可能都高于 0.33，系统选最高分的那个，但那个 Agent 可能根本没有所需工具。

**③ @mention 设计语义混乱**  
输入框里的 `@mention` 给用户「单次路由」的直觉，但底层和工具栏 Select 做同一件事（PUT `conv.agent_id`），永久改变整个会话绑定。另有 CJK Agent 名的文字清除 bug（见下文 Bug Fix 部分）。

### 1.2 目标状态

```
每条消息独立路由（per-message），用户可按需显式覆盖。

Priority 1: 用户 @mention（单次，发完即清）
Priority 2: 用户工具栏锁定（会话级，显式操作）
Priority 3: Router Agent（LLM 调用，每条消息 fallback）
```

---

## 2. 方案设计

### 2.1 三层路由模型

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 1: 显式单次覆盖（@mention）                            │
│  用户在输入框打 @AgentName，仅对本条消息生效，发完自动清除    │
├──────────────────────────────────────────────────────────────┤
│  Layer 2: 会话锁定（Toolbar Lock）                           │
│  用户在工具栏下拉框选定，PUT conv.agent_id，整个会话有效     │
│  × 可随时清除（清除 → 回到 Layer 3）                         │
├──────────────────────────────────────────────────────────────┤
│  Layer 3: Router Agent（默认智能路由）                        │
│  LLM_FAST_MODEL 调用，根据当前消息 + 最近 3 轮上下文决策     │
│  结果不持久化 conv.agent_id，只影响本条消息的 task_context   │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Router Agent 的 Prompt 设计

```
System:
你是一个 Agent 路由助手。
根据用户最新的消息（以及最近几轮对话历史），从下方 Agent 列表中选出最合适的 Agent。
如果没有明显合适的 Agent，返回 null。
只返回 JSON，不要解释。

Agent 列表（JSON）：
[
  { "id": "...", "name": "客服专员", "description": "...", "tools": ["crm_query", "ticket_create"] },
  { "id": "...", "name": "财务分析师", "description": "...", "tools": ["report_generate", "data_analyze"] },
  ...
]

User:
最近对话：
[User]: ...
[Assistant]: ...
[User]: {当前消息}

请返回：
{"agent_id": "<id 或 null>", "confidence": 0.0~1.0, "reason": "一句话"}
```

关键设计决策：
- **工具列表纳入 prompt**：LLM 能判断 Agent 有没有能力完成任务，不只是名字/描述相似
- **confidence 字段**：低于 0.5 时不路由（等同于 null），避免错误绑定
- **reason 字段**：用于前端气泡显示 + 后端 audit log
- **最近 3 轮上下文**：帮助识别 topic shift，但不传完整历史（防止 token 爆炸）

### 2.3 后端架构变更

#### 新增：`app/services/agent_router.py`

```python
"""
Agent Router Service
路由逻辑与 conversations.py 解耦，独立可测。
"""

@dataclass
class RouteResult:
    agent_id: str | None    # None = 不路由
    confidence: float
    reason: str
    source: str             # "mention" | "locked" | "router" | "none"


def route(
    message: str,
    recent_turns: list[dict],   # [{"role": "user/assistant", "content": "..."}]
    available_agents: list[dict],  # [{"id", "name", "description", "tools"}]
    fast_model: str | None = None,
    timeout: float = 2.0,
) -> RouteResult:
    """
    调用 LLM_FAST_MODEL 选出最合适的 Agent。
    超时或出错时返回 RouteResult(agent_id=None, source="none")。
    """
```

#### 修改：`routers/conversations.py` — `send_message()`

```python
# 新的优先级链（替换现有 embedding 路由）

# Layer 1: 用户 @mention（单次，不写 conv.agent_id）
if data.agent_id:
    effective_agent_id = data.agent_id
    task_context["_custom_agent_id"] = data.agent_id
    task_context["_agent_route_source"] = "mention"

# Layer 2: 会话锁定
elif conv.agent_id:
    effective_agent_id = conv.agent_id
    task_context["_custom_agent_id"] = conv.agent_id
    task_context["_agent_route_source"] = "locked"

# Layer 3: Router Agent
else:
    route_result = _call_router_agent(message, recent_turns, agents, timeout=2.0)
    if route_result.agent_id:
        effective_agent_id = route_result.agent_id
        task_context["_custom_agent_id"] = route_result.agent_id
        task_context["_agent_route_source"] = "router"
        task_context["_agent_route_reason"] = route_result.reason
    # 不写 conv.agent_id → 不持久化
```

**删除的现有代码：**
- `_auto_bind_agent()` 及所有 embedding 路由逻辑
- `_should_release_specialist_agent()` — 不再需要，per-message 天然无此问题
- `_auto_bind_by_business_intent()` — IR 事件关键词规则合并进 Router Agent prompt
- `_looks_like_*()` 系列函数（6 个）
- `_get_agent_embedding()` / `_agent_embed_cache` / `_SIMILARITY_THRESHOLD`

**保留：**
- `PUT /conversations/{id}/agent` 端点 — 工具栏锁定仍需
- `_is_execution_approval()` — 审批确认逻辑与路由无关

### 2.4 Task Context 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `_agent_route_source` | `str` | `mention` / `locked` / `router` / `none` |
| `_agent_route_reason` | `str` | Router Agent 给出的理由（仅 source=router 时有） |

这两个字段随 task 持久化，供审计日志、前端消息气泡使用。

### 2.5 前端变更

#### ComposeBar.tsx — 修复 @mention CJK bug

```ts
// 修复前：\w 不匹配中文/日文
const after = inputText.slice(mentionAnchorIdx).replace(/^@\w*/, '')

// 修复后：匹配任意非空白非@ 字符（与检测侧一致）
const after = inputText.slice(mentionAnchorIdx).replace(/^@[^\s@]*/, '')
```

#### ComposeBar.tsx — @mention 改为单次路由语义

```ts
function handleMentionSelect(agentId: string) {
  // 不再调用 setMentionedAgentId（不持久化到会话）
  // 改为临时存到 oneTimeMentionRef，handleSend 消费后清除
  oneTimeMentionRef.current = agentId
  // 移除 @xxx 文字
  ...
  setMentionSearch(null)
}
```

```ts
// handleSend 里
const agentId = oneTimeMentionRef.current || mentionedAgentId || null
if (agentId) payload.agent_id = agentId
oneTimeMentionRef.current = null   // 发完清除单次 mention
```

#### ChatToolbar.tsx — 工具栏 Select 明确标记为「锁定」

- placeholder 文案改为「🔒 锁定 Agent」（区别于 @mention 的单次路由）
- 选中后 Tag 显示「🔒 客服专员」，明确是会话级锁定

#### ChatMessages.tsx — 消息气泡显示路由来源

每条 assistant 消息右下角增加小标记：

```
🤖 客服专员 · 由 Router 选择        ← source=router
🤖 财务分析师 · 你指定的             ← source=mention
🔒 客服专员 · 会话锁定               ← source=locked
```

数据来源：`task.context._agent_route_source` + `._agent_route_reason`，通过现有 `GET /tasks/{id}` 或消息元数据暴露。

#### ChatToolbar.tsx — 修复 filterOption

```tsx
// 修复前（依赖 JSX 内部结构，脆弱）
filterOption={(input, opt) =>
  (opt?.label as any)?.props?.children[1]?.toLowerCase().includes(input.toLowerCase()) ?? false
}

// 修复后（独立 search 字段）
options={availableAgents.map((a) => ({
  value: a.id,
  label: <span>...<RobotOutlined/>{getAgentName(a, lang)}</span>,
  search: getAgentName(a, lang).toLowerCase(),   // ← 增加
}))}
filterOption={(input, opt) =>
  (opt as any).search?.includes(input.toLowerCase()) ?? false
}
```

---

## 3. 实施计划

### Phase 1：Bug Fix（1 天，可立即合并）

| # | 文件 | 改动 | 影响 |
|---|------|------|------|
| 1.1 | `ComposeBar.tsx` | `@mention` CJK 文字清除 bug：`\w*` → `[^\s@]*` | 修复中文/日文 Agent 选择后残留文字 |
| 1.2 | `ChatToolbar.tsx` | `filterOption` 改用 `opt.search` | 搜索不再依赖 JSX 结构 |
| 1.3 | `ChatToolbar.tsx` | `@mention` 语义改为单次（`oneTimeMentionRef`） | 与工具栏 Select 的会话锁定区分 |

### Phase 2：Router Agent 后端（3 天）

| # | 文件 | 改动 |
|---|------|------|
| 2.1 | `app/services/agent_router.py` | 新建 `AgentRouter` 服务，`route()` 方法 + 单元测试 |
| 2.2 | `routers/conversations.py` | 替换 embedding 路由 → 三层优先级链；删除 6 个 `_looks_like_*` 函数 |
| 2.3 | `routers/conversations.py` | `task_context` 写入 `_agent_route_source` / `_agent_route_reason` |
| 2.4 | `tests/test_agent_router.py` | Router Agent 单元测试（mock LLM）：mention / locked / router / none 四条路径 |

### Phase 3：前端路由可见性（2 天）

| # | 文件 | 改动 |
|---|------|------|
| 3.1 | `ChatMessages.tsx` | 消息气泡增加 Agent 归属标记（路由来源 + Agent 名） |
| 3.2 | `ChatToolbar.tsx` | 工具栏 Select placeholder 改为「🔒 锁定 Agent」，已锁定时 Tag 前加锁图标 |
| 3.3 | `api/` 或消息模型 | 暴露 `task.context._agent_route_source` 给前端（可复用现有 task 接口） |

### Phase 4：观测与调优（上线后持续）

| # | 项目 | 说明 |
|---|------|------|
| 4.1 | Router Agent audit log | 每次路由决策写入结构化日志（agent_id, confidence, reason, latency_ms） |
| 4.2 | 路由准确率监控 | 通过用户 @mention 覆盖 Router 决策的次数 / 比率，反映路由质量 |
| 4.3 | Confidence 阈值调优 | 初始 0.5，根据 audit log 中的覆盖率调整 |
| 4.4 | Agent 描述优化 | Router 的准确率强依赖 Agent 的 `description` 质量，需建立描述规范 |

---

## 4. 性能与风险评估

### 4.1 Router Agent 延迟

| 场景 | 延迟 | 处理方式 |
|------|------|---------|
| LLM_FAST_MODEL 正常 | ~500ms | 可接受（用户感受不到，消息已乐观显示） |
| 超时（>2s） | → fallback: `agent_id=None` | 无 Agent 路由，系统默认 prompt 执行 |
| 嵌入服务不可用 | — | 与现有 embedding 路由同等风险，router 不依赖 embedding |

`timeout=2.0` 硬限制在 `ThreadPoolExecutor` 中执行，不会阻塞请求（参考现有 `_auto_bind_agent` 的 3s 限制实现方式）。

### 4.2 Agent 列表规模

| Agent 数 | Prompt Token 估算 | 是否可行 |
|---------|------------------|---------|
| 10 个 | ~800 tokens | ✅ 无问题 |
| 30 个 | ~2400 tokens | ✅ 可行 |
| 60 个 | ~4800 tokens | ⚠️ 需要过滤：只传当前用户可见的 Agent |
| 100+ 个 | >8000 tokens | ❌ 需要分级：先 embedding 粗筛 Top 10，再 LLM 精选 |

**初期实现：传用户可见的全部 Active Agent（通常 < 30 个）。**  
**超过 50 个时启用 embedding 粗筛 → LLM 精选的两阶段策略（Phase 4 延伸项）。**

### 4.3 向后兼容

- 现有 `conv.agent_id` 字段继续保留（工具栏锁定写，不删除）
- `PUT /conversations/{id}/agent` 端点不变
- `_custom_agent_id` 在 `task_context` 里的键名不变（executor.py 不动）
- 删除 `_auto_bind_agent` 等函数前，先跑全量测试确认无外部引用

---

## 5. 关键文件一览

### 后端

| 文件 | 动作 | 说明 |
|------|------|------|
| `app/services/agent_router.py` | **新建** | Router Agent 服务主体 |
| `app/routers/conversations.py` | **修改** | 替换路由逻辑，删除 embedding 相关函数 |
| `tests/test_agent_router.py` | **新建** | Router 单元测试 |

### 前端

| 文件 | 动作 | 说明 |
|------|------|------|
| `pages/chat/components/ComposeBar.tsx` | **修改** | @mention 改单次 + CJK bug 修复 |
| `pages/chat/components/ChatToolbar.tsx` | **修改** | 锁定语义 + filterOption 修复 |
| `pages/chat/components/ChatMessages.tsx` | **修改** | Agent 归属气泡标记 |
| `pages/chat/ChatPage.tsx` | **修改** | `oneTimeMentionRef` 逻辑 |

---

## 6. 验收标准

| 场景 | 预期行为 |
|------|---------|
| 用户 `@客服专员` 发一条消息，不再 @mention | 第一条路由给客服专员；第二条由 Router Agent 决定（不再锁死） |
| 工具栏锁定「财务分析师」后发 10 条消息 | 全部路由给财务分析师，消息气泡显示「🔒 财务分析师 · 会话锁定」 |
| 无 Agent 可信匹配（confidence < 0.5） | 消息正常发送，不路由任何 Agent，执行默认系统 prompt |
| Router Agent 调用超时（> 2s） | 消息正常发送，`_agent_route_source = "none"`，无报错 |
| `@日本语エージェント`（日文名） | @mention 文字正确从输入框清除（CJK bug 已修） |
| 搜索 Agent 下拉框输入中文 | 正确过滤，不因 JSX 结构变更而失效 |

---

> 参考：`docs/ROADMAP-model-mgmt-delegation.md`（相同分层设计思路）  
> 关联 bug：ComposeBar @mention CJK 清除、ChatToolbar filterOption 脆弱性
