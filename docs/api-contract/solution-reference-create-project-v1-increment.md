# SOL-01-A04-P03-P02-P03：PROJECT Reference 创建 HTTP 增量

日期：2026-10-09；依据 Gate 2 冻结 API-01/API-04。此文件细化而不修改冻结的 `SOL_REFERENCE_CREATE` 操作。GLOBAL 路径未在本增量装配。

`POST /api/v1/projects/{project_id}/reference-solutions` 接受当前 `plm_session` Cookie、`X-CSRF-Token`、`Idempotency-Key` 和可信 Origin/Host；路径 ProjectId 是唯一受信 Scope 来源，不接受 body 中的 actor/project/scope。JSON 正文恰含 `name`、`document_version_ids`、`evidence_ids`、`source_project_class`、`deidentification_class`、`applicability`；版本和证据 ID 为有序 canonical UUID 数组。未知或重复键、非 JSON、查询串拒绝。正文上限 128 KiB；应用层再检查名称、来源数量、重复 ID、JSON 适用性和当前文件/Evidence/授权资格。

成功为 `201`，`data` 含 `reference_solution_id`、`reference_version_id`、`scope=PROJECT`、`project_id`、`name`、`eligibility_state=REFERENCE_ONLY`、`version_state=DRAFT`、`created_by`、`created_at`、`etag`；响应 `ETag: "v0"`、相应资源的 `Location`、`Cache-Control: no-store` 和与 body 一致的 Trace ID。相同 Key/请求保留首次语义；异载荷 `409 CONFLICT_IDEMPOTENCY`。

公开错误沿用 API-01 Envelope：Session 无效 401、Origin/CSRF 403、无权/跨项目/来源不可见 404、许可拒绝 403、畸形正文 400、字段不合法 422、来源服务不可用 503。不回传 Session、CSRF、绝对文件路径、客户正文或内部异常。PROJECT_MANAGER/IMPLEMENTATION_MEMBER 才能创建；角色、Project 状态与来源在同一写事务中再次验证。

本增量仅提供可注入的 Router 和 `create_app` opt-in 插槽；默认应用、Windows 正式组合和 GLOBAL 路由均不开放。真实 ASGI/PG/文件端到端、GET/List、GLOBAL 人工脱敏确认入口及 UI 是后续任务，不能据此认定 Reference 可供用户使用。
