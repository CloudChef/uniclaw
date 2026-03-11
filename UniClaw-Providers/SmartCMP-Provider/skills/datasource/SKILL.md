---
name: "datasource"
description: "Query SmartCMP reference data (read-only). Trigger when user asks to view catalogs, list business groups, check resource pools, show applications. Does NOT submit requests."
---

# datasource

Provider skill under `SmartCMP-Provider/skills/datasource`.

## Purpose

Query and browse SmartCMP reference data as standalone read-only operations. Use when the user wants to explore or look up data WITHOUT submitting a request.

## Trigger Conditions

Use this skill when user intent is any of:
- View/show catalogs
- List business groups
- Check resource pools
- List applications
- List OS templates
- List images

**NOT for**: resource provisioning (use `request` skill instead)

## Script Entry Points

All scripts are in `../shared/scripts/` (shared with request skill):

- `list_services.py` — List published service catalogs
- `list_business_groups.py` — List business groups for a catalog
- `list_components.py` — Get component type information
- `list_resource_pools.py` — List resource pools
- `list_applications.py` — List applications
- `list_os_templates.py` — List OS templates (VM only)
- `list_cloud_entry_types.py` — Get cloud entry types
- `list_images.py` — List images (private cloud only)

## Invocation Guidance

When user asks "show available catalogs":

```bash
python ../shared/scripts/list_services.py
```

When user asks "list business groups for Linux VM":

```bash
# First get catalog ID from list_services.py output
python ../shared/scripts/list_business_groups.py <catalogId>
```

When user asks "what resource pools are available":

```bash
# Need: bgId, sourceKey, nodeType (from list_components.py)
python ../shared/scripts/list_resource_pools.py <bgId> <sourceKey> <nodeType>
```

## Environment Setup

```powershell
$env:CMP_URL = "https://<host>/platform-api"
$env:CMP_COOKIE = '<full cookie string>'
```

## References

- [WORKFLOW.md](references/WORKFLOW.md) — Detailed script usage and query flows

## Notes

- All operations are **read-only** — no data is created or modified.
- Scripts are shared with the `request` skill.
- On error (`[ERROR]`), report to user immediately; do NOT self-debug.
- On `401` / token expired, ask user to refresh cookie.
