"""


JIRA create-issue skill

create JIRA Issue, JIRA instance.
"""

from __future__ import annotations

from typing import Any

from app.uniclaw.skills.registry import SkillMetadata

SKILL_METADATA = SkillMetadata(
    name="create_issue",
    description="在 JIRA 中创建 Issue（需要 project_key、summary，可选 description、issue_type）",
    category="provider:jira",
    requires_auth=True,
    timeout_seconds=30,
)


async def handler(
    ctx: Any,
    project_key: str,
    summary: str,
    description: str = "",
    issue_type: str = "Task",
) -> dict:
    """

create JIRA Issue

    Args:
        ctx:RunContext[SkillDeps]
        project_key:JIRA Key(such as "PROJ")
        summary:Issue heading
        description:Issue description(optional)
        issue_type:Issue type(default "Task")

    Returns:
        `ToolResult`-formatted dictionary
    
"""
    instance_config = ctx.deps.extra.get("provider_instance", {})
    if not instance_config:
        return {
            "is_error": True,
            "content": [{"type": "text", "text": "未选择 JIRA 实例，请先调用 select_provider_instance"}],
        }

    base_url = instance_config.get("base_url", "")
    username = instance_config.get("username", "")
    token = instance_config.get("token", "")

    if not all([base_url, username, token]):
        return {
            "is_error": True,
            "content": [{"type": "text", "text": "JIRA 实例配置不完整，缺少 base_url/username/token"}],
        }

    # JIRA REST API
    import httpx

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
        }
    }

    try:
        async with httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            auth=(username, token),
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        ) as client:
            resp = await client.post("/rest/api/2/issue", json=payload)
            resp.raise_for_status()
            data = resp.json()

            issue_key = data.get("key", "unknown")
            issue_url = f"{base_url}/browse/{issue_key}"

            return {
                "is_error": False,
                "content": [{"type": "text", "text": f"已创建 Issue: {issue_key}\n链接: {issue_url}"}],
                "details": {
                    "key": issue_key,
                    "url": issue_url,
                    "id": data.get("id"),
                },
            }
    except httpx.HTTPStatusError as e:
        return {
            "is_error": True,
            "content": [{"type": "text", "text": f"创建 JIRA Issue 失败: HTTP {e.response.status_code}"}],
        }
    except Exception as e:
        return {
            "is_error": True,
            "content": [{"type": "text", "text": f"创建 JIRA Issue 失败: {str(e)}"}],
        }
