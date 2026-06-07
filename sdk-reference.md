# Goku-AIOS SDK Reference

> **Version**: 1.9.27 | **Python**: ≥ 3.9 | **[中文文档](SDK_Guidelines.md)**

---

## Installation

```bash
pip install aios-sdk
# With SSE streaming support
pip install "aios-sdk[streaming]"
```

---

## Quick Start

```python
from aios_sdk import AgentSession

session = AgentSession(
    base_url="https://your-aios.example.com",
    api_key="goku_your_api_key_here",
    agent="analyst",          # default agent slug
)

# One-shot: submit and wait for completion
result = session.run("Summarise the Q1 revenue report")
if result.ok:
    print(result.result)
else:
    print(f"Failed: {result.error}")
```

---

## AgentSession

```python
AgentSession(
    base_url: str,           # AIOS instance URL, e.g. "https://aios.example.com"
    api_key: str,            # API key from /system/api-keys (prefix: goku_)
    agent: str | None = None,  # Default agent slug; can be overridden per call
    timeout: int = 300,      # Default request timeout (seconds)
    verify_ssl: bool = True,
)
```

### Environment variable fallbacks

| Variable | Parameter |
|----------|-----------|
| `AIOS_BASE_URL` | `base_url` |
| `AIOS_API_KEY` | `api_key` |
| `AIOS_AGENT` | `agent` |

---

## Methods

### `run(prompt, *, agent=None, timeout=None, context=None) → TaskResult`

Submit a task and **block** until completion. Simplest usage.

```python
result = session.run(
    "Write a market analysis for the EV sector",
    agent="researcher",     # override default agent
    timeout=120,
    context={"locale": "ja"},
)
print(result.result)
```

---

### `submit(prompt, *, agent=None, context=None) → str`

Submit a task **without waiting**. Returns `task_id`.

```python
task_id = session.submit("Generate weekly report")
# ... do other work ...
result = session.wait(task_id)
```

---

### `wait(task_id, *, timeout=None, poll_interval=2) → TaskResult`

Poll until a task finishes. Raises `TimeoutError` if it doesn't complete in time.

```python
result = session.wait(task_id, timeout=60)
```

---

### `status(task_id) → TaskResult`

Single poll — returns current state without waiting.

```python
snap = session.status(task_id)
print(snap.status)   # pending / executing / completed / failed
```

---

### `stream(task_id) → Iterator[dict]`

Subscribe to **SSE events** as the task runs. Requires `pip install "aios-sdk[streaming]"`.

```python
for event in session.stream(task_id):
    if event["type"] == "step":
        print(f"  [{event['step_type']}] {event.get('tool_name', '')}")
    elif event["type"] == "completed":
        print("Done:", event.get("result", "")[:200])
        break
```

---

## TaskResult

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `str` | Unique task identifier |
| `status` | `str` | `pending` / `executing` / `completed` / `failed` / `cancelled` |
| `result` | `str \| None` | Final answer text (set when `status == "completed"`) |
| `error` | `str \| None` | Error message (set when `status == "failed"`) |
| `ok` | `bool` | `True` when `status == "completed"` |
| `steps` | `list` | Execution steps (tool calls, thinking, etc.) |
| `created_at` | `str` | ISO 8601 timestamp |
| `completed_at` | `str \| None` | ISO 8601 timestamp |

---

## Error Handling

```python
from aios_sdk import AgentSession, AIOSError, AuthError, RateLimitError

try:
    result = session.run("analyse sales data")
except AuthError:
    print("Invalid API key")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except AIOSError as e:
    print(f"API error {e.status_code}: {e.detail}")
except TimeoutError:
    print("Task timed out")
```

---

## CLI

```bash
# Run a task from the command line
aios run "Summarise yesterday's audit log" --agent analyst

# Check task status
aios status <task_id>

# Stream task output
aios stream <task_id>

# List available agents
aios agents
```

Set `AIOS_BASE_URL` and `AIOS_API_KEY` environment variables for the CLI.

---

## Full Example

```python
import os
from aios_sdk import AgentSession

session = AgentSession(
    base_url=os.environ["AIOS_BASE_URL"],
    api_key=os.environ["AIOS_API_KEY"],
    agent="financial-analyst",
)

# Non-blocking submit → stream steps → final result
task_id = session.submit(
    "Compare Q1 vs Q2 revenue and highlight anomalies",
    context={"fiscal_year": 2026},
)

print(f"Task {task_id} started")
for event in session.stream(task_id):
    etype = event.get("type")
    if etype == "step":
        tool = event.get("tool_name") or event.get("step_type", "")
        print(f"  ▸ {tool}")
    elif etype in ("completed", "failed"):
        result = event.get("result") or event.get("error", "")
        print(f"\nResult:\n{result}")
        break
```

---

## Changelog

| Version | Changes |
|---------|---------|
| 1.9.27 | Sync with AIOS v1.9.27; public docs/helm pages and MCP resilience updates |
| 1.9.26 | Sync with AIOS v1.9.26; feishu bidirectional bot support |
| 1.9.19 | UniCall channel bindings, mobile workspace deep-link signing |
| 0.1.0 | Initial release |

---

## Links

- [GitHub](https://github.com/chenbinsg/goku-core)
- [API Reference](https://your-aios.example.com/docs)
- [中文文档](SDK_Guidelines.md)
- [Helm Chart](https://chenbinsg.github.io/goku-core-helm)
