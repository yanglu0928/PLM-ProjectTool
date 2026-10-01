# Evidence 资格操作结果回查 V1 增量（CR-EVD-004）

状态：`DESIGN_ONLY / NOT_IMPLEMENTED`；2026-10-01。原冻结 API Contract V1 `64cdf09` 原样保留。

|Operation|Method / Path|主体|响应|
|---|---|---|---|
|EVIDENCE_ELIGIBILITY_OPERATION_LOOKUP|POST `/api/v1/projects/{project_id}/evidence/{evidence_id}:lookup-eligibility-operation`|原操作者且当前 PM/CustomerManager|200 `{status: UNCONFIRMED}` 或 `{status: COMPLETED, evidence_id, first_status_code: 200}`|
|EVIDENCE_ELIGIBILITY_OPERATION_LOOKUP_GLOBAL|POST `/api/v1/global/evidence/{evidence_id}:lookup-eligibility-operation`|原操作者且当前 DeploymentAdmin|同上|

Body 只接受 `operation_key`（现有 Idempotency-Key 格式 16～128 printable ASCII）。成功仍采用 `{data, trace_id}` 和 `Cache-Control: no-store`。不返回 Key、指纹、理由、当前资格或其他操作者结果。POST 仅为隐藏 URL 中的 Key，没有业务写入/收据预留；验证 CSRF，不需要新的 Idempotency-Key/If-Match。错误沿用安全 Envelope：401 Session、403 CSRF/License、404 无权或资源不存在、422 Key 不合规、409 已完成但引用冲突、503 依赖不可用。`UNCONFIRMED` 可能是尚未提交或不存在，不能自动换 Key/重发。`COMPLETED` 只证明该 actor/project/operation/key 的收据已提交且结果引用匹配，当前状态须另行受权 GET。

本设计须按 CR 分项实现并验证后更新状态，不因本文件存在而声称端点可用。
