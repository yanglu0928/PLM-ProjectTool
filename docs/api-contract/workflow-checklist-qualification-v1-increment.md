# Workflow Checklist Qualification API V1 兼容增量

版本 `0.1.0-dev.0`；日期 2026-10-06；依据 `CR-WFL-008`。本文只定义新增的
资格预览读边界，不修改冻结 `WORKFLOW_GET` 或 `WORKFLOW_CHECKLIST_RECORD`。

## Endpoint

```text
GET /api/v1/projects/{project_id}/workflow/checklist-items/{item_key}/qualification
Operation ID: WORKFLOW_CHECKLIST_QUALIFICATION_GET
Role: ProjectManager on ACTIVE Project
```

- `project_id` 必须为 canonical 非零 UUID。
- `item_key` 首版仅允许 `HANDOVER_BASELINE` / `HANDOVER_ISSUES`。
- 不接受 query/body；Cookie Session、受信 Host、License 和 Project 成员身份每次重验。
- 成功响应 `200`，`Cache-Control: no-store`，强 `ETag` 必须等于响应中
  `workflow_etag`。

## Success data

```json
{
  "workflow_id": "uuid",
  "project_id": "uuid",
  "definition_version": 1,
  "stage_key": "HANDOVER",
  "item_key": "HANDOVER_BASELINE",
  "current_item_state": "PENDING",
  "workflow_etag": "\"v4\"",
  "handover_analysis_version_id": "uuid",
  "review_round_ref": "uuid",
  "evidence_refs": ["uuid"]
}
```

字段严格白名单；`evidence_refs` 为服务端 Owner 规范顺序、非空、无重复集合。
响应不含文档正文/路径、AI 输入输出、内部内容摘要、权限凭据或失败事实细节。

## Error and use rule

- `401 AUTH_SESSION_EXPIRED`
- `403 AUTH_CSRF_INVALID` / `LICENSE_OPERATION_DENIED`
- `404 RESOURCE_NOT_FOUND`
- `409 PROJECT_ARCHIVED` / `CONFLICT_STATE` / `WORKFLOW_GATE_NOT_SATISFIED`
- `400 REQUEST_MALFORMED`、`422 VALIDATION_FAILED`、`503 SYSTEM_UNAVAILABLE`

前端只可把成功预览作为构造紧随其后的 Checklist PASS 请求的输入。它不是
当前 Gate 通过证明；写入必须使用 `workflow_etag` 作为 `If-Match`，并接受服务端
在写事务中的再次完整复验。
