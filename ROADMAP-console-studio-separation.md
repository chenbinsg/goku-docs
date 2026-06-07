# Roadmap: Goku Console / Studio Separation

> 状态：Phase 5 complete · 创建：2026-06-06 · Owner：TBD  
> 目标：将现有 AIOS 单体重构为 Console shell + 五个 domain modules，后端 API 按 studio / core 分域，为未来 Studio 独立服务化留出清晰切割线。

---

## 目标架构

```
Goku Console (shell)          ← auth / nav / layout / routing / theme
│
├── modules/studio            ← AI application construction only
├── modules/runtime           ← tasks, chat, executions, stateful timeline
├── modules/policy            ← action policies, audit, RBAC
├── modules/approvals         ← approval center
└── modules/admin             ← tenants, users, system config, LLM health

Backend: Goku AIOS Core
    routers/studio/*          ← /api/studio/v1/  (build-time CRUD)
    routers/core/*            ← /api/core/v1/    (runtime engine)

Backend: Goku Router          ← already independent
```

**Studio scope rule:**
> Studio only owns AI application construction.  
> It does not own platform operations, runtime monitoring, policy governance, or tenant/user admin.

---

## Phase 1 — Page → Module Classification

**No code changes. Classification only.**

### Frontend: `frontend/src/pages/` → module

| Current path | Module | Rationale |
|---|---|---|
| `agents/` | `studio` | Agent builder — build-time |
| `workflows/` | `studio` | Workflow designer — build-time |
| `tools/` | `studio` | Tool registry — build-time |
| `mcp/` | `studio` | MCP connector manager — build-time |
| `knowledge/` | `studio` | Knowledge manager — build-time |
| `memory/` | `studio` | Memory profile manager — build-time |
| `skills/` | `studio` | Skill package manager — build-time |
| `plugins/` | `studio` | Plugin manager — build-time |
| `connectors/` | `studio` | Connector config — build-time |
| `docs/` | `studio` | Document center — build-time content |
| `chat/` | `runtime` | Conversation + SSE stream |
| `tasks/` | `runtime` | Task list / execution monitor |
| `tickets/` | `runtime` | Stateful ticket runtime |
| `analytics/` | `runtime` | Execution analytics / usage |
| `approvals/` | `approvals` | Approval center |
| `mobile/` | `approvals` | Mobile approval UI |
| `audit/` | `policy` | Audit log |
| `admin/` | `policy` | Stateful policy admin, transition audit |
| `roles/` | `admin` | RBAC roles |
| `users/` | `admin` | User management |
| `tenants/` | `admin` | Tenant management |
| `org/` | `admin` | Org / dept / team structure |
| `departments/` | `admin` | Department management |
| `system/` | `admin` | System config, agent soul, LLM health |
| `heartbeats/` | `admin` | Scheduled heartbeat monitor |
| `metrics/` | `admin` | Alert rules, metrics dashboard |
| `billing/` | `admin` | Billing dashboard |
| `cost/` | `admin` | Cost dashboard |
| `sso/` | `admin` | SSO admin |
| `models/` | `admin` | Model catalog (when not Router-delegated) |
| `email/` | `admin` | Email queue / watch |
| `Dashboard.tsx` | Console shell | Landing / overview |
| `Login.tsx` | Console shell | Auth |
| `SSOCallback.tsx` | Console shell | Auth |
| `EnterpriseSSOCallback.tsx` | Console shell | Auth |
| `profile/` | Console shell | User profile — cross-module |

### Backend: `backend/app/routers/` → domain

**Studio domain** (`/api/studio/v1/`):

| Router file | Endpoint domain |
|---|---|
| `agents.py` | Agent CRUD + export |
| `workflows.py` | Workflow CRUD |
| `tools.py` | Tool registry |
| `mcp_servers.py` | MCP server management |
| `mcp_external_connections.py` | MCP external connections |
| `knowledge.py` | Knowledge base CRUD |
| `memory.py` | Memory profiles |
| `auto_skills.py` | Skill management |
| `plugins.py` | Plugin registry |
| `connectors.py` | Connector config |
| `connector_config.py` | Connector config detail |
| `docs.py` | Document center |
| `instructions.py` | Agent instructions |
| `uploads.py` | File uploads (agent assets) |
| `ai_tools_mcp.py` | MCP tool bridge |
| `external_memory.py` | External memory sources |

**Core domain** (`/api/core/v1/`):

| Router file | Endpoint domain |
|---|---|
| `tasks.py` | Task CRUD + status |
| `conversations.py` | Conversation management |
| `events.py` | SSE event stream |
| `approvals.py` | Approval workflows |
| `audit.py` | Audit log |
| `stateful_policies.py` | Action policy admin |
| `stateful_runtime_debug.py` | Stateful debug API |
| `agent_policies.py` | Agent access policies |
| `proposals.py` | Improvement proposals (self-evolution) |
| `hooks.py` | Execution hooks |
| `observability.py` | Runtime observability |
| `ws.py` | WebSocket (runtime events) |

**Admin domain** (`/api/core/v1/` or future `/api/admin/v1/`):

| Router file | Endpoint domain |
|---|---|
| `users.py` | User management |
| `tenants.py` | Tenant management |
| `roles.py` | RBAC roles |
| `org.py` + `org_teams.py` | Org structure |
| `departments.py` | Departments |
| `system.py` | System config + LLM health |
| `auth.py` | Auth endpoints |
| `sso_admin.py` | SSO configuration |
| `models_router.py` | Model catalog |
| `analytics.py` | Usage analytics |
| `billing.py` | Billing |
| `costs.py` | Cost tracking |
| `heartbeats.py` | Scheduled heartbeats |
| `agent_health.py` + `agent_instances.py` | Agent health probes |
| `external_api.py` + `external_keys.py` | External API keys |
| `notifications.py` + `push.py` | Notifications |
| `dashboard.py` | Dashboard data |

**Integration/channel domain** (stays in Core, may extract later):

| Router file | Notes |
|---|---|
| `unicall.py` | Unified message channel |
| `mobile.py` | Mobile API |
| `email_queue.py` + `email_watch.py` + `outlook.py` | Email integration |
| `discord.py` + `telegram.py` + `whatsapp.py` + `line.py` | Messaging channels |
| `webhooks.py` | Inbound webhooks |
| `reactions_api.py` | Message reactions |

---

## Phase 2 — Console Shell Extraction

**Goal:** Isolate the shell from domain content. No functional change.

### Work items

1. **Create module directory structure**
```
frontend/src/
    shell/                    ← NEW: Console shell
        App.tsx               ← moved from src/App.tsx
        Layout.tsx            ← moved from src/components/Layout.tsx
        CollapsibleSidebar.tsx
        router.tsx            ← central route registry
        auth/                 ← login, SSO callbacks, auth store
        theme/
    modules/
        studio/
        runtime/
        policy/
        approvals/
        admin/
    shared/                   ← cross-module: types, hooks, UI primitives
        api/                  ← axios instances, request helpers
        components/           ← shared UI components (cards, etc.)
        hooks/
        stores/
```

2. **Define module registration contract**

Each module exports a manifest:
```typescript
// modules/studio/index.ts
export const studioModule = {
  routes: [...],         // React Router routes
  navItems: [...],       // sidebar entries + permission gates
  permissionKeys: [...], // permission keys this module needs
}
```

Console shell imports and mounts all module manifests. Modules never import from each other.

3. **Move Login, SSOCallback, Dashboard to shell**

4. **Move profile/ to shell** — cross-module concern

### Deliverable
- Module directory structure created
- Shell isolated: `Layout.tsx`, `CollapsibleSidebar.tsx`, `App.tsx` in `shell/`
- No page logic changed yet

---

## Phase 3 — Frontend Module Migration

**Goal:** Move all pages into their correct module directories.

### Work items

For each module, migrate pages in one batch commit:

1. `modules/studio/` ← agents, workflows, tools, mcp, knowledge, memory, skills, plugins, connectors, docs
2. `modules/runtime/` ← chat, tasks, tickets, analytics
3. `modules/approvals/` ← approvals, mobile
4. `modules/policy/` ← audit, admin (stateful policy pages)
5. `modules/admin/` ← users, tenants, roles, org, system, heartbeats, metrics, billing, cost, sso, email, models

Each module gets its own API client:
```typescript
// modules/studio/api.ts
import { createApiClient } from '@/shared/api'
export const studioApi = createApiClient('/api/studio/v1')

// modules/runtime/api.ts
export const coreApi = createApiClient('/api/core/v1')
```

### Rule enforced
- Pages inside `modules/studio/` may only import from `modules/studio/` or `shared/`
- No page imports across module boundaries
- Inter-module navigation via route strings only (`navigate('/tasks/123')`)

### Deliverable
- All pages in correct module directories
- Each module has its own typed API client
- No cross-module component imports

---

## Phase 4 — Backend API Namespace Split

**Goal:** Introduce `/api/studio/v1/` and `/api/core/v1/` prefixes.

### Work items

1. **Reorganize backend routers**
```
backend/app/routers/
    studio/
        __init__.py
        agents.py
        workflows.py
        tools.py
        knowledge.py
        memory.py
        skills.py
        mcp.py
        plugins.py
        connectors.py
        docs.py
        uploads.py
    core/
        __init__.py
        tasks.py
        conversations.py
        events.py
        approvals.py
        audit.py
        stateful_policies.py
        stateful_runtime_debug.py
        agent_policies.py
        proposals.py
        hooks.py
    admin/
        __init__.py
        users.py
        tenants.py
        roles.py
        org.py
        system.py
        auth.py
        analytics.py
        billing.py
    channels/
        __init__.py
        unicall.py
        mobile.py
        webhooks.py
        (messaging integrations)
```

2. **Update `main.py` router registration**
```python
app.include_router(studio_router,   prefix="/api/studio/v1")
app.include_router(core_router,     prefix="/api/core/v1")
app.include_router(admin_router,    prefix="/api/core/v1")   # same prefix for now
app.include_router(channels_router, prefix="/api/core/v1")
```

3. **Maintain legacy `/api/v1/` aliases** during transition
```python
# Backward-compat shim — remove after Console is fully migrated
app.include_router(studio_router, prefix="/api/v1")
app.include_router(core_router,   prefix="/api/v1")
```

4. **Update Console module API clients** to use new prefixes

5. **Remove legacy aliases** once Console migration is confirmed

### Deliverable
- Backend routers reorganized into studio / core / admin / channels
- `/api/studio/v1/` and `/api/core/v1/` live
- Legacy `/api/v1/` shim in place for safe migration
- Console modules updated to new prefixes

---

## Phase 5 — Boundary Enforcement

**Goal:** Harden the module boundaries so they hold under future development.

### Frontend rules (enforced via ESLint)

```
// .eslintrc: no cross-module imports
'no-restricted-imports': ['error', {
  patterns: [
    { group: ['*/modules/studio/*'], from: 'modules/runtime' },
    { group: ['*/modules/runtime/*'], from: 'modules/studio' },
    // etc.
  ]
}]
```

### Backend rules

| Rule | Enforcement |
|---|---|
| Studio routers import nothing from `core/` routers | `ruff` + import linter |
| Core runtime reads Studio DB models — never calls Studio HTTP | Code review + architecture test |
| Core never writes to Studio-owned tables (agents, workflows, tools) | DB write audit in CI |

### Architecture test (CI)

```python
# backend/tests/test_architecture.py
def test_studio_routers_do_not_import_core_runtime():
    # parse imports in routers/studio/ — assert no executor.py / stateful_runtime.py imports

def test_core_runtime_does_not_write_studio_tables():
    # assert executor.py has no INSERT/UPDATE on agents/workflows/tools tables
```

### Deliverable
- ESLint rules blocking cross-module imports
- Architecture tests in CI for backend boundaries
- Both pass in CI before Phase 5 is complete

---

## Phase 6 — Studio Extraction Readiness

**Goal:** Studio module is self-contained enough to deploy as a standalone service — without doing it yet.

### Work items

1. **Studio module API base URL is configurable**
```typescript
// Console can point Studio at a different backend
const studioApi = createApiClient(
  import.meta.env.VITE_STUDIO_API_URL ?? '/api/studio/v1'
)
```

2. **Studio backend routes have no runtime dependencies**
   - `routers/studio/` imports only from `models.py` (Studio-owned tables), `auth.py`, `db.py`
   - Zero imports from `executor.py`, `stateful_runtime.py`, `action_guard.py`

3. **Studio-owned DB tables identified**
   - `agents`, `workflows`, `tools`, `knowledge_entries`, `memory_profiles`, `skill_packs`, `mcp_servers`
   - Document which tables Core reads (read-only) vs. Studio owns (read-write)

4. **Extraction checklist written** — what would need to change to deploy Studio as its own service:
   - Move Studio tables to Studio DB
   - Core reads agent/tool/workflow definitions via Studio API instead of direct DB query
   - Console `VITE_STUDIO_API_URL` points to Studio service

### Deliverable
- Studio configurable API base URL
- Studio routers free of Core runtime imports
- Studio-owned tables documented
- Extraction checklist exists

---

## Milestones

| Milestone | Completion criteria |
|---|---|
| **M1 — Classification complete** | Every page and router file assigned to a module/domain, documented |
| **M2 — Console shell isolated** | Shell directory exists, module manifest contract defined, no regressions |
| **M3 — Frontend modules live** | All pages in correct modules, cross-module import lint rules passing |
| **M4 — Backend namespaced** | `/api/studio/v1/` and `/api/core/v1/` live, legacy shim removed |
| **M5 — Boundaries enforced** | ESLint + architecture tests green in CI |
| **M6 — Studio extraction-ready** | Configurable API URL, zero runtime imports in Studio routes, extraction checklist written |

---

## What does NOT change

- Database schema — no table moves, no migrations required for this refactor
- Auth / JWT — Console owns auth, no change to token structure
- Goku Router — already independent, untouched
- Stateful runtime — stays in Core, adapters (reimbursement, procurement, etc.) move to Studio domain over time
- Existing API behavior — legacy `/api/v1/` shim ensures zero breakage during migration

---

## Current state vs. target

| Dimension | Now | After |
|---|---|---|
| Frontend structure | `src/pages/` flat list, 30+ directories | `src/modules/{studio,runtime,policy,approvals,admin}/` |
| Backend structure | `routers/` flat list, 60+ files | `routers/{studio,core,admin,channels}/` |
| API prefix | `/api/v1/*` (everything mixed) | `/api/studio/v1/*` and `/api/core/v1/*` |
| Cross-module coupling | Implicit (any page imports any component) | Enforced by ESLint + architecture tests |
| Studio extractability | Not possible without major surgery | Possible — one config change + data source swap |
