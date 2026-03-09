"""

JIRA shared code

for JIRA factory, for Provider Skills.
"""

from __future__ import annotations

from typing import Any


def create_jira_client(instance_config: dict[str, Any]):
    """

create JIRA REST API

    Args:
        instance_config:instanceconfigurationparameter(contains base_url, username, token)

    Returns:
        configuration httpx.Async-Client

    Example usage:
        ```python
        config = ctx.deps.extra["provider_instance"]
        client = create_jira_client(config)
        async with client:
            resp = await client.get("/rest/api/2/myself")
        ```
    
"""
    import httpx

    base_url = instance_config.get("base_url", "")
    username = instance_config.get("username", "")
    token = instance_config.get("token", "")

    return httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        auth=(username, token),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )
