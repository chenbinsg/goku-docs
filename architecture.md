# Goku Platform — Architecture Overview

> Last updated: 2026-06-07

## What Is Goku?

Goku is a multi-tenant enterprise AI Agent platform composed of four independent services.
Each service has its own repository, runs on its own port, and can be deployed independently.

---

## The Four Repos

| Repo | Default Port (backend / frontend) | Role |
|------|-----------------------------------|------|
| **goku-core** | `:8106` / `:5106` | Runtime — chat, tasks, approvals, audit, channels, external API |
| **goku-studio** | `:8107` / `:5107` | Studio — agent/workflow/tool/knowledge CRUD builder |
| **goku-router** | `:8108` | Model gateway — routes LLM requests, manages model catalog |
| **goku-sdk** | (library, no server) | Python `aios-sdk` + TypeScript `@goku-ai/sdk` client libraries |

---

## Request Flow

```
Browser
  │
  ├── :5106  goku-core frontend (React + Vite)
  │     │  chat, audit, analytics, admin pages
  │     │
  │     └── navigates to Studio → StudioRedirect appends JWT → :5107
  │
  ├── :5107  goku-studio frontend (React + Vite)
  │     │  agents, workflows, tools, knowledge, memory, docs pages
  │     │
  │     └── "Return to Runtime" appends JWT → :5106
  │
  ├── :8106  goku-core backend (FastAPI)
  │     │
  │     ├── POST /conversations/{id}/messages  → creates task_id
  │     ├── GET  /tasks/{task_id}/events       → SSE stream
  │     │         │
  │     │   AgentExecutor (ReAct loop, max 20 steps)
  │     │         │
  │     │   ToolRegistry.execute(tool_name, params)
  │     │         │
  │     │   EventBus.publish(event) → SSE to client
  │     │
  │     ├── GET  /api/v1/models  → proxies to goku-router when GOKU_ROUTER_URL set
  │     └── POST /api/external/v1/...  → SDK entry point
  │
  ├── :8107  goku-studio backend (FastAPI)
  │     └── agent CRUD, workflow engine, tool registry, knowledge base
  │
  └── :8108  goku-router
        └── LLM routing, model catalog, load balancing
```

---

## Data Model

```
tenants
  └── departments
        └── teams
              └── users
tenants
  └── agents          ← defined in goku-studio, executed in goku-core
        └── agent_access_policies
        └── conversations  (goku-core)
              └── tasks
                    └── task_steps
```

All tables are scoped to `tenant_id`. JWT middleware injects tenant context on every request.

---

## Auth Flow

1. User logs in at **goku-core** (`POST /api/v1/auth/login`)
2. Receives `access_token` (JWT) + `refresh_token`
3. Tokens stored in Zustand auth store (`stores/auth.ts`) in both frontends
4. When navigating cross-service, tokens are passed via URL query params (see [auth-bridge.md](auth-bridge.md))

---

## Cross-Service Navigation

```
goku-core  ──[?_token=JWT]──►  goku-studio   (user goes to build/edit agents)
goku-studio ──[?_token=JWT]──►  goku-core    (user returns to chat)
```

Full protocol: see [auth-bridge.md](auth-bridge.md)

---

## Model Routing (Phase 3)

When `GOKU_ROUTER_URL` is set in goku-core's `.env`:
- `GET /api/v1/models` proxies to Goku-Router instead of the local `models` DB table
- Frontend hides CRUD buttons (read-only catalog mode)
- DB `models` table remains as fallback when Router is unreachable

When `GOKU_ROUTER_URL` is not set: legacy DB-only mode, all model management is local.

---

## Environment Variables (per service)

### goku-core (`backend/.env`)
```
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/aios
SECRET_KEY=<32-byte hex>
OPENAI_API_KEY=...
OPENAI_BASE_URL=...           # optional: Kimi / DeepSeek / Ollama
GOKU_ROUTER_URL=http://localhost:8108   # optional: enable router delegation
VITE_STUDIO_URL=http://localhost:5107   # where goku-studio frontend runs
REDIS_URL=...                 # optional: required for multi-worker SSE
QDRANT_URL=...                # optional: vector memory
```

### goku-studio (`backend/.env`)
```
DATABASE_URL=...              # can share the same DB as goku-core
SECRET_KEY=<same key>         # must match goku-core (shared JWT verification)
VITE_STUDIO_BACKEND_PORT=8107
VITE_STUDIO_PORT=5107
VITE_RUNTIME_URL=http://localhost:5106
```

---

## Running Everything Locally

```bash
# Terminal 1 — goku-core
cd ~/goku/core && ./start.sh        # backend :8106, frontend :5106

# Terminal 2 — goku-studio
cd ~/goku/studio && ./start.sh      # backend :8107, frontend :5107

# Terminal 3 — goku-router (optional)
cd ~/goku/router && ./start.sh      # :8108

# SDK — no server needed
pip install aios-sdk
npm install @goku-ai/sdk
```

Or with docker-compose (see `~/goku/infra/docker-compose.yml` when available).

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| goku-core and goku-studio are separate backends | Studio CRUD is development-time; Runtime is production-critical. Separate deployments allow independent scaling and failure isolation. |
| Shared `SECRET_KEY` | Both services verify the same JWT — no inter-service token exchange needed. |
| URL token bridge (not OAuth redirect) | Simpler than a full OAuth dance for a same-organization tool. Tokens are stripped from history immediately after hydration. |
| goku-router as separate service | Model catalog and routing logic changes frequently (new providers, load balancing). Decoupling lets the router be upgraded without touching the core execution path. |
| SDK as separate repo | External developers should not need to clone either backend to use the API. Clean versioning and publish cadence independent of platform releases. |
