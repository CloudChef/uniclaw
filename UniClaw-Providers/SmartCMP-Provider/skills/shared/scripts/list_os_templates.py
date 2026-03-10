"""
List available OS templates (logic templates) for a given resource bundle.

Usage:
  python list_os_templates.py <OS_TYPE> <RESOURCE_BUNDLE_ID>

  OS_TYPE            - "Linux" or "Windows" (caller determines this)
  RESOURCE_BUNDLE_ID - resource bundle ID from list_resource_pools.py

Environment:
  CMP_URL    - Base URL, e.g. https://<host>/platform-api
  CMP_COOKIE - Session cookie string
"""
import requests, urllib3, sys, os
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = os.environ.get("CMP_URL", "")
COOKIE   = os.environ.get("CMP_COOKIE", "")
if not BASE_URL or not COOKIE:
    print("ERROR: Set CMP_URL and CMP_COOKIE environment variables first.")
    print('  $env:CMP_URL = "https://<host>/platform-api"')
    print('  $env:CMP_COOKIE = "<full cookie string>"')
    sys.exit(1)

if len(sys.argv) < 3:
    print("Usage: python list_os_templates.py <OS_TYPE> <RESOURCE_BUNDLE_ID>")
    print("  OS_TYPE: Linux or Windows")
    sys.exit(1)

os_type            = sys.argv[1]
resource_bundle_id = sys.argv[2]
headers = {"Cookie": COOKIE}

# ── Query logic templates ─────────────────────────────────────────────────────
url = f"{BASE_URL}/logic-templates/search?expand&osType={os_type}&resourceBundleId={resource_bundle_id}"
try:
    resp = requests.get(url, headers=headers, verify=False, timeout=30)
    resp.raise_for_status()
    data = resp.json()
except requests.exceptions.RequestException as e:
    print(f"[ERROR] Request failed: {e}")
    sys.exit(1)

templates = data if isinstance(data, list) else data.get("content", data.get("data", []))

print(f"\nOS Templates  (osType={os_type}, resourceBundleId={resource_bundle_id})")
print("=" * 60)

if not templates:
    print("[INFO] No OS templates found.")
    sys.exit(0)

for i, t in enumerate(templates, 1):
    name    = t.get("nameZh") or t.get("name") or t.get("templateName", "Unknown")
    eng     = t.get("name", "")
    tid     = t.get("id", "N/A")
    os_ver  = t.get("osVersion") or t.get("version", "")
    display = f"  [{i}] {name}"
    if eng and eng != name:
        display += f"  ({eng})"
    if os_ver:
        display += f"  v{os_ver}"
    display += f"  [ID: {tid}]"
    print(display)

print()
