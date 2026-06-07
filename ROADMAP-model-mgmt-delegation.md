# Roadmap：将「模型管理」职责下沉到 Goku-Router

> 状态：Draft · 创建：2026-05-28 · Owner：TBD
> 目标分支：`codex/router-delegation`（建议从 `codex/smartsms` 切出）

---

## 1. 背景与问题

按设计分工：

- **Goku-AIOS** = Agent 业务面（智能体、工具、工作流、对话、记忆、审批）
- **Goku-Router** = LLM 控制面（模型清单、提供商路由、健康检查、failover、计费）

但当前实现里 AIOS 自己维护了一张 `models` 表 + 一个「模型管理」UI，把 Router 该管的事情复制了一份。

**事故先例（2026-05-26 晚）**：AIOS 的模型表里 `qwen-max` 标"正常"，但底层 Router（`OPENAI_BASE_URL=http://localhost:8159/v1`）只配了 `qwen3.6` 这一个上游。将默认模型切到 `qwen-max` → Router 返回 `400 Bad Request`，普通聊天全挂。**这就是双源数据漂移的直接代价。**

---

## 2. 重叠盘点（Inventory）

### 2.1 后端代码

| 文件 | 重叠职责 | 处理方式 |
|------|---------|---------|
| `backend/app/models.py:Model` (ORM) | 模型清单/状态/价格/tier/priority | **整表删除**（Phase 3） |
| `backend/app/routers/models_router.py` | CRUD：`POST/PATCH/DELETE /models/{id}` | **删除写接口**（Phase 2）|
| `backend/app/routers/models_router.py:list_models` | `GET /models` | **改为转发** Router 的 `/models`（Phase 1） |
| `backend/app/routers/models_router.py:health_check` | `GET /models/health` | **删除**，Router 自己暴露 |
| `backend/app/routers/models_router.py:route_model` | `POST /models/route` | **删除**，AIOS 不该决定路由策略 |
| `backend/app/routers/models_router.py:list_ollama_models` | `GET /models/ollama` | **删除** |
| `backend/app/services/model_capabilities.py` | glob 匹配 capabilities | **保留**，但数据源改为 Router |
| `backend/app/services/model_router.py` | 内部 `set_runtime_default` / `apply_runtime_default` | **保留**（管 default name），删 priority/failover 逻辑 |
| `backend/app/routers/dashboard.py` | 统计 active model 数 | 改为查 Router |

### 2.2 数据库表

| 表 | 是否保留 |
|----|---------|
| `models` | ❌ 删除（Phase 3 migration） |
| `system_config[LLM_MODEL]` | ✅ 保留（全局默认模型名） |
| `system_config[LLM_PROVIDER]` | ⚠️ 可保留作覆盖；正常情况下由 Router 决定 |
| `agents.model_override` | ✅ 保留（per-agent 偏好的模型名） |
| `tasks.model_name` / `tasks.token_usage` | ✅ 保留（调用日志，AIOS 自己的统计） |

### 2.3 前端

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/models/ModelList.tsx` | Phase 1：转为只读视图；Phase 2：合并到 `Settings` 下作为状态面板 |
| `frontend/src/pages/models/ModelRoute.tsx` | 删除 |
| `frontend/src/hooks/useModelCapabilities.ts` | 保留，HTTP 源切换为 `/api/v1/router/models/{name}/capabilities` |
| `frontend/src/components/Layout.tsx` | 删除「AI 能力 → 模型管理」菜单项 |

---

## 3. 目标态架构

```
┌──────────────────────────────────────────────┐
│ Goku-Router (LLM 控制面，单一事实源)         │
│ 暴露 API:                                    │
│  - GET  /v1/models                           │ ← 实时模型清单 + 状态
│  - GET  /v1/models/{name}/capabilities       │ ← supports_tools 等
│  - POST /v1/chat/completions                 │ ← 真实推理
│  - GET  /v1/usage?model=xx&from=...          │ ← 计费数据（可选）
└──────────────────┬───────────────────────────┘
                   │
                   │  GokuRouterClient (新)
                   │  - 启动时拉一次 /models 缓存
                   │  - 每 60s 后台刷新
                   │  - 提供 list_models() / get_capabilities(name)
                   │
┌──────────────────▼───────────────────────────┐
│ Goku-AIOS (Agent 业务面)                     │
│ 只持有：                                     │
│  - SystemConfig.LLM_MODEL  (str, 默认模型名) │
│  - Agent.model_override    (str, per-agent)  │
│  - TenantModelAccess       (白名单，可选)    │
│  - tasks.model_name        (调用日志)        │
└──────────────────────────────────────────────┘
```

---

## 4. 分阶段路线图

### Phase 0 — 接口契约对齐（前置，0.5d）

**前提**：Goku-Router 必须先支持以下端点。如果还没有，先去 Router 仓库补齐。

- `GET /v1/models` → 返回 `[{name, provider, capabilities[], status, tier?, cost_per_1k?}]`
- `GET /v1/models/{name}/capabilities` → 单模型详情
- 文档 / OpenAPI schema 同步

**Deliverable**：Router 侧 PR + 一个 curl 验证脚本。

---

### Phase 1 — 影子模式：AIOS 改为只读代理（1–2d，零风险） ✅ 已实施 2026-05-28

**目标**：AIOS UI 看到的模型清单完全来自 Router，但 DB 表保留作为 fallback。

**改动**：

1. 新增 `backend/app/services/goku_router_client.py`
   ```python
   class GokuRouterClient:
       def __init__(self): ...
       def list_models(self) -> list[dict]: ...      # 带 60s 缓存
       def get_capabilities(self, name: str) -> dict: ...
       def health(self) -> dict: ...
   ```
   - 配置：新增 env `GOKU_ROUTER_URL`（默认空 → 退回旧逻辑）
   - 失败时 fallback 读 DB 的 `models` 表

2. 改造 `routers/models_router.py`：
   - `list_models()` 优先调用 `GokuRouterClient.list_models()`，DB 仅作 fallback
   - `health_check()` 同上
   - 写接口 `POST/PATCH/DELETE` 保持现状但加 deprecation log
   - `route_model` 保持

3. 前端 `ModelList.tsx`：
   - 当后端返回的数据带 `source: "router"` 时，隐藏「新增模型 / 编辑 / 删除」按钮，只保留「设为默认」
   - 加一条 banner：「模型清单由 Goku-Router 实时提供」

**风险**：低。Router 不可用时自动 fallback。

**验证**：
- [ ] Router 启停切换，UI 显示对应数据源
- [ ] 默认模型设置仍正常工作
- [ ] 现有 agents 调用不受影响

---

### Phase 2 — 删除 AIOS 侧写入路径（1d，中风险） ✅ 已实施 2026-05-28

> **实施备注**：Phase 1 与 Phase 2 同批实施。`GokuRouterClient` 已实现（`backend/app/services/goku_router_client.py`），`list_models` 优先走 Router、DB 兜底，前端当 `source:"router"` 时隐藏 CRUD 按钮。写接口（POST/PATCH/DELETE /models、/route、/ollama）已删除。DB 表保留作为 fallback，回退点 git tag = `pre-router-delegation`。

**前提**：Phase 1 在生产环境稳定运行 ≥1 周。

**改动**：

1. 后端：
   - 删除 `POST /api/v1/models`
   - 删除 `PATCH /api/v1/models/{id}`
   - 删除 `DELETE /api/v1/models/{id}`
   - 删除 `POST /api/v1/models/route`
   - 删除 `GET /api/v1/models/ollama`
   - `set_default_model` 保留，但不再校验 DB 是否存在该模型；改为调用 Router 验证
   - `model_capabilities.py:get_capabilities()` 优先走 Router，glob 兜底

2. 前端：
   - 「模型管理」页改名为「模型状态」，纯状态展示
   - 默认模型选择改为下拉框（数据源：Router）
   - 删除 `ModelRoute.tsx`、菜单项

3. 文档：
   - 更新 CLAUDE.md「Key Patterns - Model capability checks」段落
   - 在 README 注明 `GOKU_ROUTER_URL` 必填

**回退**：保留 ORM `Model` 表 + 旧路由代码于一个 git tag（`pre-router-delegation`），紧急时可回滚 commit。

---

### Phase 3 — 删表（0.5d，低风险） ✅ 已实施 2026-05-28

**改动**：

1. Alembic 新迁移 `0067_drop_models_table.py`（`upgrade`: `op.drop_table("models")`，`downgrade` 重建空表）
2. 删除 `models.py:Model` ORM 类
3. `dashboard.py` 把 active-model 计数改为调用 `goku_router_client.list_models()`
4. `models_router.py` 彻底移除 DB fallback 路径；Router 不可用时返回 `{"models": [], "source": "unavailable"}`
5. `tests/test_models_router.py` 全面重写，覆盖 Phase 3 行为（empty-when-unreachable 等 29 个用例全绿）

**回滚**：`alembic downgrade -1` 重建空表。

---

### Phase 4（可选）— 租户模型权限独立化（2–3d） ⛔ 已决定不实施

**决定**：截至 2026-05-28，无此需求，跳过。如未来客户有"不同租户能用不同模型"需求，再参考以下原始设计重启。

**原触发条件**：客户提出"不同租户能用不同模型"的需求时再做，否则跳过。

**新增**：
- 新表 `tenant_model_access(tenant_id, model_name, can_use, daily_quota_tokens)`
- 新 router：`GET/POST /api/v1/tenants/{id}/model-access`
- Executor 调用前先校验：`tenant_id` 是否允许 `model_name`

这一层是 AIOS 该管的（业务策略），与 Router 无关。

---

## 5. 兼容矩阵

| 场景 | Phase 0 | Phase 1 | Phase 2 | Phase 3 |
|------|---------|---------|---------|---------|
| Router 在线 | ✅ | ✅ Router 数据 | ✅ Router 数据 | ✅ Router 数据 |
| Router 离线 | ✅ | ✅ DB fallback | ⚠️ 仅本地默认模型可用 | ❌ 必须 Router 在线 |
| 升级路径 | 无操作 | 无 schema 变更 | 无 schema 变更 | 一次性 drop_table |
| 回滚 | / | 切回 PR 前版本 | revert commit | alembic downgrade |

---

## 6. 成功指标

| 指标 | 起点 | Phase 1+2 实测 | 目标（Phase 3 后） |
|------|------|-------------|-------------------|
| 模型清单事实源 | 2 处（AIOS DB + Router） | 1 主源（Router）+ 兜底 DB | 1 处（Router） |
| 漂移导致的故障 | 至少 1 起（qwen-max 事件） | 0 | 0 |
| `models` 表字段数 | 9 个 | 9 个（暂留） | 0（表删除） |
| `routers/models_router.py` 行数 | ~313 行 | ~210 行 | < 60 行 |
| `models_router.py` 端点数 | 10 个 | **5 个**（read-only + set-default + capabilities + health） | 5 个 |
| 前端「模型管理」CRUD 按钮 | 4 个（新增/编辑/删除/设默认） | **1 个**（设默认） | 1 个（设默认） |
| 「智能路由」二级菜单 | 1 项 | **已删除** | — |

---

## 7. 关键风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Router 没有 `/models` 端点 | Phase 1 卡住 | Phase 0 先在 Router 仓库实现，AIOS 这边 PR 后置 |
| Router 长时间宕机 | AIOS 完全无法调用 LLM | Phase 1/2 保留 DB fallback；Phase 3 后必须保证 Router HA |
| 第三方 skill pack 直接查 `models` 表 | 升级后崩溃 | Phase 2 起在 CHANGELOG 高亮，提供 helper 函数；Phase 3 前扫描所有 skill_packs |
| `model_capabilities.py` glob 失效 | Agent 选错能力分支 | 保留 glob 兜底，Router 优先 |
| `tasks.model_name` 中存有已删除的旧模型名 | 历史日志展示异常 | 前端做 graceful fallback：未知模型名直接显示字符串 |

---

## 8. 工作量预估

| Phase | 后端 | 前端 | 测试 | 文档 | 合计 |
|-------|------|------|------|------|------|
| 0 | 0.5d（Router 侧）| - | - | 0.5d | **1d** |
| 1 | 1d | 0.5d | 0.5d | 0.5d | **2.5d** |
| 2 | 1d | 0.5d | 0.5d | 0.5d | **2.5d** |
| 3 | 0.5d | - | 0.5d | - | **1d** |
| 4（可选）| 2d | 1d | 1d | 0.5d | **4.5d** |
| **总计（不含 4）** | | | | | **~7d** |

---

## 9. 开放问题

1. **Router 是否计划开放计费 API？** 如否，AIOS 侧需保留 `tasks.token_usage` 自行累加成本估算
2. **多 Router 实例的负载均衡** 谁来做？AIOS 端配多个 `GOKU_ROUTER_URL`，还是 Router 前面挂 nginx？
3. **能力枚举的统一** 当前 `supports_thinking/supports_vision/uses_max_completion_tokens` 是 AIOS 自定义的 schema，Router 是否会有自己的 schema？需要在 Phase 0 对齐
4. **本地开发模式** 没有 Router 时如何启动 AIOS？Phase 3 后是否需要内嵌一个 "single-model" stub Router 用于本地 dev

---

## 10. 下一步动作

1. 把这份 Roadmap 发给 Goku-Router 负责人，确认 Phase 0 接口契约
2. 决定是否需要 Phase 4（取决于多租户路线图）
3. 在 `codex/router-delegation` 分支开 Phase 1 PR

---

> 维护说明：每个 Phase 完成后，在本文档表格里勾选完成项，并在 CHANGELOG 引用本文件。
