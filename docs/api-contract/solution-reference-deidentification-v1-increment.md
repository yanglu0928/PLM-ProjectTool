# SOL-01-A04-P08-P02：GLOBAL Reference 人工脱敏确认 API 增量合同

日期：2026-10-09；依据冻结 API-01/API-04、CR-SOL-006/007/009。以下为新增白名单操作，不修改冻结 `SOL_REFERENCE_CREATE`/GET/List。P03-P03/P04/P05 已完成可注入 HTTP、隔离 PG 与 Windows 显式写模式组合；默认应用、只读模式仍关闭，正式信任账户和实际人工确认未验，不能据此声称业务入口可用。

|Operation ID|Method/Path|语义|
|---|---|---|
|`SOL_REFERENCE_DEIDENTIFICATION_PREVIEW`|`POST /api/v1/global/reference-deidentification-confirmations:preview`|读取当前 GLOBAL 固定来源证明和定位身份，不创建确认/Audit/收据|
|`SOL_REFERENCE_DEIDENTIFICATION_CONFIRM`|`POST /api/v1/global/reference-deidentification-confirmations`|实际管理员明确声明，当前来源指纹匹配后原子创建确认/Audit/收据|
|`SOL_REFERENCE_DEIDENTIFICATION_REVOKE`|`POST /api/v1/global/reference-deidentification-confirmations/{confirmation_id}:revoke`|实际管理员受控撤回最新有效确认，保留历史/Audit/收据|

三项均要求可信 Host/Origin、当前 `plm_session`、`X-CSRF-Token`、有效 License 与 DeploymentAdmin。Preview 虽只读但以 POST 承载固定来源集合，也须 CSRF，不写账本。Confirm/Revoke 另要求 `Idempotency-Key`；重放仅返回相同操作首次结果，冲突 `409`。不接受 query、客户端 actor/scope/project、绝对路径、文件正文、AI 自动声明、未知/重复 JSON 键；请求上限 128 KiB，响应 `Cache-Control: no-store`、一致 Trace ID。

Preview/Confirm 共用精确来源字段：`document_version_ids` 为创建顺序的 1～100 个规范 UUID；`evidence_ids` 为 0～500 个规范 UUID；`source_project_class`、`deidentification_class` 为已归一化非空字符串（≤128）；`applicability` 为受限 JSON 对象。均只允许 GLOBAL 当前受权、完整且合格的固定来源，不接收来源 SHA 作为证明。Preview 成功 `200` 只投影 `source_fingerprint`（服务端现时来源集合 SHA-256）、有序 `document_refs: [{document_id,document_version_id}]`、有序 `evidence_ids` 和 `previewed_at`；客户端可用现有受权 Document 详情/Evidence Viewer 打开原文，不把预览当批准或持久确认。

Confirm 另强制 `expected_source_fingerprint` 为 Preview 返回的 64 位小写十六进制，`attestation_statement` 精确为 `I_VERIFIED_DEIDENTIFICATION`，`expires_at` 为 UTC 时间且晚于当前、最长 30 天。服务端仍从现时 Document/Evidence 重新计算来源指纹，若与预览不同必须拒绝、要求重新预览；不得信任客户端指纹作为来源事实。成功 `201` 返回 `confirmation_id`、`source_fingerprint`、`confirmed_by`、`confirmed_at`、`expires_at`、`trace_id`，但不自动创建 GLOBAL Reference、不自动标记 Eligibility。实际 UI 要求管理员逐项打开必要原文、显式勾选核查声明；脚本合成点击只验证机制，不代替实际人的业务确认。

Revoke 路径 ID 为非零规范 UUID，请求体恰含 `reason_code`，取 `SOURCE_EXPOSED`、`SCOPE_CHANGED`、`ADMIN_REVIEW`；成功 `200` 仅返回 `confirmation_id`、`revoked_at`、`trace_id`。撤回不可删除历史，不允许旧确认在最新确认撤回后复活。

错误采用 API-01 信封：Session 失效 401、Host/Origin/CSRF 或 License 403、身份/来源越权或缺失 404、畸形请求 400、字段不合法 422、已漂移预览 `409 SOURCE_SNAPSHOT_CHANGED` 或幂等冲突 409、来源/内部不可用 503。前端遇已漂移预览一律清除旧预览并要求重新核查。公开错误不得含客户正文、文件路径、Secret、内部栈或可用于枚举跨项目/全局资料的信息。响应均有当前请求顶层 `trace_id`；幂等重放的 Confirm `data.trace_id` 保留首次确认审计的 Trace ID。默认应用和 GLOBAL Create 仍关闭；Windows 显式组合、真实 PG/HTTP、前端/Edge 在后续任务验证后分别开放。
