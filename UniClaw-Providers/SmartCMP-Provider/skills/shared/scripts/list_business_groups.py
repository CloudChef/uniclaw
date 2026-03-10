"""
List available business groups for a catalog.

Usage:
  python list_business_groups.py <CATALOG_ID>

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
    print("Usage: python scripts/datasource/list_business_groups.py <CATALOG_ID>")
    sys.exit(1)

CATALOG_ID = sys.argv[1]
url = f"{BASE_URL}/catalogs/{CATALOG_ID}/available-bgs"
headers = {"Content-Type": "application/json; charset=utf-8", "Cookie": COOKIE}

resp = requests.get(url, headers=headers, verify=False, timeout=30)
if resp.status_code != 200:
    print(f"HTTP {resp.status_code}: {resp.text}")
    sys.exit(1)

result = resp.json()
items = result if isinstance(result, list) else result.get("content", [])
print(f"Found {len(items)} business group(s):\n")
for i, bg in enumerate(items):
    name = bg.get("name", "N/A")
    bid = bg.get("id", "N/A")
    print(f"  [{i+1}] {name} (id: {bid})")
