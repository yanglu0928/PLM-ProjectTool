# Handover Analysis 五个普通写命令 HTTP V1 增量

日期：2026-10-05。实现基线：冻结 API-01/API-04、DM-05、CR-HND-005；不增加或改名 Operation。

## 公共边界

Router 只通过 `create_app(handover_command_router=...)` 显式注入；默认应用五个路径均为 404。A05-A04 不进入 Windows 生产组合，真实组合与 HTTP/PostgreSQL 全链验证留给 A05-A07。

所有命令要求可信 Origin/Host、当前 `plm_session`、`X-CSRF-Token` 和有效 License；项目角色、资源隔离与当前资格继续由 Application Owner 同事务重验。创建、归档、版本创建和校验要求 16～128 字符可打印 ASCII `Idempotency-Key`；修改、归档和版本创建要求强 `If-Match: "v<n>"`。

JSON 只接受 UTF-8 `application/json`，拒绝重复键、未知字段、NaN/Infinity、多余 query 和超过 2 MiB 正文。ID 必须是 canonical lowercase non-zero UUID。响应均为冻结 `data/trace_id` Envelope、`Cache-Control: no-store`，不投影内部表、文档路径、Evidence 正文、AI 输入输出、异常或 Secret。

## Operation

|Operation|请求|成功|
|---|---|---|
|`HND_ANALYSIS_CREATE` `POST /api/v1/projects/{project_id}/handover-analyses`|`analysis_purpose` 和非变 `source_documents[]`|201 ACTIVE identity、来源摘要、ETag、Location|
|`HND_ANALYSIS_PATCH` `PATCH .../{analysis_id}`|精确 `analysis_purpose`，强 If-Match|200 AnalysisView + 新 ETag|
|`HND_ANALYSIS_ARCHIVE` `POST .../{analysis_id}:archive`|空正文，强 If-Match，幂等键|200 ARCHIVED AnalysisView + 新 ETag|
|`HND_VERSION_CREATE` `POST .../{analysis_id}/versions`|强 If-Match；完整固定来源、APPROVED Capability Baseline Version、`items[]`、AI Task refs|201 DRAFT Version、内容指纹、Analysis 新 ETag、Location|
|`HND_VERSION_VALIDATE` `POST .../{analysis_version_id}:validate`|空正文、幂等键|200 当前来源/问题/完整性报告，不改正式状态|

`AnalysisItemInput` 精确字段为 `analysis_item_id/item_type/title/statement/impact/severity/priority/recommendation/confirmation_question/required_input_spec/source_missing/evidence_refs/capability_refs/options`。`capability_refs`、`evidence_refs` 和 `ai_task_refs` 是 UUID 数组；option 为精确 `option_code/label/description`。输入仅固定引用，资料、Evidence、Capability 和 AI provenance 资格仍由对应 Owner 校验。

## 错误、兼容与回滚

权限或资源隔离失败对资源统一 404；License 403；缺 If-Match 428；版本/状态/幂等冲突 409；字段、固定来源、Evidence 资格问题 422；未知内部失败 503。`HANDOVER_SOURCE_REQUIRED`、`HANDOVER_ITEM_INCOMPLETE` 及其余 Handover 码来自冻结 API-04 码表。

本增量无 Schema/Migration/依赖/配置/网络/外发。为保证打包与源码行为一致，补充 `handover.api` 包标记，使已有 Action 读取与新增命令 Router 均进入 wheel。回滚方式是不注入 Router；合法业务历史不删除。业务原子送审、五个读取 Router 与 Windows 组合仍分别由 A05-A05～A07 完成。
