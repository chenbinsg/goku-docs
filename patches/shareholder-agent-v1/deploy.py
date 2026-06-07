#!/usr/bin/env python3
"""
Patch deployer -- 股东会组织助理 agent

Usage:
    python deploy.py --host https://aios.example.com --token <admin_jwt>

What this does:
    1. Checks whether the agent already exists (by fixed UUID d4b49ecc...)
    2. If missing: creates it via POST /api/v1/agents (UPSERT semantics)
    3. If present but outdated: reports the diff so you can manually update
    4. Verifies the conversations.py auto-bind can find it by name

Prerequisites:
    pip install requests
    The AIOS backend must support event_agent type (registered since v1.0).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed -- run: pip install requests")

HERE = Path(__file__).parent
AGENT_DEF = HERE / "agent" / "agent_definition.json"
CANONICAL_ID = "d4b49ecc-c254-4ca8-b5bc-a1c6250cb109"
AGENT_NAME = "股东会组织助理"


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_existing(host: str, token: str) -> dict | None:
    """Try to fetch the agent by canonical UUID."""
    resp = requests.get(f"{host}/api/v1/agents/{CANONICAL_ID}", headers=_h(token), timeout=15)
    if resp.status_code == 404:
        return None
    if resp.ok:
        return resp.json()
    # Fallback: search by name
    resp2 = requests.get(
        f"{host}/api/v1/agents",
        headers=_h(token),
        params={"limit": 100},
        timeout=15,
    )
    if resp2.ok:
        items = resp2.json()
        if isinstance(items, dict):
            items = items.get("items") or items.get("data") or []
        for a in items:
            if a.get("name") == AGENT_NAME:
                print(f"[warn] Agent found by name but with different id: {a.get('id')}")
                return a
    return None


def check_diff(existing: dict, desired: dict) -> list[str]:
    """Return list of fields that differ between existing and desired."""
    diffs = []
    for key in ("allowed_tools", "skills", "max_steps", "system_prompt"):
        ev = existing.get(key) or existing.get("system_prompt_override")
        dv = desired.get(key) or desired.get("system_prompt")
        if key == "system_prompt":
            ev = existing.get("system_prompt_override")
            dv = desired.get("system_prompt")
        if isinstance(ev, list):
            ev = sorted(ev)
        if isinstance(dv, list):
            dv = sorted(dv)
        if ev != dv:
            diffs.append(key)
    return diffs


def create_agent(host: str, token: str, tenant_id: str | None) -> dict:
    with open(AGENT_DEF) as f:
        payload = json.load(f)
    if tenant_id:
        payload["tenant_id"] = tenant_id

    resp = requests.post(f"{host}/api/v1/agents", headers=_h(token), json=payload, timeout=30)
    if resp.ok:
        return resp.json()
    if resp.status_code == 409:
        print("[info] 409 Conflict -- agent already exists in DB, fetching by name...")
        existing = get_existing(host, token)
        if existing:
            return existing
    sys.exit(f"[error] Failed to create agent: {resp.status_code}\n{resp.text[:500]}")


def patch_agent(host: str, token: str, agent_id: str) -> None:
    """PATCH the existing agent with the latest tool/skill list."""
    with open(AGENT_DEF) as f:
        payload = json.load(f)
    resp = requests.patch(
        f"{host}/api/v1/agents/{agent_id}",
        headers=_h(token),
        json={
            "allowed_tools": payload["allowed_tools"],
            "skills": payload["skills"],
            "system_prompt_override": payload["system_prompt"],
            "max_steps": payload["max_steps"],
        },
        timeout=30,
    )
    if resp.ok:
        print(f"  [ok]  Agent patched: {resp.json().get('name')}")
    else:
        print(f"  [warn] PATCH failed: {resp.status_code} {resp.text[:200]}")
        print("         Apply db/migrations/2026_05_04_shareholder_assistant_tools.sql manually.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy 股东会组织助理 agent to AIOS")
    parser.add_argument("--host", required=True, help="AIOS base URL, e.g. https://aios.example.com")
    parser.add_argument("--token", required=True, help="Admin JWT bearer token")
    parser.add_argument("--tenant-id", default=None, help="Tenant ID (leave blank for default)")
    parser.add_argument("--force-patch", action="store_true",
                        help="If agent exists, force-update tools/skills to match agent_definition.json")
    args = parser.parse_args()

    host = args.host.rstrip("/")
    print(f"\n=== 股东会组织助理 Patch Deployer ===")
    print(f"Target: {host}\n")

    # Step 1 -- check existence
    print(f"[1/2] Checking whether agent exists (id={CANONICAL_ID})...")
    existing = get_existing(host, args.token)

    if existing:
        print(f"      Agent found: id={existing.get('id')}  name={existing.get('name')}")
        diffs = check_diff(existing, json.load(open(AGENT_DEF)))
        if diffs:
            print(f"      Outdated fields: {diffs}")
            if args.force_patch:
                print("      --force-patch set: updating...")
                patch_agent(host, args.token, existing["id"])
            else:
                print("      Run with --force-patch to update tools/skills to latest.")
        else:
            print("      Agent is up-to-date. No action needed.")
        print()
    else:
        print("      Agent NOT found -- creating...\n")
        print("[2/2] Creating 股东会组织助理 agent definition...")
        agent = create_agent(host, args.token, args.tenant_id)
        agent_id = agent.get("id") or agent.get("agent_id")
        print(f"      [ok] Agent created: id={agent_id}  name={agent.get('name')}")
        print()

    print("=== Done ===")
    print("Verify in AIOS UI -> Agent Management -> search [股东会组织助理]")
    print("Expected: event_agent type, 28 tools, 18 skills, icon=CalendarOutlined, color=#c41d7f")
    print()


if __name__ == "__main__":
    main()
