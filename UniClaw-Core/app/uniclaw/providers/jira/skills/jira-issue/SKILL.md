---
name: "jira-issue"
description: "Jira issue skill for CRUD. Trigger when user asks to create/get/update/delete Jira issues (e.g. '创建一个Jira 的issue，记录服务失败的问题')."
---

# jira-issue

This is a provider skill under `providers/jira/skills/jira-issue`.

## Purpose

Handle Jira Issue CRUD by orchestrating local scripts in `scripts/` that call Jira REST API.

## Trigger Conditions

Use this skill when user intent is any of:
- Create issue / report bug / log incident
- Get issue details
- Update issue fields
- Delete issue

## Script Entry Points

- `scripts/create_issue.py`
- `scripts/get_issue.py`
- `scripts/update_issue.py`
- `scripts/delete_issue.py`

## Invocation Guidance

When the user says:
- "创建一个Jira 的issue，记录服务失败的问题"

Construct and run:

```bash
python app/uniclaw/providers/jira/skills/jira-issue/scripts/create_issue.py \
  --summary "服务失败问题" \
  --description "记录服务失败的问题"
```

Then return created issue key to user.

## Notes

- Scripts read Jira connection from `uniclaw.json` (`service_providers.jira`).
- API mappings are in `references/api_mapping.md`.
- Skill scripts are part of this skill package, not standalone global skills.
