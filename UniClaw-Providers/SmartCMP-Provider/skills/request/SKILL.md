---
name: request
description: >
  Submit cloud resource or application provisioning requests via SmartCMP.
  Includes interactive parameter selection: query published catalogs, business
  groups, applications, resource pools, OS templates, and images before submitting.
  Use when the user says "我要申请", "申请资源", "申请云主机", "provision", or wants
  to create VMs, deploy cloud resources, or provision any catalog item on SmartCMP.
  Resource requests are NOT limited to VMs — they include all catalog types.
  Supports multi-cloud (Azure, AWS, Aliyun, OpenStack, vSphere, FusionCompute).
compatibility: Python 3 with requests library. Network access to SmartCMP platform.
metadata:
  author: smartcmp
  version: "2.1"
---

# Submit Provision Request

## Setup (once per session)

```powershell
$env:CMP_URL = "https://<host>/platform-api"
$env:CMP_COOKIE = '<full cookie string>'   # MUST use single quotes (cookie may contain semicolons)
```

---

## EXECUTION RULES

1. **Atomic**: ONE user-visible action per turn. Silent pre-fetches (Step 1b, Step 3f①) do NOT count as a turn.
2. **NEVER run multiple user-visible scripts in the same turn.**
3. **NEVER run a script speculatively** — only when the step explicitly requires it.
4. `[optional]` params with `list:` are **never auto-fetched**. Skip unless user asks.
5. **STOP and wait** after every user-facing output or question.
6. **NEVER create temp `.py` files** or use `python -c` for tasks covered by standard scripts.
7. **NEVER pipe, redirect, or filter script output** (no `|`, `>`, `2>&1`, `Select-String`, `Select-Object`, etc.).
   Scripts print `##BLOCK_START##...##BLOCK_END##` as the **very first lines** of output. Read them directly from the terminal — no file capture needed.
8. **`list_components.py` is called EXACTLY ONCE** — silently in Step 1b. NEVER call it again in Steps 2-5.

---

## Script → datasource mapping

`list:X` in a catalog description → run `../shared/scripts/list_X.py`

| When | Script | Args |
|------|--------|------|
| Step 1a | `list_services.py` | *(none)* |
| Step 1b *(silent, no STOP)* | `list_components.py` | `<sourceKey>` |
| `list:business_groups` | `list_business_groups.py` | `<catalogId>` |
| `list:applications` *(required only)* | `list_applications.py` | `<bgId>` |
| `list:resource_pools` or param `resourceBundleId/Name` | `list_resource_pools.py` | `<bgId> <sourceKey> <nodeType>` |
| `list:os_templates` or param `logicTemplateName/Id` *(VM only)* | `list_os_templates.py` | `<osType> <rbId>` |
| Step 3f① *(silent, no STOP)* | `list_cloud_entry_types.py` | *(none)* |
| `list:images` or param `imageId/imageName` | `list_images.py` | `<rbId> <ltId> <cloudEntryTypeId>` |

---

## Full workflow

### Step 1a — List catalogs

```
ACTION: python ../shared/scripts/list_services.py
SHOW:   numbered list of catalog names (clean, no raw IDs)
PARSE:  ##CATALOG_META_START## silently → cache {index, id, sourceKey, description} per catalog
ASK:    "请告诉我您想申请哪个服务？"
STOP → wait for user selection
```

### Step 1b — Silently fetch component type *(runs in the same turn as user's Step 1a reply — NO STOP)*

```
LOOKUP: catalogId, sourceKey, description from cached ##CATALOG_META## (NO API call)
ACTION: python ../shared/scripts/list_components.py <sourceKey>
PARSE:  ##COMPONENT_META_START## silently
RECORD (FINAL — never re-derive in any later step):
  typeName = ##COMPONENT_META##["typeName"]   ← model.typeName ("" if not found)
  nodeType = typeName                          ← 3rd arg for list_resource_pools (Step 3d)
  osType   = "Windows" if "windows" in typeName.lower() else "Linux"
                                               ← 1st arg for list_os_templates (Step 3e)
DO NOT show output. Proceed immediately to Step 2 in this same turn.
```

---

### Step 2 — Show parameter summary *(NO API call, NO file read)*

```
SOURCE: description field from ##CATALOG_META## (already cached in Step 1a — do NOT read any files)

IF description is empty or missing:
  → STOP and show:
    "⚠️ 该服务卡片尚未配置参数使用说明

    当前服务【<name>】缺少必要的参数定义（instructions 字段），无法自动收集申请参数。

    建议操作：
    1. 请联系平台管理员为该服务卡片配置 instructions 字段
    2. 配置完成后重新发起申请流程

    如您已知悉该服务所需参数，可直接告诉我具体申请内容，我将尝试手动构建请求。"
  → Do NOT proceed to Step 3.

OTHERWISE:
SHOW:
  服务名称: <name>
  必填参数:
    - 参数显示名 (paramName) — 默认: xxx   [无需输入]
    - 参数显示名 (paramName) — 需要选择/输入
  可选参数: [...]
STOP → do NOT run any datasource script yet
```

---

### Step 3 — Collect required params *(in order: 3a → 3b → 3c → 3d → 3e → 3f)*

> **CACHED VALUES ARE FINAL**: `osType` (Step 1b), `nodeType` (Step 1b), `cloudEntryTypeId` (Step 3d).
> NEVER re-derive, re-infer, or call any script again to obtain these values.
> If a cached value is missing → STOP and report to user. Do NOT guess.

#### 3a — Plain text required params

```
ASK (all in one message):
  请提供以下必填信息：
  1. 资源名称 (name)：
  2. ...
STOP
```

#### 3b — Business group

```
list:business_groups → python ../shared/scripts/list_business_groups.py <catalogId>
SHOW: numbered list
ASK:  "请选择业务组："
STOP → RECORD: businessGroupId, businessGroupName
```

#### 3c — Application *(only if `list:applications` in `[required]`)*

```
list:applications → python ../shared/scripts/list_applications.py <businessGroupId>
SHOW: numbered list
ASK:  "请选择应用："
STOP → RECORD: projectId, projectName
```

> Skip if `list:applications` is in `[optional]` — never auto-run.

#### 3d — Resource pool

```
list:resource_pools → python ../shared/scripts/list_resource_pools.py <bgId> <sourceKey> <nodeType>
# nodeType: ALWAYS pass cached value from Step 1b. Pass "" if empty — NEVER omit 3rd arg.
SHOW: numbered list (name + cloud type + cloudEntryTypeId)
ASK:  "请选择资源池："
STOP → MANDATORY: parse ##RESOURCE_POOL_META_START## block
         find entry where index == user's selection
         RECORD: resourceBundleId, resourceBundleName, cloudEntryTypeId
         ⚠ cloudEntryTypeId MUST be recorded. If empty → STOP: "资源池缺少 cloudEntryTypeId，无法继续。"
```

> Trigger: `list:resource_pools` in `[required]`, OR param name is `resourceBundleId/Name`.
> Always query dynamically even if description shows `default:xxx`.

#### 3e — OS template *(VM only)*

> Trigger: param `logicTemplateName/Id` in `[required]` with no default, AND `sourceKey.lower()` contains `"machine"`.

```
# osType is ALREADY cached in Step 1b — DO NOT re-derive, DO NOT call list_components again
python ../shared/scripts/list_os_templates.py <osType> <resourceBundleId>
SHOW: numbered list (nameZh / name + version)
ASK:  "请选择操作系统模板："
STOP → RECORD: logicTemplateName, logicTemplateId
```

#### 3f — Image *(private cloud only)*

> Trigger: param `imageId/imageName` in `[required]` with no default.
> `cloudEntryTypeId` is ALREADY cached from Step 3d — DO NOT infer or guess.

```
① python ../shared/scripts/list_cloud_entry_types.py   ← silent, no STOP
   PARSE: ##CLOUD_ENTRY_TYPES_META_START##
   → group == "PRIVATE_CLOUD" → continue
   → group == "PUBLIC_CLOUD"  → tell user: "公有云镜像暂不支持，请手动输入镜像ID。" STOP.

② python ../shared/scripts/list_images.py <resourceBundleId> <logicTemplateId> <cloudEntryTypeId>
SHOW: numbered list of images
ASK:  "请选择镜像："
STOP → RECORD: imageId, imageName
```

---

**Catalog description format:**

```
[required]
- Display Label | paramName | default:xxx    ← use default silently (EXCEPT resourceBundleName/Id)
- Display Label | paramName | list:X         ← run list_X.py
- Display Label | paramName                  ← ask user

[optional]
- Display Label | paramName | list:X         ← SKIP (do not auto-run)
- Display Label | paramName | default:xxx    ← include in body silently
- Display Label | paramName                  ← skip unless user asks
```

> ALL `default:xxx` values from both `[required]` and `[optional]` **MUST** be included in the final body.

---

### Step 4 — Build and confirm request body

1. Build complete JSON request body.
2. **Always output BOTH** in the same message (do NOT wait to be asked):
   - Human-readable summary table (参数名 + 值)
   - Complete raw JSON in a `json` code block
3. STOP → wait for user confirmation.

See [parameter placement](references/PARAMS.md) and [examples](references/EXAMPLES.md).

---

### Step 5 — Submit

```python
import json, requests, urllib3, os
urllib3.disable_warnings()
url = os.environ['CMP_URL'] + '/generic-request/submit'
headers = {'Content-Type': 'application/json; charset=utf-8', 'Cookie': os.environ['CMP_COOKIE']}
body = { ... }  # assembled dict
resp = requests.post(url, headers=headers, json=body, verify=False, timeout=30)
result = resp.json()
print('Status:', resp.status_code)
if isinstance(result, list):
    for r in result:
        print('Request ID:', r.get('id'), '| State:', r.get('state'))
```

> **NEVER** pass JSON as a command-line string in PowerShell — it corrupts Unicode. Always use inline Python.

Output: status code + Request ID + State + any error message.
