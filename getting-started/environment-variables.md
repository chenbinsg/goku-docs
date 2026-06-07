# Environment Variables Reference

All variables go in `backend/.env` (copy `backend/.env.example` to get started).

---

## Required

| Variable | Example | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `mysql+pymysql://root:pass@127.0.0.1:3306/goku` | MySQL connection string |
| `SECRET_KEY` | *(32+ random chars)* | JWT signing key — generate with `openssl rand -hex 32` |
| `LLM_PROVIDER` | `openai` | LLM backend: `openai`, `azure`, `ollama`, `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini` | Default model name |
| `OPENAI_API_KEY` | `sk-...` | Required when `LLM_PROVIDER=openai` |
| `AGENT_WORKSPACE` | `/path/to/workspace` | Directory for agent file operations |

---

## Service URLs

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_STUDIO_URL` | `http://localhost:5107` | goku-studio frontend URL (Core frontend) |
| `VITE_RUNTIME_URL` | `http://localhost:5106` | goku-core frontend URL (Studio frontend) |
| `GOKU_ROUTER_URL` | *(unset)* | goku-router base URL; enables model proxying when set |

---

## LLM Providers

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key |
| `AZURE_OPENAI_ENDPOINT` | Azure endpoint URL |
| `AZURE_OPENAI_API_VERSION` | API version (e.g. `2024-02-01`) |
| `ANTHROPIC_API_KEY` | Anthropic Claude key |
| `OLLAMA_BASE_URL` | Ollama server URL (default `http://localhost:11434`) |

---

## Email & Notifications

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` / `SMTP_PORT` | SMTP server for outbound email |
| `SMTP_USER` / `SMTP_PASSWORD` | SMTP credentials |
| `TOOL_PROBE_REPORT_EMAIL` | Recipient for tool health reports |
| `AGENT_PROBE_REPORT_EMAIL` | Recipient for agent probe reports |
| `LOG_ANALYSIS_REPORT_EMAIL` | Recipient for log analysis reports |
| `IR_DAILY_REPORT_EMAIL` | Recipient for daily IR reports |

---

## Microsoft 365 / Outlook Integration

| Variable | Description |
|----------|-------------|
| `OUTLOOK_CLIENT_ID` | Azure app Client ID |
| `OUTLOOK_CLIENT_SECRET` | Azure app Client Secret |
| `OUTLOOK_TENANT_ID` | Azure Tenant ID |
| `OUTLOOK_MAILBOX` | Mailbox owner email |
| `OUTLOOK_CALENDAR_MAILBOX` | Calendar owner email |
| `OUTLOOK_CALENDAR_TIMEZONE` | Timezone (e.g. `Tokyo Standard Time`) |

---

## Rate Limits (optional overrides)

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_LOGIN` | `10/minute` | Login endpoint |
| `RATE_LIMIT_REGISTER` | `5/minute` | Registration endpoint |
| `RATE_LIMIT_CREATE_TASK` | `60/minute` | Task creation |
| `RATE_LIMIT_SEND_MESSAGE` | `120/minute` | Chat message send |
| `RATE_LIMIT_UPLOAD` | `20/minute` | File uploads |

---

## SSO / Auth

| Variable | Description |
|----------|-------------|
| `KEYCLOAK_URL` | Keycloak server URL |
| `KEYCLOAK_REALM` | Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | Keycloak client ID |
| `KEYCLOAK_CLIENT_SECRET` | Keycloak client secret |
