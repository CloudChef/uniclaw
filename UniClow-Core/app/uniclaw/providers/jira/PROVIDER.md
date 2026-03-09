# JIRA Service Provider

JIRA 项目管理与工单追踪服务。

## 连接参数

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| base_url | string | 是 | JIRA 服务地址（如 `https://jira.corp.com`） |
| username | string | 是 | JIRA 用户名 |
| token | string | 是 | JIRA API Token 或密码（建议使用 `${JIRA_TOKEN}` 环境变量） |

## 配置示例

```json
{
  "service_providers": {
    "jira": {
      "prod": {
        "base_url": "https://jira.corp.com",
        "username": "admin",
        "token": "${JIRA_PROD_TOKEN}"
      },
      "dev": {
        "base_url": "https://jira-dev.corp.com",
        "username": "admin",
        "token": "${JIRA_DEV_TOKEN}"
      }
    }
  }
}
```

## 提供的 Skills

- `jira__create_issue` — 创建 JIRA Issue（需要 project_key、summary、description）
