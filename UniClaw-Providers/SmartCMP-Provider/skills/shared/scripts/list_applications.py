"""
List applications/projects for a business group.

Usage:
  python list_applications.py <BG_ID> [KEYWORD]

Environment:
  CMP_URL    - Base URL, e.g. https://<host>/platform-api
  CMP_COOKIE - Session cookie string
"""
import requests, urllib3, sys, os
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = os.environ.get("CMP_URL", "")
COOKIE = os.environ.get("CMP_COOKIE", "")
if not BASE_URL or not COOKIE:
    print("ERROR: Set CMP_URL and CMP_COOKIE environment variables first.")
    sys.exit(1)
if len(sys.argv) < 2:
    print("Usage: python scripts/datasource/list_applications.py <BG_ID> [KEYWORD]")
    sys.exit(1)

BG_ID = sys.argv[1]
keyword = sys.argv[2] if len(sys.argv) > 2 else ""
url = f"{BASE_URL}/groups"
params = {"query": "", "topGroup": "true", "businessGroupIds": BG_ID, "page": 1, "size": 50, "sort": "name,asc"}
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
print(f"Found {total} application(s):\n")
for i, g in enumerate(items):
    name = g.get("name", "N/A")
    gid = g.get("id", "N/A")
    desc = g.get("description", "")
    print(f"  [{i+1}] {name} (id: {gid})")
    if desc:
        print(f"      Description: {desc[:80]}")
