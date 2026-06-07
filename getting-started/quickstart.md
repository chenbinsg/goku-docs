# Quickstart — Create Your First Agent in 5 Minutes

> Assumes Goku is already running locally. See [installation.md](installation.md) if not.

---

## Step 1 — Open Goku Studio

Navigate to **http://localhost:5107**.  
If you are already logged into Goku-Core (`:5106`) the auth bridge will sign you in automatically.

---

## Step 2 — Create an Agent

1. Click **Agents** in the left sidebar.
2. Click **+ New Agent**.
3. Fill in:
   - **Name**: `My First Agent`
   - **System Prompt**: `You are a helpful assistant. Answer concisely.`
   - **Model**: pick any available model from the dropdown.
4. Click **Save**.

---

## Step 3 — Test It

1. On the agent tile, click the **Test** button (▶).  
   Goku-Core opens in a new tab with that agent pre-selected in the chat.
2. Type a message and press Enter.
3. You should see a streaming response.

---

## Step 4 — Add a Tool (optional)

1. Back in Studio, open your agent and go to the **Tools** tab.
2. Click **Add Tool** → select a built-in tool (e.g. `web_search`).
3. Save and test again — the agent will now call the tool automatically when needed.

---

## Next Steps

| Goal | Where to go |
|------|-------------|
| Build a multi-step workflow | **Studio → Workflows** |
| Connect a knowledge base | **Studio → Knowledge** |
| Connect Feishu / Slack | [feishu-bidirectional-bot-setup.md](../feishu-bidirectional-bot-setup.md) |
| Deploy to production | [ops/deploy-sop.md](../ops/deploy-sop.md) |
| Use the SDK | [sdk-reference.md](../sdk-reference.md) |
