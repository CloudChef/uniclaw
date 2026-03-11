"""
List available resource pools for a given business group.

Usage (positional - preferred):
  python list_resource_pools.py <BUSINESS_GROUP_ID> <SOURCE_KEY> <NODE_TYPE>

Usage (named - also supported):
  python list_resource_pools.py --business-group-id <ID> --source-key <KEY> [--node-type <TYPE>]

Arguments:
  BUSINESS_GROUP_ID - from list_business_groups.py output
  SOURCE_KEY        - from list_services.py output (the sourceKey field)
  NODE_TYPE         - from list_components.py output (the typeName field).
                      Pass empty string "" or omit if not available.

Output blocks:
  ##RESOURCE_POOL_META_START## ... ##RESOURCE_POOL_META_END##
    JSON array of {index, id, name, cloudEntryTypeId} for each pool.
    Use this block to look up cloudEntryTypeId by the pool number the user selected.

  ##RESOURCE_POOL_RAW_START## ... ##RESOURCE_POOL_RAW_END##
    Full raw JSON array. Use only when extra fields beyond META are needed.

Environment:
  CMP_URL    - Base URL, e.g. https://<host>/platform-api
  CMP_COOKIE - Session cookie string
"""
import requests, urllib3, sys, os, json, argparse
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = os.environ.get("CMP_URL", "")
COOKIE   = os.environ.get("CMP_COOKIE", "")
if not BASE_URL or not COOKIE:
    print("ERROR: Set environment variables first:")
    print('  $env:CMP_URL = "https://<host>/platform-api"')
    print('  $env:CMP_COOKIE = "<full cookie string>"')
    sys.exit(1)

# ── Parse arguments (support both positional and named) ──────────────────────
def parse_args():
    # Check if using named args (any arg starts with --)
    has_named = any(arg.startswith('--') for arg in sys.argv[1:])
    
    if has_named:
        parser = argparse.ArgumentParser(description='List resource pools')
        parser.add_argument('--business-group-id', '-b', required=True, help='Business group ID')
        parser.add_argument('--source-key', '-s', required=True, help='Source key (componentType)')
        parser.add_argument('--node-type', '-n', default='', help='Node type (optional)')
        args = parser.parse_args()
        return args.business_group_id, args.source_key, args.node_type.strip()
    else:
        # Positional arguments
        if len(sys.argv) < 3:
            print("Usage: python list_resource_pools.py <BUSINESS_GROUP_ID> <SOURCE_KEY> [NODE_TYPE]")
            print("   or: python list_resource_pools.py --business-group-id <ID> --source-key <KEY> [--node-type <TYPE>]")
            sys.exit(1)
        bg_id      = sys.argv[1]
        source_key = sys.argv[2]
        node_type  = sys.argv[3].strip() if len(sys.argv) > 3 else ""
        return bg_id, source_key, node_type

bg_id, source_key, node_type = parse_args()
headers = {"Content-Type": "application/json; charset=utf-8", "Cookie": COOKIE}

# ── Query resource pools ──────────────────────────────────────────────────────
url = f"{BASE_URL}/resource-bundles"
params = {
    "businessGroupId":  bg_id,
    "componentType":    source_key,
    "cloudEntryTypeId": "",
    "enabled":          "true",
    "readOnly":         "false",
    "strategy":         "RB_POLICY_STATIC",
}
if node_type:
    params["nodeType"] = node_type

try:
    resp = requests.get(url, headers=headers, params=params, verify=False, timeout=30)
    resp.raise_for_status()
    data = resp.json()
except requests.exceptions.RequestException as e:
    print(f"[ERROR] Request failed: {e}")
    sys.exit(1)

def _extract_list(d):
    if isinstance(d, list):
        return d
    for key in ("content", "data", "items", "result"):
        if isinstance(d.get(key), list):
            return d[key]
    return []

items = _extract_list(data) if isinstance(data, dict) else (data if isinstance(data, list) else [])

if not items:
    print("\nNo resource pools found for this business group.")
    sys.exit(0)

print(f"\nFound {len(items)} resource pool(s):\n")
for i, rb in enumerate(items):
    name                = rb.get("name", "N/A")
    rid                 = rb.get("id", "N/A")
    cloud_type          = rb.get("cloudEntryType", rb.get("cloudEntryTypeName", rb.get("type", "")))
    cloud_entry_type_id = rb.get("cloudEntryTypeId", "")
    print(f"  [{i+1}] {name}")
    print(f"      ID: {rid}")
    if cloud_type:
        print(f"      Cloud Type: {cloud_type}")
    if cloud_entry_type_id:
        print(f"      CloudEntryTypeId: {cloud_entry_type_id}")
    print()

# ── META block FIRST (agent reads immediately) ────────────────────────────────
meta = [
    {
        "index":            i + 1,
        "id":               rb.get("id", ""),
        "name":             rb.get("name", ""),
        "cloudEntryTypeId": rb.get("cloudEntryTypeId", ""),
    }
    for i, rb in enumerate(items)
]
print("##RESOURCE_POOL_META_START##")
print(json.dumps(meta, ensure_ascii=False))
print("##RESOURCE_POOL_META_END##")

# ── RAW block (use only when extra fields beyond META are needed) ─────────────
print("##RESOURCE_POOL_RAW_START##")
print(json.dumps(items, ensure_ascii=False))
print("##RESOURCE_POOL_RAW_END##")
