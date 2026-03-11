# Approval Workflow Reference

Detailed workflow for managing SmartCMP approvals.

---

## Setup (once per session)

```powershell
$env:CMP_URL = "https://<host>/platform-api"
$env:CMP_COOKIE = '<full cookie string>'   # MUST use single quotes
```

---

## Execution Rules

1. **Always list first** — Run `list_pending.py` before approve/reject operations.
2. **Confirm batch operations** — Ask user before approving/rejecting multiple items.
3. **NEVER create temp files** — Your context IS your memory.
4. **NEVER redirect output** — Run scripts directly, read stdout.
5. **Parse META blocks silently** — Do NOT display raw JSON to user.

---

## Full Workflow

### Step 1 — List pending approvals

```
ACTION: python scripts/list_pending.py
SHOW:   numbered list of pending items
PARSE:  ##APPROVAL_META_START## silently → cache {index, id, name, requester}
ASK:    "Would you like to approve or reject any of these?"
STOP → wait for user selection
```

**Optional filters:**
```bash
# Query last 7 days only
python scripts/list_pending.py --days 7
```

---

### Step 2a — Approve (single item)

When user says "approve #1" or "approve the first one":

```
LOOKUP: id from cached ##APPROVAL_META## by index
ACTION: python scripts/approve.py <id>
SHOW:   "[SUCCESS] Approval completed."
```

**With reason:**
```bash
python scripts/approve.py <id> --reason "Approved per policy"
```

---

### Step 2b — Approve (multiple items)

When user says "approve all" or "approve #1, #2, #3":

```
LOOKUP: ids from cached ##APPROVAL_META##
CONFIRM: "You are about to approve N items. Proceed? (yes/no)"
STOP → wait for confirmation
ACTION: python scripts/approve.py <id1> <id2> <id3>
SHOW:   "[SUCCESS] Approval completed."
```

---

### Step 3a — Reject (single item)

When user says "reject #2":

```
LOOKUP: id from cached ##APPROVAL_META## by index
ASK:    "Would you like to provide a rejection reason?"
STOP → wait for user input (optional)
ACTION: python scripts/reject.py <id> [--reason "..."]
SHOW:   "[SUCCESS] Rejection completed."
```

---

### Step 3b — Reject (multiple items)

When user says "reject all" or "reject #1 and #2":

```
LOOKUP: ids from cached ##APPROVAL_META##
CONFIRM: "You are about to reject N items. Proceed? (yes/no)"
STOP → wait for confirmation
ASK:    "Would you like to provide a rejection reason?"
STOP → wait for user input (optional)
ACTION: python scripts/reject.py <id1> <id2> [--reason "..."]
SHOW:   "[SUCCESS] Rejection completed."
```

---

## Script Reference

| Script | Purpose | Arguments |
|--------|---------|-----------|
| `list_pending.py` | List pending approvals | `[--days N]` |
| `approve.py` | Approve items | `<id1> [id2...] [--reason "..."]` |
| `reject.py` | Reject items | `<id1> [id2...] [--reason "..."]` |

---

## API Reference

### List pending approvals
```
GET /generic-request/current-activity-approval
    ?page=1&size=50&stage=pending&sort=updatedDate,desc
    &startAtMin=<timestamp>&startAtMax=<timestamp>
    &rangeField=updatedDate&states=
```

### Approve batch
```
POST /approval-activity/approve/batch?ids=<id1>,<id2>
Body: {"reason": "<optional>"}
```

### Reject batch
```
POST /approval-activity/reject/batch?ids=<id1>,<id2>
Body: {"reason": "<optional>"}
```

---

## Error Handling

| Error | Action |
|-------|--------|
| `401 Unauthorized` | Cookie expired → ask user to re-login |
| `404 Not Found` | Invalid approval ID → re-run list_pending.py |
| `400 Bad Request` | Check API response for details |
| Network timeout | Retry or check connectivity |
