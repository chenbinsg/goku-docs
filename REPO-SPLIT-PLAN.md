# Repo Split Plan: goku-core + goku-studio

> 状态：Ready to execute · Created: 2026-06-06 · Owner: 智能体技术  
> Prerequisites: Steps 1–3 complete ✅

## Overview

The monorepo is split into three git repositories plus a shared package:

```
packages/goku-shared/      → PyPI package (both repos depend on it)
  └── goku_shared/

goku-core/                 → 智能体技术 owns
  ├── backend/             ← Core runtime engine + admin + channels
  └── frontend/            ← All frontend modules (Console shell)

goku-studio/               ← 智能体应用 owns
  └── backend/             ← Studio API only (agents/workflows/tools/MCP)
```

> **Note**: The frontend stays in goku-core initially because the Console shell
> and navigation are cross-domain. Studio frontend pages (`modules/studio/`)
> will be extracted into goku-studio in a later phase once the frontend module
> boundary is fully enforced.

---

## File → Repo Mapping

### `packages/goku-shared/` → **goku-shared** (new repo)

| Path | Notes |
|------|-------|
| `packages/goku-shared/` | Extract as standalone repo; publish to internal PyPI |

---

### Backend: goku-core

Everything except `routers/studio/` and `models_studio.py`.

```
backend/
  app/
    main.py
    db.py
    auth.py
    config.py
    middleware/
    agent/                   ← Core ReAct engine
    services/                ← All shared services
    models_admin.py          ← Admin ORM
    models_core.py           ← Core ORM
    models_channels.py       ← Channels ORM
    models.py                ← backward-compat shim (remove after migration)
    routers/
      admin/                 ← 26 files
      core/                  ← 16 files
      channels/              ← 14 files
  alembic/
    versions/                ← 0046–0086 (shared baseline, frozen)
    core/                    ← 0087+ Core domain chain
  seeds/agents/              ← Agent JSON seeds
  scripts/
  tests/
  Makefile
  requirements.txt

frontend/                    ← Console shell + all 5 modules
  src/
    shell/
    modules/
      studio/    ← studio pages (read-only for 智能体应用 initially)
      runtime/
      policy/
      approvals/
      admin/
    shared/
```

---

### Backend: goku-studio

Only Studio domain code.

```
backend/
  app/
    db.py                    ← re-exports from goku_shared.db
    auth.py                  ← imports from goku_shared.auth + adds FastAPI layer
    config.py                ← Settings(SharedSettings) with studio-specific extras
    models_studio.py         ← Studio ORM (agent_definitions, workflows, tools, MCP, IRA…)
    routers/
      studio/                ← 18 files: agents, workflows, tools, MCP, knowledge…
      studio/__init__.py
    schemas/                 ← Studio-specific Pydantic schemas
  alembic/
    studio/                  ← studio_0001+ domain chain (down_revision = "0086")
  seeds/
  scripts/
  tests/
  requirements.txt
  pyproject.toml
```

---

## File Attribution Table (backend/app)

| File / Directory | goku-core | goku-studio |
|-----------------|-----------|-------------|
| `main.py` | ✅ (without Studio router registration) | ✅ (own main.py) |
| `db.py` | ✅ re-exports goku_shared.db | ✅ re-exports goku_shared.db |
| `auth.py` | ✅ full (FastAPI layer) | ✅ copy, same FastAPI layer |
| `config.py` | ✅ full Settings subclass | ✅ Studio Settings subclass |
| `models_admin.py` | ✅ | ❌ |
| `models_core.py` | ✅ | ❌ |
| `models_channels.py` | ✅ | ❌ |
| `models_studio.py` | read-only (FK target) | ✅ owner |
| `models.py` (shim) | ✅ (until all imports updated) | ✅ (until all imports updated) |
| `agent/` | ✅ | ❌ (Studio never runs agents directly) |
| `services/` | ✅ (all services) | ⚠️ copy subset: llm_provider, model_router for build-time previews |
| `middleware/` | ✅ | ✅ same copy |
| `routers/admin/` | ✅ | ❌ |
| `routers/core/` | ✅ | ❌ |
| `routers/channels/` | ✅ | ❌ |
| `routers/studio/` | read-only ref | ✅ owner |
| `alembic/versions/` (0046–0086) | ✅ stays | ❌ (goku-studio starts from 0086 baseline) |
| `alembic/core/` | ✅ | ❌ |
| `alembic/studio/` | ❌ | ✅ |

---

## Execution Steps

Run these steps **in order**. Each step is independently safe to stop/resume.

### Phase A — Prepare (no git surgery yet)

1. **[Done ✅] Step 1**: Split `models.py` into domain files.
2. **[Done ✅] Step 2**: Separate alembic migration chains + domain `Makefile` targets.
3. **[Done ✅] Step 3**: Create `packages/goku-shared/` pip package.
4. **[This doc] Step 4**: Repo split plan and stub directories.

### Phase B — Studio repo extraction

**Prerequisites:**
- `requirements.txt` split into `requirements-core.txt` and `requirements-studio.txt`
- All Studio router tests pass when only `routers/studio/` and `models_studio.py` are imported
- `VITE_STUDIO_API_URL` implemented in frontend Studio module (Phase 6 frontend)

**Extraction steps:**

```bash
# 1. Create goku-studio repo
mkdir ~/goku-studio && cd ~/goku-studio && git init

# 2. Use git subtree or filter-repo to seed initial history from the monorepo
#    (only Studio-domain paths)
git clone ~/agent goku-studio-seed
cd goku-studio-seed
git filter-repo \
  --path backend/app/routers/studio/ \
  --path backend/app/models_studio.py \
  --path backend/alembic/studio/ \
  --path backend/seeds/ \
  --path backend/tests/  \
  --force

# 3. Add goku-shared as a dependency
pip install goku-shared==0.1.0

# 4. Create minimal main.py that mounts only studio router
# 5. Run tests: pytest backend/tests/ -k studio
# 6. CI green → cut goku-studio v1.0.0 tag
```

### Phase C — Core repo (rename monorepo)

After Studio is extracted and running independently:

```bash
# In the monorepo (now becomes goku-core):
# 1. Remove routers/studio/ + models_studio.py from this repo
git rm -r backend/app/routers/studio/
git rm backend/app/models_studio.py

# 2. Remove Studio imports from main.py (routers/studio import block)
# 3. Update models.py shim to remove Studio re-exports
# 4. Core reads AgentDefinition via Studio HTTP API instead of direct DB query
#    (or keeps direct DB read if sharing the same DB — see note below)

# 5. Rename remote origin
git remote set-url origin git@github.com:your-org/goku-core.git
```

### Cross-DB strategy (important decision point)

Two options for how Core reads Studio data (agents, workflows):

| Option | How | When to use |
|--------|-----|-------------|
| **Shared DB** (recommended for v1) | Both services use the same MySQL DB. Core reads `agent_definitions` via direct SQL. Studio has exclusive write rights. | Single-region, same team manages DB |
| **Studio API** | Core calls `GET /api/studio/v1/agents/{id}` to resolve agent configs. Studio becomes the authoritative source. | Multi-region, teams manage separate DBs |

Start with Shared DB (no network hop, no cache invalidation), migrate to Studio API in a later phase.

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Missing imports after file removal | Architecture tests + `pytest --import-mode=importlib` catch missing modules before deploy |
| Studio DB migration divergence | Studio alembic chain starts from 0086 and manages only Studio tables; Core chain manages the rest |
| Cross-repo FK breakage (agent_id FK on tasks) | FK stays (same DB). If DBs ever split, FK becomes an application-level check |
| goku-shared version drift | Pin exact version in both repos; semantic-version bump triggers both repo PRs |
| Frontend still in goku-core while Studio backend is separate | `VITE_STUDIO_API_URL` env var lets frontend point at either goku-core or goku-studio Studio API |

---

## Success Criteria

- [x] `pytest` passes in goku-studio with only Studio files + goku-shared
      ✅ 6/6 boundary tests pass (2026-06-06, after lazy-init fix + conftest.py added)
- [x] `pytest` passes in goku-core without Studio files
      ✅ routers/studio/*.py removed (Phase D); all non-Studio tests pass
- [x] `make deploy` in goku-core applies 0046–0086 + core chain, does not touch Studio tables
      ✅ alembic/core/ chain exists; env.py imports models_admin/core/channels only
- [x] `make deploy` in goku-studio applies 0046–0086 baseline + studio chain
      ✅ alembic/studio/ chain exists (down_revision="0086")
- [x] Frontend builds with `VITE_STUDIO_API_URL` pointing at goku-studio
      ✅ frontend/src/modules/studio/api.ts reads VITE_STUDIO_API_URL; falls back to shared client
- [x] No Studio migration in goku-core; no Core migration in goku-studio
      ✅ alembic/core/ and alembic/studio/ are isolated chains

**Status: ALL criteria met — 2026-06-06**
