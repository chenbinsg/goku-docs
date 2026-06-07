# Migration Domain Attribution

All 42 existing migrations (0046–0086) are tracked against their owning domain.

## Domain definitions

| Domain | Tables owned | Future repo |
|--------|-------------|-------------|
| **shared** | Baseline schema, cross-cutting | goku-core (stays) |
| **admin** | users, tenants, departments, teams, roles, SSO, billing, push, notifications, external_tools, heartbeats | goku-core |
| **studio** | agent_definitions, workflows, tools, MCP servers, knowledge, memory, skills, plugins, IRA, improvement_proposals, prompt_experiments, tool_call_stats | goku-studio |
| **core** | tasks, task_steps, conversations, conversation_messages, approvals, stateful_*, memory, cost_ledger, message_reactions, reimbursements, procurement_requests, contract_reviews, incidents | goku-core |
| **channels** | channel_accounts, channel_messages, channel_actions, channel_bind_codes, incoming_emails, cs_*, shareholder_*, market_* | goku-core |

---

## Migration map

| Migration | Domain | Tables created/altered |
|-----------|--------|----------------------|
| `0046_legacy_baseline_anchor` | shared | — (anchor) |
| `0047_baseline_schema` | shared | All pre-existing tables (baseline snapshot) |
| `0048_incoming_messages_source_type` | channels | incoming_emails: +source_type column |
| `0049_mcp_capability_rate_limit` | studio | mcp_capabilities: +rate_limit column |
| `0050_drop_rc_agent` | studio | — (drops obsolete rc_agent rows) |
| `0051_agent_visibility_and_favorites` | studio | user_agent_favorites, agents: +visibility |
| `0052_departments_table` | admin | departments |
| `0053_cost_ledger_source` | core | cost_ledger: +source column |
| `0054_external_memory_sources` | studio | external_memory_sources |
| `0055_teams_org_structure` | admin | teams, users: +team_id |
| `0056_agent_access_policies` | studio | agent_access_policies |
| `0057_aap_tenant_nullable` | studio | agent_access_policies: tenant nullable |
| `0058_improvement_proposals` | studio | improvement_proposals |
| `0059_fix_taskstatus_enum_case` | core | tasks: fix TaskStatus enum case |
| `0060_external_tools` | admin | external_tools |
| `0061_push_subscriptions` | admin | push_subscriptions |
| `0062_enterprise_sso` | admin | sso_configurations, sso_group_mappings |
| `0063_add_missing_indexes` | shared | cross-domain index additions |
| `0064_add_conversation_id_to_tasks` | core | tasks: +conversation_id |
| `0065_vdi_jobs` | studio | vdi_jobs (temp table) |
| `0066_zhuyun_user_fields` | admin | users: +zhuyun extra fields |
| `0067_drop_models_table` | admin | — (drops models table, now Goku-Router) |
| `0068_add_agent_id_to_conversation_messages` | core | conversation_messages: +agent_id |
| `0069_add_dlp_bypass_to_agents` | studio | agent_definitions: +dlp_bypass |
| `0070_unicall_channel_gateway` | channels | channel_accounts, channel_messages, channel_actions, notification_deliveries |
| `0071_drop_vdi_jobs` | studio | — (drops vdi_jobs) |
| `0072_heartbeat_workflow_id` | admin | heartbeats: +workflow_id |
| `0073_workflow_agent_id` | studio | workflows: +agent_id |
| `0074_agent_auto_send_drafts` | studio | agent_definitions: +auto_send_drafts |
| `0075_unicall_phase2` | channels | channel_bind_codes |
| `0076_message_reactions` | core | message_reactions |
| `0077_proposal_outcomes` | studio | proposal_outcomes |
| `0078_prompt_experiments` | studio | prompt_experiments |
| `0079_tool_call_stats` | studio | tool_call_stats |
| `0080_drop_rc_agent_tools_residue` | studio | — (cleanup) |
| `0081_mcp_servers_unique_active_code` | studio | mcp_servers: unique index |
| `0082_stateful_transitions` | core | stateful_transitions |
| `0083_stateful_action_policies` | core | stateful_action_policies |
| `0084_stateful_policy_retry_flag` | core | stateful_action_policies: +retry_flag |
| `0085_reimbursements_and_policy_agent_id` | core | reimbursements |
| `0086_procurement_contract_incident_tables` | core | procurement_requests, contract_reviews, incidents |

---

## Future migration convention

New migrations **do not go into `alembic/versions/`**. Instead, use the domain-specific chain:

```
backend/alembic/
    versions/        ← frozen (0046–0086); do not add new files here
    core/            ← NEW: goku-core domain migrations (0087+)
        env.py
        versions/
            0087_*.py
    studio/          ← NEW: goku-studio domain migrations
        env.py
        versions/
            studio_0001_*.py
```

Run the correct alembic environment:
```bash
# Core domain (tasks, conversations, stateful, channels, admin)
alembic -c alembic/core/alembic.ini upgrade head
make migration-core name="add xyz column"

# Studio domain (agents, workflows, tools, MCP, knowledge)
alembic -c alembic/studio/alembic.ini upgrade head
make migration-studio name="add xyz column"
```

Both chains point to the same database but manage separate table subsets.
The `down_revision` of the first migration in each domain chain is `"0086"` — the shared baseline.

---

## Repo split plan for migrations

When the repos are physically split (Step 4):

| Migration files | Destination repo |
|----------------|-----------------|
| `alembic/versions/0046–0086` | goku-core (shared baseline, never re-run) |
| `alembic/core/versions/0087+` | goku-core |
| `alembic/studio/versions/studio_0001+` | goku-studio (own alembic, own DB eventually) |
