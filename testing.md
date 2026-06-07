# Testing Guide — Goku-AIOS

> Last updated: 2026-06-01 (v1.9.19)

---

## Overview

| Layer | Framework | Count | Coverage |
|-------|-----------|------:|---------|
| Backend integration tests | pytest + FastAPI TestClient + MySQL | ~380 | ~80 % |
| Backend unit tests | pytest | ~90 | varies by module |
| UniCall adapter unit tests | pytest (sync, no DB) | 42 | adapters 100 % |
| Frontend type-check | TypeScript `tsc --noEmit` | — | compile-time |

---

## Running Tests

### All backend tests

```bash
# From repo root
pytest -q --tb=short
```

### Specific file

```bash
pytest backend/tests/test_proposals_api.py -q
```

### With coverage report

```bash
pytest --cov=backend/app \
       --cov-report=term-missing:skip-covered \
       --cov-report=html:reports/coverage_html \
       --cov-fail-under=80
# Open reports/coverage_html/index.html
```

### Frontend type-check

```bash
cd frontend && npx tsc --noEmit
```

---

## Test Database Setup

Tests run against a real **MySQL** database (`aios_test`).  
Each test function runs in a SAVEPOINT that is rolled back — no teardown overhead, full isolation.

**Default connection** (override with `TEST_DATABASE_URL`):
```
mysql+pymysql://root:123456@127.0.0.1:3306/aios_test
```

**First-time setup:**
```bash
# Create the database
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS aios_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Apply all migrations
DATABASE_URL="mysql+pymysql://root:123456@127.0.0.1:3306/aios_test" alembic upgrade head
```

The test fixtures are defined in `backend/conftest.py` — `engine` (session-scoped), `db` (function-scoped SAVEPOINT), `client` (FastAPI TestClient bound to the isolated session).

---

## Coverage Gates (CI)

Enforced in `.github/workflows/ci.yml`:

| Scope | Threshold |
|-------|----------:|
| **Global** | ≥ 80 % |
| `auth.py` | ≥ 90 % |
| `routers/agents.py` | ≥ 80 % |
| `agent/executor.py` | ≥ 70 % |
| `services/workflow_engine.py` | ≥ 80 % |
| `services/memory.py` | ≥ 85 % |

PRs automatically receive a coverage diff comment from `py-cov-action`.

---

## Key Test Files

| File | What it covers |
|------|----------------|
| `test_auth_security.py` | JWT, RBAC, rate limits, token rotation |
| `test_approval_service.py` | Approval creation, escalation, expiry, full action cycle |
| `test_agent_policies.py` | DefaultDeny, DefaultAllow, per-principal grants |
| `test_conversations_api.py` | Conversation CRUD, message send, model switch |
| `test_executor_unit.py` | Executor helper functions (pure unit, no DB) |
| `test_workflow_engine.py` | Node execution, branching, error handling |
| `test_memory_service.py` | BM25 + vector hybrid search, RRF fusion |
| `test_unicall_adapters.py` | All 7 channel adapters, Gateway rate limiting, notification dedup |
| `test_proposals_api.py` | ImprovementProposal CRUD, apply, reject, stats |
| `test_mobile_api.py` | Mobile summary, per-user preferences, signed deep-links |
| `test_model_capabilities.py` | Model capability registry glob-matching |
| `test_analytics_api.py` | DAU/WAU/MAU, cohort, agent usage endpoints |

---

## Coverage Snapshot (v1.9.19)

| Module | Coverage | Notes |
|--------|---------|-------|
| `auth.py` | ~92 % | Password, JWT, audit log, MFA |
| `routers/agents.py` | ~85 % | Access filter, CRUD, export |
| `routers/approvals.py` | ~82 % | Full approval lifecycle |
| `routers/conversations.py` | ~78 % | Core paths; SSE stream excluded |
| `agent/executor.py` | ~71 % | Core ReAct loop; LLM stubs mock network |
| `services/workflow_engine.py` | ~83 % | Node types, error paths |
| `services/memory.py` | ~90 % | BM25 + Qdrant hybrid |
| `services/approval.py` | ~88 % | All risk levels, escalation |
| `routers/proposals.py` | ~88 % | New in v1.9.19 |
| `routers/mobile.py` | ~86 % | New in v1.9.19 |
| `services/unicall/` | ~80 % | Adapter unit tests |
| `services/llm_provider.py` | ~55 % | Network paths hard to unit-test |
| `routers/mcp_servers.py` | ~48 % | MCP runtime needs integration env |

---

## Adding a New Test

1. Create `backend/tests/test_<feature>.py`
2. Use the `client` and `db` fixtures from `conftest.py`
3. Use `_make_user()` / `_headers()` helpers (copy from any existing test file)
4. All DB writes are rolled back automatically — no cleanup needed
5. Run locally with `pytest backend/tests/test_<feature>.py -q` before pushing

**Pattern:**
```python
import uuid
from app import auth, models

def _make_user(db):
    u = models.User(id=str(uuid.uuid4()), username=f"u_{uuid.uuid4().hex[:6]}",
                    email=f"u_{uuid.uuid4().hex[:6]}@test.com",
                    hashed_password=auth.hash_password("Pass@1234"),
                    is_active=True, is_superuser=False)
    db.add(u); db.flush(); return u

def _headers(user):
    tok = auth.create_access_token({"sub": user.id, "user_id": user.id})
    return {"Authorization": f"Bearer {tok}"}

class TestMyFeature:
    def test_happy_path(self, client, db):
        user = _make_user(db)
        resp = client.get("/api/v1/my-endpoint", headers=_headers(user))
        assert resp.status_code == 200
```
