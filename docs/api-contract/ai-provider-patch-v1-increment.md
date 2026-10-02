# AI_PROVIDER_PATCH 实现增量（冻结合同不变）

版本：V1；日期：2026-10-02；任务：`AI-01-A03-P04-A02-P02`。细化 Gate 2 冻结的 PATCH `200 config version + ETag`，不更改路径、角色或强If-Match要求。

`PATCH /api/v1/admin/ai/providers/{provider_id}` 需要可信Origin/Host、当前Cookie Session、`X-CSRF-Token`、强 `If-Match: "v<lock_version>"` 和 `application/json`。正文为非空受控部分DTO，只允许 `display_name`、`endpoint_policy_ref`、`secret_ref`、`data_region`、`egress_class`、`capabilities`；缺失字段不修改，显式null不接受。Kind、原始URL、API Key/明文Secret及未知字段拒绝。`secret_ref` 为canonical lowercase UUID；能力数组非空、不重复，仅冻结枚举。重复JSON键、超8192字节和多余query拒绝。

冻结表未将 `Idempotency-Key` 列为客户端必填。缺该Header时服务器生成仅本次事务的随机收据键，成功后同If-Match重试返回版本冲突；提供合法Key时同Key/同规范化原始部分DTO返回首次结果，异载荷返回409。响应固定200：`data.provider_id`、`data.config_version`、`data.etag` 与 `trace_id`，并带同值`X-Trace-Id`、强`ETag`及`Cache-Control: no-store`。内部版本创建收据不是公开HTTP201。PATCH仅追加配置版本，不激活Provider、测试连通性或授权客户数据外发。

错误沿冻结Envelope：格式400、会话401、CSRF/License403、无权或不存在404、状态/版本/幂等409、输入422、缺If-Match428、Secret/Provider暂不可用503。本项只由 `create_app(ai_provider_patch_router=...)` 显式装配；默认及当前Windows组合未挂载，待后续平台写模式任务验证。
