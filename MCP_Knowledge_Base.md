# Goku-AIOS MCP 知识库

> 本文档整理了 Goku-AIOS 平台关于 MCP（Model Context Protocol）的完整实现知识、设计规范和最佳实践，供 Agent 学习和参考。

---

## 一、MCP 在 Goku-AIOS 中的定位

MCP（Model Context Protocol）是 Goku-AIOS 连接**外部能力**的标准协议层。平台内置 85+ 工具覆盖常规场景；MCP 则用于接入任意第三方服务、私有 API 或专业工具，使 Agent 能力边界可以无限扩展。

**核心区别：**
- **AI 工具（Tool）**：Goku-AIOS 内置的 Python `BaseTool` 子类，在 `tool_registry` 中注册，直接参与 ReAct 循环。
- **MCP 能力（MCPCapability）**：外部 MCP Server 暴露的端点，Goku-AIOS 称为"能力"（Capability），刻意不叫"工具"，以避免与内置工具命名冲突。
- **MCPToolWrapper**：将 MCP 能力包装成 `BaseTool`，名称格式为 `{server_code}__{capability_name}`，注册进 `ToolRegistry` 后对 Agent 透明。

---

## 二、数据模型

### 核心表结构

```
mcp_servers              — MCP Server 注册信息（连接配置、认证、风险控制）
mcp_capabilities         — Server 暴露的能力（工具端点）列表，status 字段控制生命周期
mcp_resources            — Server 暴露的资源（文件、数据等）
mcp_prompts              — Server 暴露的 Prompt 模板
mcp_health_records       — 健康探测历史（append-only）
mcp_call_logs            — 调用记录（append-only，已脱敏）
mcp_capability_authorizations  — 能力授权（Principal → Capability 的显式授权关系）
mcp_capability_blacklists      — 黑名单（强制拒绝特定 Principal 调用某能力）
mcp_external_connections       — 外部连接绑定（Server ↔ 外部系统账号）
mcp_permissions          — 权限配置
```

### 生命周期设计规范

| 表 | 删除方式 | 原因 |
|---|---------|------|
| `mcp_servers` | soft-delete（`deleted_at`） | 保留历史引用；`code` 全局唯一，软删后不可复用 |
| `mcp_capabilities` | `status` 字段（`active`/`inactive`） | 由上游 Server 同步驱动，不是管理员删除 |
| `mcp_health_records` / `mcp_call_logs` | append-only，永不删除 | 审计链路必须完整 |
| `mcp_resources` / `mcp_prompts` | soft-delete（`deleted_at`） | 同 servers |

### MCPServer 关键字段说明

```python
connection_type: 'http' | 'stdio' | 'sse'   # 连接方式
auth_type: 'none' | 'bearer' | 'header' | 'basic'  # 认证方式
auth_secret: Text   # 加密存储，明文永不落库，使用 encryption.encrypt_secret()
env_config: Text    # 加密 JSON，stdio 模式的环境变量
allow_agent_auto_invoke: bool   # 是否允许 Agent 自动调用（默认 False）
high_risk_confirm_required: bool  # 高风险操作是否需要人工确认
audit_enabled: bool   # 是否记录调用日志
```

---

## 三、连接方式

### 1. HTTP/SSE 模式
- `service_url` 指定 MCP Server 的 HTTP 端点
- 适合远程 MCP Server、云端 API

### 2. stdio 模式
- `start_command` 为完整命令行字符串（`shlex.split` 解析）
- `work_dir` 指定工作目录
- `env_config`（加密）注入环境变量
- 适合本地进程、Python/Node.js MCP Server

### 3. 认证
- `bearer`：HTTP `Authorization: Bearer <token>` 头
- `header`：自定义 header 名（`auth_header_name`）+ 值（`auth_secret`）
- `basic`：HTTP Basic Auth
- `none`：无认证

---

## 四、运行时架构

```
MCPServer DB 行
    ↓ build_runtime_config()       # 解密 secrets，构建 MCPServerConfig
MCPServerConfig (dataclass)
    ↓ MCPClientManager
MCPServerConnection (subprocess/HTTP 连接)
    ↓ manager.call_tool(server_code, capability_name, arguments)
结果返回
```

**关键设计：**
- `mcp_runtime.py` 是 DB → 运行时的唯一适配层，解密 secrets 后传给 Client，明文不回流到 API 响应。
- `MCPClientManager` 维护全局连接池，`server_code` 是稳定的外部 key（与 `.mcp.json` 约定一致）。
- 启动时加载所有 `status='enabled'` 且 `deleted_at IS NULL` 的 Server。

---

## 五、工具注册机制

MCP 能力通过 `MCPToolWrapper` 注册进 `ToolRegistry`：

```python
# 工具名格式：{server_code}__{capability_name}
# 例：file_parser__parse_document

class MCPToolWrapper(BaseTool):
    name = f"{server_name}__{tool_name}"      # 命名空间隔离，避免冲突
    description = f"[MCP:{server_name}] ..."  # LLM 可见的描述
    parameters = input_schema                  # JSON Schema，来自 MCP 同步
    permission_level = 2                       # 需要认证
    requires_approval = False                  # 授权门已管控，不再一刀切审批
```

**Agent 过滤规则：**
- 默认：所有 MCP wrappers 对 Agent 可见
- 显式禁止：Agent `allowed_tools` 中包含 `@mcp:none` → 严格模式，0 个 MCP wrapper
- 能力调用准入：通过 `invoke_principal_via_mcp` 的授权链管控

---

## 六、授权模型（Default-Deny）

**核心原则：未经授权，拒绝一切 MCP 调用。**

```
Agent 调用 MCP 能力
    ↓
invoke_principal_via_mcp(db, principal_type='agent', principal_id=agent_id, capability_id)
    ↓
① 检查 MCPCapabilityBlacklist → 命中则拒绝
② 检查 MCPCapabilityAuthorization → 未找到授权行则拒绝（ERR_NOT_AUTHORIZED）
③ 检查配额（quota_enabled + quota_limit/period）→ 超限则拒绝
④ 通过所有检查 → 消费配额 → 执行 MCP 调用 → 写 call_log
```

**授权表（mcp_capability_authorizations）字段：**
- `principal_type`：`agent` | `user` | `team` 等
- `principal_id`：对应 ID
- `capability_id`：MCPCapability.id
- `quota_enabled` / `quota_limit` / `quota_period`：配额控制
- `rate_limit`：速率限制

**错误码：**
- `MCP_CAPABILITY_NOT_AUTHORIZED`：无授权行
- `MCP_QUOTA_EXCEEDED`：配额超限
- `MCP_SERVER_DISABLED`：Server 已禁用

---

## 七、调用上下文要求

MCPToolWrapper 的 `execute()` 必须在 **Agent 上下文**中调用：

```python
# 必须：ctx.context 中包含 '_custom_agent_id'
agent_id = ctx.context.get('_custom_agent_id')

# 缺少 agent_id → 直接返回错误，不走 MCP
if not agent_id:
    return {"error": "需要在 Agent 上下文中调用", "error_code": "MCP_CAPABILITY_NOT_AUTHORIZED"}
```

**含义：** 默认对话（无指定 Agent）无法直接调用 MCP 能力，必须通过具体 Agent 路由。这是平台的安全设计——每次 MCP 调用都必须有可审计的 Agent 主体。

---

## 八、调用日志与脱敏规范

**原则：mcp_call_logs 绝不能含敏感数据。**

### 脱敏规则（_sanitize_args / _sanitize_value）

```python
# Key 名包含以下关键词 → 值替换为 "[REDACTED]"
SECRET_KEY_MARKERS = ("key", "token", "secret", "password", "passwd", "credential")

# Value 是 presigned URL（含 X-Amz-Signature 等签名 Query 参数）→ "[REDACTED]"

# 长字符串（>200 chars）→ 截断 + "+N chars truncated" 标记

# 嵌套 dict/list → 递归处理
```

### 输出脱敏（_summarize_output）
1. 先尝试 JSON parse → 走树形递归脱敏
2. JSON parse 失败 → 正则替换 presigned URL
3. 长度超 500 chars → 截断

### call_log 字段含义
- `input_summary`：脱敏后的入参（非原始参数）
- `output_summary`：脱敏+截断后的输出预览
- `invoke_type`：`mcp_test`（管理员测试）| `agent_auto`（Agent 自动调用）
- `result`：`success` | `failed`
- `response_time`：毫秒

---

## 九、能力同步机制

MCP Server 的能力（capabilities/resources/prompts）通过**同步**从 Server 拉取并存入 DB：

```
MCP Server（运行中）
    ↓ manager.list_tools(server_code)
MCPCapability 行（status='active'）
    ↓ last_synced_at 更新
Agent 工具池更新（registry 重新注册）
    ↓
mcp_knowledge.refresh_server_knowledge()  → KnowledgeDoc 更新（语义检索）
```

**同步状态：**
- `last_sync_status`：`success` | `partial_success` | `failed`
- `last_sync_error_message`：多 bucket 错误合并（格式：`<bucket>: <reason>; ...`）
- `auto_sync_enabled`：是否自动定时同步
- `sync_frequency`：`hourly` | `daily` | cron 表达式

**能力生命周期：**
- 上游 Server 移除某能力 → `status='inactive'`（不删除，历史 call_log FK 仍可解析）
- Server 禁用/软删 → 触发 `purge_server_knowledge()`，清除 KnowledgeDoc 和向量

---

## 十、知识库集成（MCP → Agent 语义检索）

`mcp_knowledge.py` 将 MCP 能力同步到 KnowledgeDoc，使 Agent 能通过语义检索发现可用能力：

```markdown
# MCP 能力目录:{server_name}（{server_code}）
source=mcp:{server_code}

## {capability_name}
- Server: `{server_code}`
- 说明: {description}
- 入参:
  - `param_name` (type, 必填/可选) — description
```

**触发时机：**
- 能力同步成功后 → `refresh_server_knowledge()`
- Server 禁用/软删 → `purge_server_knowledge()`
- Server 重新启用 → `refresh_server_knowledge()`

**隔离性：** 每个 Server 一个 KnowledgeDoc（`source=mcp:{code}`），Server 变更只影响自己的文档。

---

## 十一、健康探测

```python
# mcp_health_records 记录每次探测结果
health_status: 'normal' | 'abnormal' | 'unchecked'
consecutive_failures: int    # 连续失败次数（触发告警）
last_recovered_at: datetime  # 最近一次从 abnormal 恢复的时间
```

探测结果：
- 成功 → `health_status='normal'`，重置 `consecutive_failures`
- 失败 → `health_status='abnormal'`，`consecutive_failures+1`
- 首次注册 → `health_status='unchecked'`

---

## 十二、风险控制配置

```python
# MCPServer 风险控制字段
allow_agent_auto_invoke: bool       # 关键开关：False 则 Agent 无法自动调用
high_risk_confirm_required: bool    # True = 高风险操作需人工确认
rate_limit_config: JSON             # 速率限制（calls/window）
circuit_breaker_config: JSON        # 熔断配置（失败阈值/恢复时间）
audit_enabled: bool                 # 是否写 call_log
```

**最佳实践：**
- 新 Server 接入时，`allow_agent_auto_invoke` 默认 `False`，测试通过后再开启
- 涉及写操作/支付/删除的能力，`high_risk_confirm_required=True`
- 外部 API 必须配置 `rate_limit_config`，防止配额耗尽
- 所有生产 Server `audit_enabled=True`

---

## 十三、外部连接（MCPExternalConnection）

`mcp_external_connections` 表用于绑定 MCP Server 与外部系统账号（如 OAuth token、API Key 绑定的用户）：

- 一个 MCP Server 可以绑定多个外部连接
- 连接代表"用 MCP Server 的能力，以哪个外部账号身份执行"
- 例：飞书 MCP Server 绑定某用户的飞书 access_token，Agent 以该用户身份发消息

---

## 十四、Service Category 规范

`service_category` 使用稳定的英文 code，前端 i18n 层负责翻译：

| Code | 含义 |
|------|------|
| `model_service` | 模型服务 |
| `file_processing` | 文件处理 |
| `communication` | 通信服务 |
| `data_service` | 数据服务 |
| `dev_tools` | 开发工具 |
| `business_service` | 业务服务 |

---

## 十五、常见问题与最佳实践

### Q: 为什么 MCP 能力叫 Capability 不叫 Tool？
A: Goku-AIOS 的"工具"专指内置 `BaseTool` 体系。MCP 端点叫 Capability，避免与 AI 工具管理体系命名冲突。

### Q: Agent 调用 MCP 失败，提示 NOT_AUTHORIZED？
A: 检查 `mcp_capability_authorizations` 表中是否存在该 Agent 对该 Capability 的授权行。授权模型是 Default-Deny，未明确授权即拒绝。

### Q: 如何让新 MCP 能力对 Agent 可见？
A: ① Server 同步成功（`status='active'`）② 为 Agent 添加授权行 ③ 重启或触发 registry 刷新

### Q: MCP call_log 里看不到完整参数？
A: 符合预期。call_log 只存脱敏后的 `input_summary`，含 secret/token 的字段被替换为 `[REDACTED]`，长值被截断。这是安全设计。

### Q: stdio 模式 MCP Server 如何传递 API Key？
A: 通过 `env_config` 字段（加密 JSON），运行时解密后注入子进程环境变量。不要放在 `start_command` 明文里。

### Q: 如何禁止某 Agent 使用所有 MCP 能力？
A: 在 Agent 的 `allowed_tools` 列表中加入 `@mcp:none`，executor 会进入严格模式，过滤掉所有 MCP wrapper。

---

## 十六、关键代码路径速查

| 场景 | 入口 |
|------|------|
| Server CRUD | `app/services/mcp_servers.py` |
| 运行时配置构建 | `app/services/mcp_runtime.py:build_runtime_config()` |
| 能力调用（授权+配额+日志） | `app/services/mcp_authorizations.py:invoke_principal_via_mcp()` |
| 工具包装注册 | `app/agent/mcp/tool_wrapper.py:MCPToolWrapper` |
| 调用日志脱敏 | `app/services/mcp_capabilities.py:_sanitize_args()` |
| 能力目录同步到知识库 | `app/services/mcp_knowledge.py:refresh_server_knowledge()` |
| 健康状态查询 | `app/services/mcp_observability.py:get_health_state()` |
| 外部连接管理 | `app/services/mcp_external_connections.py` |
| Agent 执行器 MCP 过滤 | `app/agent/executor.py:_is_mcp_wrapper()` |
