---
name: "approval"
description: "SmartCMP approval management. Trigger when user asks to view pending approvals, approve requests, or reject requests."
---

# approval

Provider skill under `SmartCMP-Provider/skills/approval`.

## Purpose

Manage SmartCMP approval workflows including querying pending approvals, approving requests, and rejecting requests.

## Trigger Conditions

Use this skill when user intent is any of:
- View pending approvals / list approvals / check what needs approval
- Approve a request / approve all / batch approve
- Reject a request / deny request / batch reject

## Script Entry Points

All scripts are in `scripts/`:

- `scripts/list_pending.py` — List pending approval items
- `scripts/approve.py` — Approve one or more requests
- `scripts/reject.py` — Reject one or more requests

## Invocation Guidance

### Query pending approvals

When user says "show me pending approvals" or "what needs my approval":

```bash
python scripts/list_pending.py
```

Output: numbered list of pending items with enhanced details:
- Priority indicator (🔴High/🟡Medium/🟢Low) with intelligent scoring
- Request name, workflow ID, catalog type
- Applicant name and email
- Description/justification (if provided)
- Creation time, update time, and wait duration
- Resource specifications (CPU, memory, storage, tags)
- Cost estimate (if available)
- Current approval step and assigned approver
- Priority factors explaining the score

The `##APPROVAL_META##` block contains structured JSON with full details for programmatic use.

### Approve requests

When user says "approve request #1" or "approve all":

```bash
# Approve single item (ID from list_pending.py output)
python scripts/approve.py <approval_id>

# Approve with reason
python scripts/approve.py <approval_id> --reason "Approved per policy"

# Approve multiple items
python scripts/approve.py <id1> <id2> <id3>
```

### Reject requests

When user says "reject request #1":

```bash
# Reject single item
python scripts/reject.py <approval_id>

# Reject with reason (recommended)
python scripts/reject.py <approval_id> --reason "Budget exceeded"

# Reject multiple items
python scripts/reject.py <id1> <id2> --reason "Not aligned with policy"
```

## Environment Setup

```powershell
$env:CMP_URL = "https://<host>/platform-api"
$env:CMP_COOKIE = '<full cookie string>'
```

## References

- [WORKFLOW.md](references/WORKFLOW.md) — Detailed approval workflow

## Notes

**CRITICAL RULES:**
- **NEVER create temp files** — no `.py`, `.txt`, `.json`. Your context IS your memory.
- **NEVER redirect output** — no `>`, `>>`, `2>&1`. Run scripts directly, read stdout.
- **Always show pending list first** before approve/reject operations.
- **Confirm with user** before batch operations affecting multiple items.

**General:**
- Scripts read SmartCMP connection from environment variables (`CMP_URL`, `CMP_COOKIE`).
- Approval IDs come from `list_pending.py` output's `##APPROVAL_META##` block.
- Default time range is last 30 days; adjustable via `--days` parameter.
