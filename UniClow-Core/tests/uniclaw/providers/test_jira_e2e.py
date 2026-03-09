# -*- coding: utf-8 -*-
"""
JIRA Provider E2E tests.

Live integration tests against real JIRA Server/DC instance.
Gated by JIRA_E2E=1 environment variable -- skipped by default.

Run:
    JIRA_E2E=1 python -m pytest tests/uniclaw/providers/test_jira_e2e.py -v -s

Config is read from uniclaw.json -> service_providers.jira -> first instance.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import pytest

_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_ROOT))

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("JIRA_E2E") != "1",
        reason="Live JIRA E2E test -- set JIRA_E2E=1 to run",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def jira_config() -> dict:
    """Load JIRA connection config from uniclaw.json."""
    config_path = _ROOT / "uniclaw.json"
    assert config_path.exists(), "uniclaw.json not found at project root"

    config = json.loads(config_path.read_text(encoding="utf-8"))
    sp = config.get("service_providers", {}).get("jira", {})
    assert sp, "No jira entry in service_providers"

    instance_name = next(iter(sp))
    instance = sp[instance_name]

    for key in ("base_url", "username", "token"):
        assert instance.get(key), f"Missing required field: jira.{instance_name}.{key}"

    return instance


@pytest.fixture(scope="module")
def api_version(jira_config: dict) -> str:
    return jira_config.get("api_version", "2")


@pytest.fixture(scope="module")
def jira_client(jira_config: dict, api_version: str):
    """Create a synchronous httpx client for JIRA REST API."""
    base_url = jira_config["base_url"].rstrip("/")

    with httpx.Client(
        base_url=base_url,
        auth=(jira_config["username"], jira_config["token"]),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        resp = client.get(f"/rest/api/{api_version}/serverInfo")
        assert resp.status_code == 200, (
            f"Cannot connect to JIRA at {base_url}: {resp.status_code} {resp.text[:200]}"
        )
        yield client


@pytest.fixture(scope="module")
def project_key(jira_client: httpx.Client, api_version: str) -> str:
    """Auto-detect a usable project key (prefer one with existing issues)."""
    resp = jira_client.get(f"/rest/api/{api_version}/project")
    assert resp.status_code == 200, f"Cannot list projects: {resp.status_code}"
    projects = resp.json()
    assert projects, "No JIRA projects available on this server"

    # Prefer a project that already has issues
    for proj in projects:
        key = proj["key"]
        search = jira_client.get(
            f"/rest/api/{api_version}/search",
            params={"jql": f"project = {key}", "maxResults": 1, "fields": "key"},
        )
        if search.status_code == 200 and search.json().get("total", 0) > 0:
            return key

    # Fallback to first project
    return projects[0]["key"]


@pytest.fixture(scope="module")
def created_issue_key(jira_client: httpx.Client, project_key: str, api_version: str):
    """
    Create a test issue and yield its key.
    Shared across tests that need an existing issue.
    Cleanup after all tests in this module.
    """
    # Query create metadata to discover required fields
    meta_resp = jira_client.get(
        f"/rest/api/{api_version}/issue/createmeta",
        params={"projectKeys": project_key, "expand": "projects.issuetypes.fields"},
    )

    fields_payload: dict = {
        "project": {"key": project_key},
        "summary": "[E2E Test] Uniclaw automated test issue",
        "description": "Created by test_jira_e2e.py. Safe to delete.",
        "issuetype": {"name": "Task"},
    }

    # If createmeta available, try to satisfy required fields
    if meta_resp.status_code == 200:
        meta = meta_resp.json()
        for proj in meta.get("projects", []):
            if proj["key"] != project_key:
                continue
            for itype in proj.get("issuetypes", []):
                if itype["name"] != "Task":
                    continue
                for field_key, field_def in itype.get("fields", {}).items():
                    if not field_def.get("required"):
                        continue
                    if field_key in ("project", "summary", "issuetype", "description", "reporter"):
                        continue
                    # Try to set component if required and available
                    if field_key == "components":
                        comp_resp = jira_client.get(
                            f"/rest/api/{api_version}/project/{project_key}/components"
                        )
                        if comp_resp.status_code == 200:
                            comps = comp_resp.json()
                            if comps:
                                fields_payload["components"] = [{"id": comps[0]["id"]}]
                    # Try to set priority if required
                    elif field_key == "priority":
                        fields_payload.setdefault("priority", {"name": "Medium"})

    resp = jira_client.post(
        f"/rest/api/{api_version}/issue",
        json={"fields": fields_payload},
    )
    assert resp.status_code in (200, 201), (
        f"Setup: create issue failed: {resp.status_code} {resp.text[:500]}"
    )

    issue_key = resp.json()["key"]
    yield issue_key

    # Cleanup
    try:
        jira_client.delete(f"/rest/api/{api_version}/issue/{issue_key}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# E2E Tests
# ---------------------------------------------------------------------------


class TestJiraE2E:
    """Live E2E tests against real JIRA Server/DC."""

    def test_list_active_issues(
        self, jira_client: httpx.Client, project_key: str, api_version: str,
        created_issue_key: str,
    ):
        """Scenario 1: List all active issues in a project."""
        jql = f"project = {project_key} ORDER BY created DESC"
        resp = jira_client.get(
            f"/rest/api/{api_version}/search",
            params={"jql": jql, "maxResults": 50, "fields": "key,summary,status,assignee"},
        )
        assert resp.status_code == 200, f"Search failed: {resp.status_code} {resp.text[:300]}"

        data = resp.json()
        assert "issues" in data
        assert "total" in data
        assert data["total"] > 0, "Expected at least 1 issue (the one we created)"

        # Verify the created issue appears in results
        keys = [i["key"] for i in data["issues"]]
        assert created_issue_key in keys, (
            f"Created issue {created_issue_key} not found in search results"
        )

        print(f"\n  Project: {project_key}")
        print(f"  Total issues: {data['total']}")
        for issue in data["issues"][:5]:
            fields = issue["fields"]
            status = fields["status"]["name"]
            assignee = (fields.get("assignee") or {}).get("displayName", "Unassigned")
            print(f"    {issue['key']}  [{status}]  {fields['summary'][:60]}  -> {assignee}")

    def test_get_issue_detail(
        self, jira_client: httpx.Client, api_version: str,
        created_issue_key: str,
    ):
        """Scenario 2: Get a specific issue's full details."""
        resp = jira_client.get(f"/rest/api/{api_version}/issue/{created_issue_key}")
        assert resp.status_code == 200, (
            f"Get issue failed: {resp.status_code} {resp.text[:300]}"
        )

        issue = resp.json()
        fields = issue["fields"]

        assert issue["key"] == created_issue_key
        assert "summary" in fields
        assert "status" in fields
        assert "issuetype" in fields
        assert fields["summary"].startswith("[E2E Test]")

        print(f"\n  Issue:       {issue['key']}")
        print(f"  Summary:     {fields['summary']}")
        print(f"  Type:        {fields['issuetype']['name']}")
        print(f"  Status:      {fields['status']['name']}")
        print(f"  Priority:    {fields.get('priority', {}).get('name', 'N/A')}")
        assignee = (fields.get("assignee") or {}).get("displayName", "Unassigned")
        reporter = (fields.get("reporter") or {}).get("displayName", "N/A")
        print(f"  Assignee:    {assignee}")
        print(f"  Reporter:    {reporter}")
        print(f"  Created:     {fields.get('created', 'N/A')}")
        print(f"  Updated:     {fields.get('updated', 'N/A')}")

    def test_create_issue(
        self, jira_client: httpx.Client, project_key: str, api_version: str,
    ):
        """Scenario 3: Create a new issue and verify it exists, then delete."""
        # Query required fields via createmeta
        fields_payload: dict = {
            "project": {"key": project_key},
            "summary": "[E2E Test] Create-and-delete verification",
            "description": "Created by test_jira_e2e.py test_create_issue. Will be deleted.",
            "issuetype": {"name": "Task"},
        }

        meta_resp = jira_client.get(
            f"/rest/api/{api_version}/issue/createmeta",
            params={"projectKeys": project_key, "expand": "projects.issuetypes.fields"},
        )
        if meta_resp.status_code == 200:
            meta = meta_resp.json()
            for proj in meta.get("projects", []):
                if proj["key"] != project_key:
                    continue
                for itype in proj.get("issuetypes", []):
                    if itype["name"] != "Task":
                        continue
                    for field_key, field_def in itype.get("fields", {}).items():
                        if not field_def.get("required"):
                            continue
                        if field_key in ("project", "summary", "issuetype", "description", "reporter"):
                            continue
                        if field_key == "components":
                            comp_resp = jira_client.get(
                                f"/rest/api/{api_version}/project/{project_key}/components"
                            )
                            if comp_resp.status_code == 200:
                                comps = comp_resp.json()
                                if comps:
                                    fields_payload["components"] = [{"id": comps[0]["id"]}]
                        elif field_key == "priority":
                            fields_payload.setdefault("priority", {"name": "Medium"})

        # Create
        resp = jira_client.post(
            f"/rest/api/{api_version}/issue",
            json={"fields": fields_payload},
        )
        assert resp.status_code in (200, 201), (
            f"Create issue failed: {resp.status_code} {resp.text[:500]}"
        )

        created = resp.json()
        assert "key" in created
        assert "id" in created
        issue_key = created["key"]

        print(f"\n  Created:  {issue_key}")
        print(f"  ID:       {created['id']}")

        # Verify it exists
        verify_resp = jira_client.get(f"/rest/api/{api_version}/issue/{issue_key}")
        assert verify_resp.status_code == 200, f"Created issue not found: {issue_key}"
        assert verify_resp.json()["fields"]["summary"].startswith("[E2E Test]")
        print(f"  Verified: {issue_key} exists with correct summary")

        # Cleanup
        del_resp = jira_client.delete(f"/rest/api/{api_version}/issue/{issue_key}")
        if del_resp.status_code in (200, 204):
            print(f"  Cleanup:  deleted {issue_key}")
        else:
            print(f"  Cleanup:  delete returned {del_resp.status_code} (manual cleanup needed)")
