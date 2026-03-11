"""Approve pending approval items in SmartCMP.

Usage:
  python approve.py <id1> [id2 id3 ...] [--reason "Approval reason"]

Arguments:
  id1, id2, ...  Approval IDs from list_pending.py output
  --reason       Optional approval reason

Examples:
  python approve.py abc123
  python approve.py abc123 --reason "Approved per policy"
  python approve.py abc123 def456 ghi789

Environment:
  CMP_URL    - Base URL, e.g. https://<host>/platform-api
  CMP_COOKIE - Session cookie string

API Reference:
  POST /approval-activity/approve/batch?ids=<id1>,<id2>
  Body: {"reason": "<optional reason>"}
"""
import requests, urllib3, sys, os, json
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = os.environ.get("CMP_URL", "")
COOKIE = os.environ.get("CMP_COOKIE", "")
if not BASE_URL or not COOKIE:
    print("[ERROR] Set environment variables first:")
    print('  $env:CMP_URL = "https://<host>/platform-api"')
    print('  $env:CMP_COOKIE = "<full cookie string>"')
    sys.exit(1)

# ── Parse arguments ───────────────────────────────────────────────────────────
ids = []
reason = ""
i = 1
while i < len(sys.argv):
    arg = sys.argv[i]
    if arg == "--reason" and i + 1 < len(sys.argv):
        reason = sys.argv[i + 1]
        i += 2
    elif not arg.startswith("--"):
        ids.append(arg)
        i += 1
    else:
        i += 1

if not ids:
    print("[ERROR] At least one approval ID is required.")
    print()
    print("Usage: python approve.py <id1> [id2 ...] [--reason \"Reason\"]")
    print()
    print("Get IDs from: python list_pending.py → ##APPROVAL_META##")
    sys.exit(1)

headers = {"Content-Type": "application/json; charset=utf-8", "Cookie": COOKIE}

# ── Approve request ───────────────────────────────────────────────────────────
url = f"{BASE_URL}/approval-activity/approve/batch"
params = {"ids": ",".join(ids)}
body = {"reason": reason} if reason else {}

print(f"Approving {len(ids)} item(s)...")
if reason:
    print(f"Reason: {reason}")
print()

try:
    resp = requests.post(url, headers=headers, params=params, json=body, verify=False, timeout=30)
    resp.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"[ERROR] Request failed: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response: {e.response.text}")
    sys.exit(1)

# ── Handle response ───────────────────────────────────────────────────────────
try:
    result = resp.json()
except:
    result = resp.text

print("[SUCCESS] Approval completed.")
print()

# Show result details if available
if isinstance(result, list):
    for item in result:
        item_id = item.get("id", "N/A")
        status = item.get("status") or item.get("state") or "approved"
        print(f"  ID: {item_id} → {status}")
elif isinstance(result, dict):
    if result.get("success") is not None:
        print(f"  Success: {result.get('success')}")
    if result.get("message"):
        print(f"  Message: {result.get('message')}")
else:
    print(f"  Response: {result}")

print()
print("##APPROVE_RESULT_START##")
print(json.dumps({"approved_ids": ids, "reason": reason, "response": result}, ensure_ascii=False, default=str))
print("##APPROVE_RESULT_END##")
