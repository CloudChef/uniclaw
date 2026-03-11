"""
Submit a service request to SmartCMP.

Usage:
  python submit.py --file <json_file>
  python submit.py --json '<json_string>'

Arguments:
  --file, -f    Path to JSON file containing request body
  --json, -j    JSON string (not recommended in PowerShell due to encoding issues)

Output:
  Request ID and State for each submitted request.

Environment:
  CMP_URL    - Base URL, e.g. https://<host>/platform-api
  CMP_COOKIE - Session cookie string

Example:
  python submit.py --file request_body.json
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

# ── Parse arguments ───────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description='Submit request to SmartCMP')
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--file', '-f', help='Path to JSON file containing request body')
group.add_argument('--json', '-j', help='JSON string (avoid in PowerShell)')
args = parser.parse_args()

# ── Load request body ─────────────────────────────────────────────────────────
try:
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            body = json.load(f)
    else:
        body = json.loads(args.json)
except json.JSONDecodeError as e:
    print(f"[ERROR] Invalid JSON: {e}")
    sys.exit(1)
except FileNotFoundError:
    print(f"[ERROR] File not found: {args.file}")
    sys.exit(1)

# ── Submit request ────────────────────────────────────────────────────────────
url = f"{BASE_URL}/generic-request/submit"
headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Cookie": COOKIE
}

try:
    resp = requests.post(url, headers=headers, json=body, verify=False, timeout=30)
    result = resp.json()
except requests.exceptions.RequestException as e:
    print(f"[ERROR] Request failed: {e}")
    sys.exit(1)
except json.JSONDecodeError:
    print(f"[ERROR] Invalid response: {resp.text}")
    sys.exit(1)

# ── Output result ─────────────────────────────────────────────────────────────
print(f"Status: {resp.status_code}")

if isinstance(result, list):
    for r in result:
        req_id = r.get('id', 'N/A')
        state = r.get('state', 'N/A')
        error = r.get('errorMessage', '')
        print(f"  Request ID: {req_id}")
        print(f"  State: {state}")
        if error:
            print(f"  Error: {error}")
        print()
elif isinstance(result, dict):
    if 'id' in result:
        print(f"  Request ID: {result.get('id', 'N/A')}")
        print(f"  State: {result.get('state', 'N/A')}")
    if 'message' in result or 'error' in result:
        print(f"  Message: {result.get('message', result.get('error', ''))}")
else:
    print(f"  Response: {result}")
