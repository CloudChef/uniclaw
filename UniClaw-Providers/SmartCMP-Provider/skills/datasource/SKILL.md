---
name: datasource
description: >
  Query and browse SmartCMP reference data as standalone read-only operations.
  Use when the user wants to explore or look up SmartCMP data WITHOUT submitting
  a request — e.g. "查看服务目录", "列出业务组", "有哪些资源池", "show catalogs",
  "list business groups for catalog X", "what resource pools are available",
  "查询应用系统". All operations are read-only. Does NOT submit any request.
  For resource provisioning, use the request skill instead.
compatibility: Python 3 with requests library. Network access to SmartCMP platform.
metadata:
  author: smartcmp
  version: "1.0"
---

# Query SmartCMP Datasource

## Setup (once per session)

```powershell
$env:CMP_URL = "https://<host>/platform-api"
$env:CMP_COOKIE = '<full cookie string>'   # MUST use single quotes (cookie may contain semicolons)
```

All scripts are **read-only** — no data is created or modified.

> Shared scripts live at `../shared/scripts/` (used by multiple skills).

---

## RULES (agent must follow strictly)

1. **Run scripts in sequence** — each script's output is input for the next. Never skip steps.
2. **STOP on any error** — if a script exits with an error or prints `[ERROR]`, stop immediately and report the exact error message to the user. Do NOT self-debug (no echo, Write-Host, Test-NetConnection, or other diagnostic commands).
3. **Never retry blindly** — if a script fails, ask the user to fix the environment (cookie, URL, network) before retrying.
4. **Cookie refresh** — if the response is `401` or contains `token expired`, tell the user: "Cookie 已过期，请重新登录 SmartCMP 并更新 `$env:CMP_COOKIE`". Do not attempt any further script calls.
5. **Network error** — if connection times out, tell the user: "无法连接到 CMP 服务器，请确认网络访问 `$env:CMP_URL` 是否正常". Do not attempt any further script calls.

---

## Scripts

### 1. List service catalogs

```powershell
python ../shared/scripts/list_services.py
python ../shared/scripts/list_services.py <KEYWORD>   # filter by name
```

Output: numbered list of catalog **names only** (user-visible). Catalog `id`, `sourceKey`, and `description` are in the `##CATALOG_META##` block — parse silently, do NOT display to user.

---

### 2. List business groups

```powershell
python ../shared/scripts/list_business_groups.py <CATALOG_ID>
```

Output: numbered list of business groups available for the given catalog.

**When to use**: user asks "这个服务有哪些业务组" / "list BGs for catalog X".

---

### 3. Get component type (required before resource pools)

```powershell
python ../shared/scripts/list_components.py <SOURCE_KEY>
```

- `SOURCE_KEY` — from `list_services.py` output (the `sourceKey` field)

Output: `##COMPONENT_META##` block (`typeName` = `model.typeName` from API, id, name) for quick access; `##COMPONENT_RAW##` block (full JSON array) for any additional fields.

**When to use**: always run this before step 4 (resource pools) or before OS template queries.

---

### 4. List resource pools

```powershell
python ../shared/scripts/list_resource_pools.py <BUSINESS_GROUP_ID> <SOURCE_KEY> <NODE_TYPE>
```

- `BUSINESS_GROUP_ID` — from `list_business_groups.py`
- `SOURCE_KEY` — from `list_services.py` output
- `NODE_TYPE` — `typeName` from `list_components.py` output.
  **Always pass this argument.** Use `""` (empty string) if typeName is not found — do NOT omit it.

Output: numbered list of resource pools (name + ID + cloud type + cloudEntryTypeId).
`##RESOURCE_POOL_META##` block: compact `[{index, id, name, cloudEntryTypeId}]` — read this to extract cloudEntryTypeId for the selected pool.
`##RESOURCE_POOL_RAW##` block: full JSON for any additional fields.

**When to use**: user asks "这个业务组下有哪些资源池" / "list resource pools".

---

### 5. List applications

```powershell
python ../shared/scripts/list_applications.py <BUSINESS_GROUP_ID>
```

Output: numbered list of applications/projects for the given business group.

**When to use**: user asks "有哪些应用系统" / "list applications in BG X".

---

### 6. List OS templates (VM only)

**Prerequisites**: must have `sourceKey` (from step 1), `resourceBundleId` (from step 4), and `typeName` (from step 3).

**Agent pre-flight (do before calling the script):**

```
① Check: sourceKey.lower() contains "machine"?
   → NO  → Tell user: "该服务类型不是虚拟机，不支持操作系统模板查询。" STOP.
   → YES → continue

② Read typeName from list_components.py output (already run in step 3).
   → typeName.lower() contains "windows" → osType = Windows
   → otherwise                            → osType = Linux
```

**Then call the script:**

```powershell
python ../shared/scripts/list_os_templates.py <OS_TYPE> <RESOURCE_BUNDLE_ID>
# OS_TYPE: Linux or Windows (determined above)
# RESOURCE_BUNDLE_ID: from list_resource_pools.py output
```

Output: numbered list of OS templates (nameZh / name + version + ID).

**When to use**: user asks "有哪些操作系统" / "list OS templates for resource bundle X".

---

### 7. List cloud entry types

```powershell
python ../shared/scripts/list_cloud_entry_types.py
```

- No positional arguments required.

Output: numbered list of cloud entry types (name + ID + group) and `##CLOUD_ENTRY_TYPES_META##` block.
`group` values: `PUBLIC_CLOUD` | `PRIVATE_CLOUD`

**When to use**: before querying images, to determine whether the selected resource pool belongs to public or private cloud. Match `cloudEntryTypeId` (from step 4 `##RESOURCE_POOL_META##`) against this list.

---

### 8. List images (private cloud only)

**Prerequisites**: must have `resourceBundleId` (step 4), `logicTemplateId` (step 6), and `cloudEntryTypeId` (from step 4 `##RESOURCE_POOL_RAW##`).

**Agent pre-flight:**

```
① Run list_cloud_entry_types.py silently → parse ##CLOUD_ENTRY_TYPES_META## block
② Match cloudEntryTypeId from step 4 → check group:
   → PRIVATE_CLOUD → continue
   → PUBLIC_CLOUD  → Tell user: "公有云镜像查询暂不支持，请手动输入镜像ID。" STOP.
```

**Then call the script:**

```powershell
python ../shared/scripts/list_images.py <RESOURCE_BUNDLE_ID> <LOGIC_TEMPLATE_ID> <CLOUD_ENTRY_TYPE_ID>
# RESOURCE_BUNDLE_ID:  from list_resource_pools.py
# LOGIC_TEMPLATE_ID:   from list_os_templates.py (the [ID: ...] value)
# CLOUD_ENTRY_TYPE_ID: from list_resource_pools.py ##RESOURCE_POOL_META## (field: cloudEntryTypeId)
```

cloudResourceType is constructed internally:
- contains `"generic-cloud"` → `yacmp:cloudentry:type:generic-cloud::images`
- otherwise → `<CLOUD_ENTRY_TYPE_ID>::images`

Output: numbered list of images (name + ID).

**When to use**: user asks "有哪些镜像" / "list images for resource bundle X" (private cloud only).

---

## Typical standalone queries

| User intent | Action |
|-------------|--------|
| "看看有哪些服务目录" | `list_services.py` |
| "XX服务有哪些业务组" | `list_services.py` → `list_business_groups.py <catalogId>` |
| "XX业务组有哪些应用" | `list_applications.py <bgId>` |
| "XX业务组有哪些资源池" | `list_components.py <sourceKey>` → 取 typeName（找不到则空）→ `list_resource_pools.py <bgId> <sourceKey> <nodeType>` |
| "有哪些操作系统 / OS 模板" | 需要 sourceKey+resourceBundleId+typeName → agent pre-flight → `list_os_templates.py <osType> <rbId>` |
| "有哪些镜像" | 需要 resourceBundleId+logicTemplateId+cloudEntryTypeId → `list_cloud_entry_types.py`（静默）→ PRIVATE_CLOUD → `list_images.py <rbId> <ltId> <cloudEntryTypeId>` |

> Scripts are **shared** with the request skill. Running them here has no side effects.
