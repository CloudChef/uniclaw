"""
List published service catalogs from SmartCMP.

Usage:
  python list_services.py [KEYWORD]

Output:
  - Numbered list of catalog names (user-visible)
  - ##CATALOG_META_START## ... ##CATALOG_META_END##
      JSON array: [{index, id, name, sourceKey, description}, ...]
      Parse silently — do NOT display to user.

Environment:
  CMP_URL    - Base URL, e.g. https://<host>/platform-api
  CMP_COOKIE - Session cookie string
"""
import requests, urllib3, sys, os, json
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = os.environ.get("CMP_URL", "")
COOKIE = os.environ.get("CMP_COOKIE", "")
if not BASE_URL or not COOKIE:
    print("ERROR: Set environment variables first:")
    print('  $env:CMP_URL = "https://<host>/platform-api"')
    print('  $env:CMP_COOKIE = "<full cookie string>"')
    sys.exit(1)

keyword = sys.argv[1] if len(sys.argv) > 1 else ""
url = f"{BASE_URL}/catalogs/published"
params = {"query": "", "states": "PUBLISHED", "page": 1, "size": 50, "sort": "catalogIndex,asc"}
if keyword:
    params["queryValue"] = keyword
headers = {"Content-Type": "application/json; charset=utf-8", "Cookie": COOKIE}

resp = requests.get(url, headers=headers, params=params, verify=False, timeout=30)
if resp.status_code != 200:
    print(f"HTTP {resp.status_code}: {resp.text}")
    sys.exit(1)

result = resp.json()
items = result.get("content", [])
total = result.get("totalElements", len(items))
print(f"Found {total} published catalog(s):\n")

# ── User-visible list (name only) ─────────────────────────────────────────
for i, c in enumerate(items):
    name = c.get("nameZh") or c.get("name", "N/A")
    print(f"  [{i+1}] {name}")
print()

# ── Machine-readable metadata (agent reads silently, do NOT display to user)
# Contains: id, name, sourceKey, description (from 'instructions' field only)
meta = [
    {
        "index": i + 1,
        "id":    c.get("id", ""),
        "name":  c.get("nameZh") or c.get("name", ""),
        "sourceKey":   c.get("sourceKey", ""),
        "description": (c.get("instructions") or "").strip(),
    }
    for i, c in enumerate(items)
]
print("##CATALOG_META_START##")
print(json.dumps(meta, ensure_ascii=False))
print("##CATALOG_META_END##")
