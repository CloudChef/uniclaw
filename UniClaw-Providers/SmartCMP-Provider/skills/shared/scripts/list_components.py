"""
Query component type information for a given resource type (sourceKey).

Usage:
  python list_components.py <SOURCE_KEY>

Output (printed first):
  ##COMPONENT_META_START## ... ##COMPONENT_META_END##
    JSON object: {sourceKey, typeName (= model.typeName), id, name}
    typeName is used as nodeType for list_resource_pools.py
    and to detect osType ("windows" in typeName.lower() → Windows, else Linux)

Environment:
  CMP_URL    - Base URL, e.g. https://<host>/platform-api
  CMP_COOKIE - Session cookie string
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

if len(sys.argv) < 2:
    print("Usage: python list_components.py <SOURCE_KEY>")
    sys.exit(1)

source_key = sys.argv[1]
headers = {"Cookie": COOKIE}

# ── Query /components ─────────────────────────────────────────────────────────
url = f"{BASE_URL}/components"
try:
    resp = requests.get(url, headers=headers, params={"resourceType": source_key},
                        verify=False, timeout=30)
    resp.raise_for_status()
    data = resp.json()
except requests.exceptions.RequestException as e:
    print(f"[ERROR] Request failed: {e}")
    sys.exit(1)

items = data if isinstance(data, list) else \
        data.get("content", data.get("data", data.get("items", [])))

# Fallback: API returned a single component object directly (has "model" field at root)
if not items and isinstance(data, dict) and "model" in data:
    items = [data]

if not items:
    print(f"[INFO] No component found for sourceKey='{source_key}'.")
    sys.exit(0)

comp      = items[0]
model     = comp.get("model", {})
type_name = model.get("typeName", comp.get("typeName", comp.get("type", "")))
comp_id   = comp.get("id", "N/A")
comp_name = comp.get("nameZh") or comp.get("name", "N/A")

# Structured block FIRST — agent reads this immediately
print("##COMPONENT_META_START##")
print(json.dumps({"sourceKey": source_key, "typeName": type_name,
                  "id": comp_id, "name": comp_name}, ensure_ascii=False))
print("##COMPONENT_META_END##")

# Human-readable summary (after the block, for reference only)
print(f"[INFO] sourceKey={source_key}  typeName={type_name}  id={comp_id}")
