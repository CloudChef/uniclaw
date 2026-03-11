# Request Body Examples

## Canonical VM Example (vSphere)

**This is the standard structure for VM requests. All VM types follow this pattern.**

```json
{
  "name": "my-linux-vm",
  "catalogName": "Linux VM",
  "businessGroupName": "我的业务组150",
  "userLoginId": "admin",
  "resourceBundleName": "Vsphere资源池",
  "resourceSpecs": [
    {
      "type": "cloudchef.nodes.Compute",
      "node": "Compute",
      "computeProfileName": "微型计算",
      "cpu": 1,
      "memory": 1,
      "logicTemplateName": "CentOS",
      "templateId": "vm-551",
      "credentialUser": "root",
      "credentialPassword": "P@ssw0rd365",
      "networkId": "network-18963"
    }
  ]
}
```

**Field sources:**
- `name` ← user input
- `catalogName` ← Step 1a selection
- `businessGroupName` ← Step 3b selection
- `resourceBundleName` ← Step 3d selection
- `type` ← Step 1b `typeName`
- `computeProfileName`, `cpu`, `memory`, `credentialUser`, `credentialPassword`, `networkId` ← instructions `default:xxx`
- `logicTemplateName` ← Step 3e selection
- `templateId` ← Step 3f selection (private cloud image ID)

---

## WRONG Structure (DO NOT USE)

```json
{
  "catalogId": "BUILD-IN-CATALOG-LINUX-VM",
  "name": "my-linux-vm",
  "businessGroupId": "47673d8d-...",
  "resourceBundleName": "Vsphere资源池",
  "computeProfileName": "微型计算",
  "logicTemplateName": "CentOS",
  "templateId": "vm-551",
  "cpu": 1,
  "memory": 1
}
```

**Why wrong:** All fields are flattened at top-level. VM-specific fields MUST be inside `resourceSpecs[]`.

---

## Minimum (3 required fields)

```json
{
  "catalogName": "Linux VM",
  "businessGroupName": "我的业务组",
  "userLoginId": "admin"
}
```

---

## Azure VM

```json
{
  "catalogId": "40cd2522-...",
  "businessGroupName": "我的业务组",
  "userLoginId": "admin",
  "resourceSpecs": [{
    "type": "cloudchef.nodes.Compute",
    "node": "Compute",
    "computeProfileName": "2C4G",
    "logicTemplateName": "CentOS",
    "credentialUser": "root",
    "credentialPassword": "P@ssw0rd365",
    "params": { "resource_group_name": "rg-prod", "storage_account": "/subscriptions/.../storageAccounts/xx" },
    "systemDisk": { "size": 30 },
    "networkId": "/subscriptions/.../virtualNetworks/mynet",
    "subnetId": "/subscriptions/.../subnets/mysubnet"
  }]
}
```

---

## Aliyun ECS

```json
{
  "catalogName": "Linux VM",
  "businessGroupName": "我的业务组",
  "userLoginId": "admin",
  "resourceBundleName": "aliyun资源池",
  "resourceSpecs": [{
    "type": "cloudchef.nodes.Compute",
    "node": "Compute",
    "flavorId": "ecs.n1.tiny",
    "logicTemplateName": "CentOS",
    "resourceBundleParams": { "available_zone_id": "cn-hangzhou-i" },
    "credentialUser": "root",
    "credentialPassword": "P@ssw0rd",
    "systemDisk": { "size": 50, "volume_type": "cloud_ssd" },
    "networkName": "my-network",
    "params": { "v_switch_id": "vsw-xxxxxxxx" }
  }]
}
```

---

## vSphere VM with specs

```json
{
  "catalogName": "Linux VM",
  "businessGroupName": "我的业务组",
  "userLoginId": "admin",
  "resourceBundleName": "Vsphere资源池",
  "resourceSpecs": [{
    "type": "cloudchef.nodes.Compute",
    "node": "Compute",
    "cpu": 2,
    "memory": 4,
    "logicTemplateName": "CentOS",
    "networkId": "network-18963"
  }]
}
```

---

## OpenStack dual-NIC + static IP

```json
{
  "catalogName": "openstack linux",
  "businessGroupName": "111",
  "userLoginId": "admin",
  "resourceSpecs": [{
    "type": "cloudchef.nodes.Compute",
    "node": "Compute",
    "logicTemplateName": "centos",
    "systemDisk": { "size": 50 },
    "networkSpecs": [
      { "networkName": "net0001", "subnetName": "net33-subnet", "networkParams": { "ip_allocation_method": "STATIC_IP", "ip_address": "192.168.1.10" } },
      { "networkName": "net0001", "subnetName": "net33-subnet", "networkParams": { "ip_allocation_method": "STATIC_IP", "ip_address": "192.168.9.13" } }
    ]
  }]
}
```
