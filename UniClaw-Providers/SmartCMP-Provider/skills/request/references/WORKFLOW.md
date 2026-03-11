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
6. **NEVER create temp files** — no `.py`, `.txt`, `.json` temp files. Use ONLY existing scripts.
7. **NEVER redirect output** — no `>`, `>>`, `2>&1`, `| tee`, `Out-File`. Run scripts directly.
8. **`list_components.py` is called EXACTLY ONCE** — silently in Step 1b.
9. **NEVER flatten request body** — VM fields MUST be inside `resourceSpecs[]` array.
10. **Script output goes to YOUR CONTEXT** — you read stdout directly, no file needed.

> **WHY NO TEMP FILES?**
> - Script output contains `##BLOCK_START##...##BLOCK_END##` markers
> - You parse these markers directly from stdout
> - Your LLM context IS your memory — values persist across turns
> - Files add latency and clutter with ZERO benefit

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

**IMPORTANT: nodeType is REQUIRED for correct resource pool filtering.**

```
REQUIRED INPUTS:
  bgId      ← from Step 3b (businessGroupId)
  sourceKey ← from Step 1a cache (##CATALOG_META##)
  nodeType  ← from Step 1b cache (typeName from ##COMPONENT_META##)

ACTION: python ../shared/scripts/list_resource_pools.py <bgId> <sourceKey> <nodeType>

Example:
  python ../shared/scripts/list_resource_pools.py \
    47673d8d-6b3f-41e1-8ec0-c37e082d9020 \
    resource.iaas.machine.instance.abstract \
    cloudchef.nodes.Compute

Or with named args:
  python ../shared/scripts/list_resource_pools.py \
    --business-group-id 47673d8d-... \
    --source-key resource.iaas.machine.instance.abstract \
    --node-type cloudchef.nodes.Compute

SHOW: numbered list
ASK:  "请选择资源池："
STOP → RECORD: resourceBundleId, resourceBundleName, cloudEntryTypeId
```

> **WARNING**: If nodeType is omitted, the API may return incomplete results or wrong resource pools.

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

**CRITICAL: Use the EXACT structure below. NEVER flatten fields.**

```json
{
  "name": "<user-provided>",
  "catalogName": "<from Step 1a>",
  "businessGroupName": "<from Step 3b>",
  "userLoginId": "admin",
  "resourceBundleName": "<from Step 3d>",
  "resourceSpecs": [
    {
      "type": "<from Step 1b: typeName>",
      "node": "Compute",
      "computeProfileName": "<from instructions default or user>",
      "cpu": <number>,
      "memory": <number in GB>,
      "logicTemplateName": "<from Step 3e>",
      "templateId": "<from Step 3f if private cloud>",
      "credentialUser": "<from instructions default>",
      "credentialPassword": "<from instructions default>",
      "networkId": "<from instructions default>"
    }
  ]
}
```

**Field placement rules:**

| Location | Fields |
|----------|--------|
| **Top-level** | name, catalogName, businessGroupName, userLoginId, resourceBundleName |
| **Inside resourceSpecs[]** | type, node, cpu, memory, computeProfileName, logicTemplateName, templateId, credentialUser, credentialPassword, networkId, systemDisk, dataDisks |

**Where to get values:**

| Field | Source |
|-------|--------|
| `type` | Step 1b `typeName` (e.g. `cloudchef.nodes.Compute`) |
| `node` | Always `"Compute"` for VM |
| `computeProfileName` | instructions `default:xxx` or user input |
| `cpu`, `memory` | instructions `default:xxx` or user input |
| `logicTemplateName` | Step 3e selection |
| `templateId` | Step 3f selection (private cloud only) |
| `credentialUser/Password` | instructions `default:xxx` |
| `networkId` | instructions `default:xxx` |

**Output format:**
1. Human-readable summary table
2. Complete raw JSON in code block (MUST match structure above)
3. STOP → wait for user confirmation

See [EXAMPLES.md](EXAMPLES.md) for complete samples.

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
