from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from pydantic_ai import RunContext

from app.uniclaw.core.deps import SkillDeps
from app.uniclaw.skills.registry import SkillMetadata
from app.uniclaw.tools.base import ToolResult

from _jira_client import (
    create_jira_client,
    ensure_connection,
    issue_description_to_payload,
    load_jira_connection,
    resolve_project_key,
)

SKILL_METADATA = SkillMetadata(
    name="jira_issue_create",
    description="Create a Jira issue via REST API.",
    category="provider:jira",
    provider_type="jira",
    instance_required=True,
    location="built-in",
)


async def handler(
    ctx: RunContext[SkillDeps],
    summary: str,
    description: str,
    issue_type: str = "Task",
    project_key: str = "",
    priority: str = "",
) -> dict:
    extra = ctx.deps.extra if isinstance(ctx.deps.extra, dict) else {}
    print(f"[jira_issue_create] extra keys: {list(extra.keys())}")
    print(f"[jira_issue_create] provider_instance: {extra.get('provider_instance', 'NOT SET')}")
    
    base_url, username, password, api_version, default_project = load_jira_connection(extra)
    print(f"[jira_issue_create] base_url={base_url}, username={username}, password={'***' if password else 'None'}")

    with create_jira_client(base_url, username, password) as client:
        ensure_connection(client, api_version)
        target_project = project_key or resolve_project_key(client, api_version, default_project)

        fields: dict = {
            "project": {"key": target_project},
            "summary": summary,
            "description": issue_description_to_payload(description, api_version),
            "issuetype": {"name": issue_type},
        }
        if priority:
            fields["priority"] = {"name": priority}

        resp = client.post(f"/rest/api/{api_version}/issue", json={"fields": fields})
        print(f"[jira_issue_create] POST response: {resp.status_code}")
        print(f"[jira_issue_create] POST body: {resp.text[:500]}")
        if resp.status_code not in (200, 201):
            return ToolResult.error(
                f"Create issue failed: {resp.status_code} {resp.text[:300]}"
            ).to_dict()

        data = resp.json()
        issue_key = data.get("key", "")
        issue_id = data.get("id", "")
        return ToolResult.text(
            f"Created issue {issue_key}",
            details={"issue_key": issue_key, "issue_id": issue_id, "project_key": target_project},
        ).to_dict()
