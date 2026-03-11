# Request Workflow Reference

Detailed step-by-step workflow for submitting provision requests.

---

## Setup (once per session)

```powershell
$env:CMP_URL = "https://<host>/platform-api"
$env:CMP_COOKIE = '<full cookie string>'   # MUST use single quotes
```

---

## Execution Rules

1. **Atomic**: ONE user-visible action per turn. Silent pre-fetches do NOT count.
2. **NEVER run multiple user-visible scripts in the same turn.**
3. **NEVER run a script speculatively** — only when explicitly required.
4. `[optional]` params with `list:` are **never auto-fetched**.
5. **STOP and wait** after every user-facing output or question.
6. **NEVER create temp `.py` files** or use `python -c` for covered tasks.
7. **NEVER pipe, redirect, or filter script output** (no `|`, `>`, `2>&1`, `Select-String`).
8. **`list_components.py` is called EXACTLY ONCE** — silently in Step 1b.

---

## Full Workflow

### Step 1a — List catalogs

```
ACTION: python ../shared/scripts/list_services.py
SHOW:   numbered list of catalog names
PARSE:  ##CATALOG_META_START## silently → cache {index, id, sourceKey, description}
ASK:    "请告诉我您想申请哪个服务？"
STOP → wait for user selection
```

### Step 1b — Silently fetch component type *(same turn as user reply — NO STOP)*

```
LOOKUP: catalogId, sourceKey, description from cached ##CATALOG_META##
ACTION: python ../shared/scripts/list_components.py <sourceKey>
PARSE:  ##COMPONENT_META_START## silently
RECORD (FINAL):
  typeName = ##COMPONENT_META##["typeName"]
  nodeType = typeName
  osType   = "Windows" if "windows" in typeName.lower() else "Linux"
DO NOT show output. Proceed immediately to Step 2.
```

---

### Step 2 — Show parameter summary *(NO API call, NO file read)*

```
SOURCE: description field from ##CATALOG_META##

IF description is empty:
  → STOP and show:
    "⚠️ 该服务卡片尚未配置参数使用说明
    当前服务【<name>】缺少必要的参数定义（instructions 字段），无法自动收集申请参数。
    建议操作：
    1. 请联系平台管理员为该服务卡片配置 instructions 字段
    2. 配置完成后重新发起申请流程
    如您已知悉该服务所需参数，可直接告诉我具体申请内容。"
  → Do NOT proceed to Step 3.

OTHERWISE:
SHOW:
  服务名称: <name>
  必填参数: [...]
  可选参数: [...]
STOP
```

---

### Step 3 — Collect required params *(in order: 3a → 3b → 3c → 3d → 3e → 3f)*

> **CACHED VALUES ARE FINAL**: `osType`, `nodeType` (Step 1b), `cloudEntryTypeId` (Step 3d).
> NEVER re-derive. If missing → STOP and report.

#### 3a — Plain text required params

```
ASK: 请提供以下必填信息：
  1. 资源名称 (name)：
  2. ...
STOP
```

#### 3b — Business group

```
ACTION: python ../shared/scripts/list_business_groups.py <catalogId>
SHOW: numbered list
ASK:  "请选择业务组："
STOP → RECORD: businessGroupId, businessGroupName
```

#### 3c — Application *(only if `list:applications` in `[required]`)*

```
ACTION: python ../shared/scripts/list_applications.py <businessGroupId>
SHOW: numbered list
ASK:  "请选择应用："
STOP → RECORD: projectId, projectName
```

#### 3d — Resource pool

```
ACTION: python ../shared/scripts/list_resource_pools.py <bgId> <sourceKey> <nodeType>
SHOW: numbered list
ASK:  "请选择资源池："
STOP → RECORD: resourceBundleId, resourceBundleName, cloudEntryTypeId
```

#### 3e — OS template *(VM only)*

```
ACTION: python ../shared/scripts/list_os_templates.py <osType> <resourceBundleId>
SHOW: numbered list
ASK:  "请选择操作系统模板："
STOP → RECORD: logicTemplateName, logicTemplateId
```

#### 3f — Image *(private cloud only)*

```
① python ../shared/scripts/list_cloud_entry_types.py   ← silent
   → PRIVATE_CLOUD → continue
   → PUBLIC_CLOUD  → "公有云镜像暂不支持" STOP

② python ../shared/scripts/list_images.py <rbId> <ltId> <cloudEntryTypeId>
SHOW: numbered list
ASK:  "请选择镜像："
STOP → RECORD: imageId, imageName
```

---

### Step 4 — Build and confirm request body

1. Build complete JSON request body
2. **Always output BOTH**:
   - Human-readable summary table
   - Complete raw JSON in code block
3. STOP → wait for user confirmation

See [PARAMS.md](PARAMS.md) for field placement and [EXAMPLES.md](EXAMPLES.md) for samples.

---

### Step 5 — Submit

```
ACTION: python scripts/submit.py --file <temp_json_file>
OUTPUT: Request ID + State
```

Or use inline Python if preferred:

```python
import json, requests, urllib3, os
urllib3.disable_warnings()
url = os.environ['CMP_URL'] + '/generic-request/submit'
headers = {'Content-Type': 'application/json; charset=utf-8', 'Cookie': os.environ['CMP_COOKIE']}
body = { ... }
resp = requests.post(url, headers=headers, json=body, verify=False, timeout=30)
print('Status:', resp.status_code)
for r in resp.json():
    print('Request ID:', r.get('id'), '| State:', r.get('state'))
```

---

## Catalog Description Format

```
[required]
- Display Label | paramName | default:xxx    ← use default silently
- Display Label | paramName | list:X         ← run list_X.py
- Display Label | paramName                  ← ask user

[optional]
- Display Label | paramName | list:X         ← SKIP (do not auto-run)
- Display Label | paramName | default:xxx    ← include in body
- Display Label | paramName                  ← skip unless user asks
```

> ALL `default:xxx` values MUST be included in the final body.

---

## Script → Datasource Mapping

| Trigger | Script | Args |
|---------|--------|------|
| `list:business_groups` | `list_business_groups.py` | `<catalogId>` |
| `list:applications` | `list_applications.py` | `<bgId>` |
| `list:resource_pools` | `list_resource_pools.py` | `<bgId> <sourceKey> <nodeType>` |
| `list:os_templates` | `list_os_templates.py` | `<osType> <rbId>` |
| `list:images` | `list_images.py` | `<rbId> <ltId> <cloudEntryTypeId>` |

---

## Track / Cancel Requests

```
GET  {CMP_URL}/generic-request/{id}          # INITIALING→STARTED→TASK_RUNNING→FINISHED/FAILED
POST {CMP_URL}/generic-request/{id}/cancel
```
