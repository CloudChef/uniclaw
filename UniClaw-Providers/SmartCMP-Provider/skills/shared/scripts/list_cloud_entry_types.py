"""
List all cloud entry types for the current tenant.

Usage:
  python list_cloud_entry_types.py

  No positional arguments required.

Environment:
  CMP_URL    - Base URL, e.g. https://<host>/platform-api
  CMP_COOKIE - Session cookie string (use single quotes in PowerShell)

Output blocks:
  ##CLOUD_ENTRY_TYPES_META_START## ... ##CLOUD_ENTRY_TYPES_META_END##
    JSON array of {id, name, group} for each cloud entry type.
    group values: "PUBLIC_CLOUD" | "PRIVATE_CLOUD"
    Use this block to determine whether a cloudEntryTypeId belongs to
    public cloud or private cloud before querying images.
"""
import requests, urllib3, sys, os, json
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = os.environ.get("CMP_URL", "")
COOKIE   = os.environ.get("CMP_COOKIE", "")
if not BASE_URL or not COOKIE:
    print("ERROR: Set CMP_URL and CMP_COOKIE environment variables first.")
    print('  $env:CMP_URL = "https://<host>/platform-api"')
    print('  $env:CMP_COOKIE = "<full cookie string>"')
    sys.exit(1)

headers = {"Cookie": COOKIE}
url = f"{BASE_URL}/cloudentry-types/list_cloud_entry_types?queryByCurrentTenant"

try:
    resp = requests.get(url, headers=headers, verify=False, timeout=30)
    resp.raise_for_status()
    data = resp.json()
except requests.exceptions.RequestException as e:
    print(f"[ERROR] Request failed: {e}")
    sys.exit(1)

items = data if isinstance(data, list) else data.get("content", data.get("data", []))

if not items:
    print("[INFO] No cloud entry types found.")
    sys.exit(0)

print(f"\nFound {len(items)} cloud entry type(s):\n")
for i, ct in enumerate(items, 1):
    name  = ct.get("nameZh") or ct.get("name", "Unknown")
    cid   = ct.get("id", "N/A")
    group = ct.get("group", "")
    print(f"  [{i}] {name}  [ID: {cid}]  [Group: {group}]")

print()

# Machine-readable META block — used by agent to check PUBLIC/PRIVATE group
meta = [
    {
        "id":    ct.get("id"),
        "name":  ct.get("nameZh") or ct.get("name", ""),
        "group": ct.get("group", ""),
    }
    for ct in items
]
print("##CLOUD_ENTRY_TYPES_META_START##")
print(json.dumps(meta, ensure_ascii=False))
print("##CLOUD_ENTRY_TYPES_META_END##")
