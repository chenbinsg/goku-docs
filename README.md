# Goku Platform Docs

> Cross-repo documentation for the **Goku AI Agent Platform** — a multi-tenant, enterprise-grade system for building and running AI agents at scale.

---

## Platform Overview

Goku is composed of four independent services:

| Repo | Port (backend / frontend) | Role |
|------|--------------------------|------|
| [goku-core](https://github.com/chenbinsg/goku-core) | `:8106` / `:5106` | **Runtime** — chat, tasks, approvals, analytics, channels |
| goku-studio | `:8107` / `:5107` | **Studio** — agent/workflow/tool/knowledge builder |
| goku-router | `:8108` | **Model gateway** — LLM routing, catalog, load balancing |
| goku-sdk | library | **SDK** — Python `aios-sdk` + TypeScript `@goku-ai/sdk` |

Core and Studio share a single MySQL database. Studio writes agent definitions; Core executes them. They can run on the same or separate servers.

---

## Contents

### Getting Started
| Doc | Description |
|-----|-------------|
| [getting-started/installation.md](getting-started/installation.md) | Local install (macOS / Linux) and Docker Compose |
| [getting-started/quickstart.md](getting-started/quickstart.md) | Create your first agent in 5 minutes |
| [getting-started/environment-variables.md](getting-started/environment-variables.md) | All `.env` variables explained |

### Architecture
| Doc | Description |
|-----|-------------|
| [architecture.md](architecture.md) | Platform overview — repos, request flow, data model |
| [auth-bridge.md](auth-bridge.md) | JWT handoff protocol between goku-core and goku-studio |

### Operations
| Doc | Description |
|-----|-------------|
| [ops/deploy-sop.md](ops/deploy-sop.md) | Production deployment standard procedure |
| [ops/upgrade-sop.md](ops/upgrade-sop.md) | Version upgrade procedure |
| [ops/rollback-sop.md](ops/rollback-sop.md) | Rollback procedure |
| [deploy-helm.md](deploy-helm.md) | Kubernetes / Helm deployment |

### Security & Hardening
| Doc | Description |
|-----|-------------|
| [production-security-hardening.md](production-security-hardening.md) | Production security checklist |
| [security/P0_S1_key_rotation.md](security/P0_S1_key_rotation.md) | Secret key rotation runbook |

### Integrations
| Doc | Description |
|-----|-------------|
| [feishu-bidirectional-bot-setup.md](feishu-bidirectional-bot-setup.md) | Feishu (Lark) bot integration |
| [MCP_Knowledge_Base.md](MCP_Knowledge_Base.md) | MCP Knowledge Base connector |
| [MCP_AIBI_Capabilty.md](MCP_AIBI_Capabilty.md) | MCP BI capability reference |

### SDK & API
| Doc | Description |
|-----|-------------|
| [sdk-reference.md](sdk-reference.md) | Python and TypeScript SDK reference |
| [SDK_Guidelines.md](SDK_Guidelines.md) | SDK contribution and usage guidelines |

### Testing & Performance
| Doc | Description |
|-----|-------------|
| [testing.md](testing.md) | Test strategy and coverage gates |
| [perf_baseline.md](perf_baseline.md) | Performance baseline metrics |

### Postmortems
| Doc | Description |
|-----|-------------|
| [postmortems/](postmortems/) | Incident postmortems and lessons learned |

---

## Repo-specific docs

Each repo keeps its own inline docs. Cross-repo / platform-wide docs live here.

| Repo | Internal docs |
|------|---------------|
| `goku-core` | `backend/docs/` + `CLAUDE.md` |
| `goku-studio` | `backend/docs/` + `CLAUDE.md` |
| `goku-sdk` | `python/README.md`, `typescript/README.md`, `CHANGELOG.md` |
| `goku-router` | `README.md` |

---

## Contributing

- Docs live here in `goku-docs`; code-level docs (`CLAUDE.md`, inline comments) stay in each repo.
- All filenames use lowercase-with-hyphens.
- Keep internal links relative so they resolve on both GitHub and any doc site.
- For breaking platform changes, update `architecture.md` in the same PR.
