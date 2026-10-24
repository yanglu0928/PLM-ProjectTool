# Workflow Prototype 资格预览 V1 兼容增量（待启用）

日期：2026-10-08。依据 `CR-PRT-005`。状态：A11-A02 合同设计；A11-A04 前不得将下列 Prototype item_key 标为已开放。既有 Handover/Survey/Requirement 响应不变。

复用 `GET /api/v1/projects/{project_id}/workflow/checklist-items/{item_key}/qualification`；仅在真实 Owner 与 Workflow 写时重证均通过后，新增 `PROTOTYPE_SCOPE_DECISIONS` 和 `PROTOTYPE_COVERAGE`。Session/License/ACTIVE Project/ProjectManager、受信 Host、当前阶段 PROTOTYPE、无 query/body、`Cache-Control: no-store`、强 Workflow ETag 与既有错误语义不变。

Prototype 专用成功 `data`：

```json
{
  "workflow_id": "uuid",
  "project_id": "uuid",
  "definition_version": 1,
  "stage_key": "PROTOTYPE",
  "item_key": "PROTOTYPE_COVERAGE",
  "current_item_state": "PENDING",
  "workflow_etag": "\"v4\"",
  "qualified_subjects": [
    {
      "subject_type": "REQ-03",
      "subject_id": "uuid",
      "subject_version_id": "uuid",
      "review_round_ref": "uuid"
    },
    {
      "subject_type": "PRT-03",
      "subject_id": "uuid",
      "subject_version_id": "uuid",
      "review_round_ref": "uuid"
    }
  ],
  "evidence_refs": ["uuid"]
}
```

`qualified_subjects` 是 Owner 规范顺序、非空、无重复的当前受审主体；`REQ-03` 证明当前批准需求，`PRT-03` 只在需原型且当前已批准时出现。全范围经真实 NOT_REQUIRED 决定验证后可只有 `REQ-03`，但不允许空主体或空 Evidence。该数组仅是预览，不是客户确认或 Gate verdict；前端不允许据此生成批准事实。既有 `WORKFLOW_CHECKLIST_RECORD` 写请求字段不变，写事务必须完整重新证明范围、Review、Evidence、固定制品和覆盖；`PROTOTYPE_COVERAGE` 中未覆盖验收标准不会因填写原因自动 PASS。失败统一 `WORKFLOW_GATE_NOT_SATISFIED`，不得泄漏哪项客户事实或文件不可用。

不返回正文、路径、内容指纹、内部锁版本、客户姓名或未授权项目细节。无 Schema/数据迁移；若 Owner 实施发现历史不可证明，应按 CR 补充迁移而非伪造。回滚关闭新的 Prototype item_key 注册与 Router 投影，保留已有 Checklist/Transition 历史。
