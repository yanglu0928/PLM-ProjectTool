# Capability 六个普通命令 HTTP V1 增量

日期：2026-10-05。实现基线：冻结 API-01/API-04；不增加或改名 Operation。

## 公共边界

Router 仅通过 `create_app(capability_command_router=...)` 显式注入；默认应用六个路径均为 404。A05-A04 不进入 Windows 生产组合，该接线留给 A05-A07。所有命令要求可信 Origin/Host、当前 `plm_session`、`X-CSRF-Token`、DeploymentAdmin 和有效 License；POST 另要求 16～128 字符可打印 ASCII `Idempotency-Key`，PATCH/Archive/Version Create 使用强 `If-Match: "v<n>"`。响应均为冻结 `data/trace_id` Envelope、`Cache-Control: no-store`，不返回内部表名、异常或 Secret。

JSON 只接受 UTF-8 `application/json`，拒绝重复键、未知字段、NaN/Infinity、多余 query 和超过 2 MiB 的正文。ID 必须是 canonical lowercase non-zero UUID。

## Operation

|Operation|请求|成功|
|---|---|---|
|`CAP_BASELINE_CREATE` `POST /api/v1/global/capability-baselines`|`baseline_code/name/description/source_documents[]`；每个来源为固定 `document_id/document_version_id`|201 identity、状态、来源摘要、ETag、Location|
|`CAP_BASELINE_PATCH` `PATCH /api/v1/global/capability-baselines/{baseline_id}`|非空受控 partial DTO，仅 `name`、`description`；显式 `description:null` 表示清空|200 BaselineView + 新 ETag|
|`CAP_BASELINE_ARCHIVE` `POST .../{baseline_id}:archive`|空正文、强 If-Match、幂等键|200 ARCHIVED BaselineView + 新 ETag|
|`CAP_VERSION_CREATE` `POST .../{baseline_id}/versions`|强 If-Match；完整 `items[]` 快照|201 DRAFT Version、内容指纹、Baseline新ETag、Location|
|`CAP_VERSION_VALIDATE` `POST .../{baseline_version_id}:validate`|空正文、幂等键|200 ValidationReport；不改变正式状态|
|`CAP_VERSION_RESTRICT` `POST .../{baseline_version_id}:restrict`|`reason_code` 受控码、幂等键|200 RESTRICTED Version + reason code|

`CapabilityItemInput` 精确字段为 `stable_item_id/capability_code/domain_name/module_name/feature_name/name/description/boundary/prerequisites/interface_refs/document_refs/evidence_refs/item_state`。来源和 Evidence 使用固定 UUID 引用，业务 Owner 继续执行 GLOBAL Document/Evidence 当前资格验证。

## 错误与回滚

权限失败对资源统一 404；License 403；缺 If-Match 428；版本/状态/幂等冲突 409；字段或 Evidence 资格问题 422；未知内部失败 503。新增公开错误 `CAPABILITY_EVIDENCE_REQUIRED` 来自冻结 API-04 码表。

本增量无 Schema/Migration/依赖/网络/外发。回滚方式是不注入 Router；已由 Application Owner 写入的合法业务历史不删除。送审命令、五个读取 Router 与 Windows 生产组合仍分别由 A05-A05～A07 完成。
