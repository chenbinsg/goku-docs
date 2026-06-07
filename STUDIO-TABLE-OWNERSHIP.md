# Studio DB Table Ownership

> Phase 6 deliverable — documents which tables Studio owns, which Core reads, and the
> cross-domain access pattern for the shared-DB strategy (Phase B/C).

---

## Table ownership matrix

### Studio-owned tables (goku-studio: read + write)

| Table | ORM class | Notes |
|-------|-----------|-------|
| `agent_definitions` | `AgentDefinition` | Central config for all agents; Core reads SELECT-only |
| `agent_access_policies` | `AgentAccessPolicy` | RBAC: which users/teams/depts can use which agents |
| `user_agent_favorites` | `UserAgentFavorite` | Per-user starred agents |
| `workflows` | `Workflow` | Workflow DAG definitions |
| `workflow_executions` | `WorkflowExecution` | Execution state; Core writes via engine, Studio reads |
| `workflow_node_executions` | `WorkflowNodeExecution` | Node-level execution log |
| `tools` | `Tool` | Registered tools |
| `auto_skills` | `AutoSkill` | Auto-extracted skill library |
| `plugins` | `Plugin` | Plugin definitions |
| `mcp_servers` | `MCPServer` | MCP server registrations |
| `mcp_capabilities` | `MCPCapability` | Capabilities per server |
| `mcp_resources` | `MCPResource` | Resource definitions |
| `mcp_prompts` | `MCPPrompt` | Prompt templates |
| `mcp_permissions` | `MCPPermission` | User-level MCP permissions |
| `mcp_health_records` | `MCPHealthRecord` | Health probe history |
| `mcp_call_logs` | `MCPCallLog` | Per-call audit log |
| `mcp_capability_authorizations` | `MCPCapabilityAuthorization` | Approved cap use |
| `mcp_capability_blacklists` | `MCPCapabilityBlacklist` | Banned capabilities |
| `mcp_external_connections` | `MCPExternalConnection` | External MCP endpoints |
| `knowledge_docs` | `KnowledgeDoc` | Knowledge base entries |
| `external_memory_sources` | `ExternalMemorySource` | External vector sources |
| `doc_pages` | `DocPage` | Document center pages |
| `ira_investors` | `IraInvestor` | IR investor registry |
| `ira_events` | `IraEvent` | IR events |
| `ira_event_participants` | `IraEventParticipant` | Event attendance |
| `ira_email_templates` | `IraEmailTemplate` | IR email templates |
| `ira_email_queue` | `IraEmailQueue` | Outbound IR email queue |
| `ira_communications` | `IraCommunication` | IR communication log |
| `ira_tasks` | `IraFollowupTask` | IR follow-up tasks |
| `ira_agent_actions` | `IraAgentAction` | Agent action log for IR |
| `ira_investor_groups` | `IraInvestorGroup` | IR investor groupings |
| `ira_investor_group_members` | `IraInvestorGroupMember` | Group membership |
| `ira_approvals` | `IraApprovalRecord` | IR approval records |
| `ira_materials` | `IraMaterial` | IR materials / documents |
| `improvement_proposals` | `ImprovementProposal` | Self-evolution proposals |
| `proposal_outcomes` | `ProposalOutcome` | Proposal apply results |
| `prompt_experiments` | `PromptExperiment` | A/B prompt experiments |
| `tool_call_stats` | `ToolCallStat` | Per-tool usage statistics |

---

### Core reads from Studio tables (SELECT only, never INSERT/UPDATE/DELETE)

| Table | Who reads | Why |
|-------|-----------|-----|
| `agent_definitions` | `agent/executor.py` | Load agent config (model, allowed_tools, skills, system prompt) at task start |
| `agent_definitions` | `routers/core/agent_policies.py` | Resolve agent for policy checks |
| `workflows` | `services/workflow_engine.py` | Load DAG for execution |
| `workflow_executions` | `services/workflow_engine.py` | Read execution state to continue |
| `tools` | `agent/tool_registry.py` | Load tool definitions at registry startup |
| `mcp_servers` | `agent/mcp/registry_integration.py` | Load enabled MCP servers into runtime |
| `mcp_capabilities` | `agent/mcp/registry_integration.py` | Capability list for tool wrapping |
| `knowledge_docs` | `services/memory.py` | Knowledge search for agent context |
| `auto_skills` | `agent/executor.py` | Inject reusable skills into ReAct prompt |
| `improvement_proposals` | `services/optimizer.py` | Apply LOW/MED proposals in daily batch |
| `agent_access_policies` | `routers/core/agent_policies.py` | Enforce DefaultDeny access gates |

---

### Studio reads from Core tables (SELECT only)

| Table | Why |
|-------|-----|
| `tasks` | Display task history in agent detail view |
| `conversations` | Show recent conversations per agent |
| `cost_ledger` | Per-agent cost breakdown in Studio UI |
| `users` | User lookup for access policy display |
| `tenants` | Tenant scope for multi-tenant queries |
| `memory` | Show agent memory entries in knowledge hub |

---

## Cross-domain access rules

```
┌──────────────┐   SELECT only    ┌──────────────┐
│  goku-core   │ ──────────────→  │ agent_defs   │  (Studio-owned)
│  executor    │                  │ workflows    │
│  tool_reg    │                  │ tools        │
└──────────────┘                  │ mcp_servers  │
                                  └──────────────┘

┌──────────────┐   SELECT only    ┌──────────────┐
│ goku-studio  │ ──────────────→  │ users        │  (Core-owned)
│  routers     │                  │ tasks        │
│  services    │                  │ tenants      │
└──────────────┘                  └──────────────┘
```

**Rules enforced by architecture tests (`test_architecture.py`):**
- Core executor never calls `db.add()` / `db.merge()` on Studio-owned ORM models
- Studio routers never import `app.agent.executor` or Core runtime services
- Enforced statically via AST scan on every CI run

---

## Split-DB migration path (future Phase D+)

When Studio gets its own database, the cross-domain reads above become HTTP calls:

| Current (shared DB) | Future (split DB) |
|---------------------|-------------------|
| `db.query(AgentDefinition).filter(...)` | `GET /api/studio/v1/agents/{id}` |
| `db.query(Workflow).filter(...)` | `GET /api/studio/v1/workflows/{id}` |
| `db.query(KnowledgeDoc).filter(...)` | `GET /api/studio/v1/knowledge?tenant=...` |

Core would cache these responses (Redis or in-process LRU) to avoid per-request latency.
Studio would publish a webhook/event on config changes to invalidate the cache.
