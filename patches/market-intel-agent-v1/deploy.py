#!/usr/bin/env python3
"""
Patch deployer — 商机情报员 agent (market_intel_agent)

Usage:
    python deploy.py --host https://aios.example.com --token <admin_jwt>

What this does:
    1. Verifies market_intel_agent type is registered (requires AIOS ≥ commit that
       adds it to subagent_config.py; will error clearly if the backend is older)
    2. Installs the baiwu-opportunity-intelligence skill (uploads all reference files)
    3. Creates the 商机情报员 AgentDefinition via the AIOS REST API
    4. Prints the agent ID so you can find it in the UI

Prerequisites:
    pip install requests
    AIOS backend updated to include market_intel_agent in subagent_config.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed — run: pip install requests")

HERE = Path(__file__).parent


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def check_agent_type(host: str, token: str) -> bool:
    """Return True if market_intel_agent type is registered in this AIOS instance."""
    url = f"{host}/api/v1/agents/types"
    resp = requests.get(url, headers=_headers(token), timeout=15)
    if resp.status_code == 404:
        # Older AIOS — try the list endpoint and look for the type field
        resp = requests.get(f"{host}/api/v1/agents", headers=_headers(token), timeout=15)
        if resp.ok:
            print("[warn] /api/v1/agents/types not found; cannot pre-verify type. Proceeding.")
            return True
        return False
    resp.raise_for_status()
    types = resp.json()
    registered = [t.get("agent_type") or t.get("type") or t for t in types]
    return "market_intel_agent" in registered


def install_skill(host: str, token: str) -> bool:
    """
    Upload baiwu-opportunity-intelligence skill files to the AIOS knowledge base
    so the agent can reference them via knowledge_search.
    """
    skill_dir = HERE / "skill-refs" / "baiwu-opportunity-intelligence"
    if not skill_dir.exists():
        print(f"[warn] Skill directory not found: {skill_dir}. Skipping skill install.")
        return False

    files_to_upload = list(skill_dir.glob("*.md")) + list((skill_dir / "references").glob("*.md"))
    if not files_to_upload:
        print("[warn] No .md files found in skill directory. Skipping.")
        return False

    upload_url = f"{host}/api/v1/knowledge/upload"
    headers_no_ct = {"Authorization": f"Bearer {token}"}
    success_count = 0
    for fpath in sorted(files_to_upload):
        rel = fpath.relative_to(HERE / "skills")
        with open(fpath, "rb") as f:
            try:
                resp = requests.post(
                    upload_url,
                    headers=headers_no_ct,
                    files={"file": (str(rel), f, "text/markdown")},
                    data={"tags": '["baiwu-opportunity-intelligence", "skill", "market-intel"]'},
                    timeout=30,
                )
                if resp.ok:
                    print(f"  [ok]  uploaded: {rel}")
                    success_count += 1
                else:
                    print(f"  [warn] {rel}: {resp.status_code} {resp.text[:120]}")
            except Exception as exc:
                print(f"  [warn] {rel}: {exc}")

    print(f"[skill] Uploaded {success_count}/{len(files_to_upload)} skill files.")
    return success_count > 0


def create_agent(host: str, token: str, tenant_id: str | None) -> dict:
    """POST the agent_definition.json to the AIOS API and return the created agent."""
    defn_path = HERE / "agent" / "agent_definition.json"
    if not defn_path.exists():
        sys.exit(f"[error] agent_definition.json not found at {defn_path}")

    with open(defn_path) as f:
        payload = json.load(f)

    if tenant_id:
        payload["tenant_id"] = tenant_id

    url = f"{host}/api/v1/agents"
    resp = requests.post(url, headers=_headers(token), json=payload, timeout=30)
    if resp.status_code == 409:
        print("[info] Agent already exists (409 Conflict). Attempting to find existing agent…")
        agents = requests.get(
            f"{host}/api/v1/agents",
            headers=_headers(token),
            params={"limit": 100},
            timeout=15,
        ).json()
        items = agents.get("items") or agents.get("data") or agents
        for a in items:
            if a.get("name") == payload["name"] or a.get("agent_type") == payload["agent_type"]:
                print(f"[info] Found existing agent: id={a.get('id')}")
                return a
        sys.exit("[error] 409 but could not locate existing agent. Check AIOS manually.")
    if not resp.ok:
        sys.exit(f"[error] Failed to create agent: {resp.status_code}\n{resp.text[:500]}")
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy 商机情报员 agent to AIOS")
    parser.add_argument("--host", required=True, help="AIOS base URL, e.g. https://aios.example.com")
    parser.add_argument("--token", required=True, help="Admin JWT bearer token")
    parser.add_argument("--tenant-id", default=None, help="Tenant ID (leave blank for default tenant)")
    parser.add_argument("--skip-skill-upload", action="store_true", help="Skip uploading skill reference files")
    args = parser.parse_args()

    host = args.host.rstrip("/")
    print(f"\n=== 商机情报员 Patch Deployer ===")
    print(f"Target: {host}\n")

    # Step 1 — verify agent type is registered
    print("[1/3] Checking market_intel_agent type registration…")
    if not check_agent_type(host, args.token):
        sys.exit(
            "[error] market_intel_agent is NOT registered in this AIOS instance.\n"
            "        Update the backend (subagent_config.py) and redeploy before running this patch."
        )
    print("      ✓ market_intel_agent type found.\n")

    # Step 2 — upload skill files
    if not args.skip_skill_upload:
        print("[2/3] Uploading baiwu-opportunity-intelligence skill files…")
        install_skill(host, args.token)
    else:
        print("[2/3] Skipped skill file upload (--skip-skill-upload).")
    print()

    # Step 3 — create agent
    print("[3/3] Creating 商机情报员 agent definition…")
    agent = create_agent(host, args.token, args.tenant_id)
    agent_id = agent.get("id") or agent.get("agent_id")
    print(f"      ✓ Agent created: id={agent_id}  name={agent.get('name')}")
    print()
    print("=== Done ===")
    print(f"Open the AIOS UI -> Agent Management -> search for [商机情报员] (id: {agent_id})")
    print("Verify tools: baiwu_daily_report, web_search, web_fetch, knowledge_search, email_send")
    print()


if __name__ == "__main__":
    main()
