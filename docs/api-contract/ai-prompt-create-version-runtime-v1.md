# AI_PROMPT_CREATE_VERSION 运行时补充（非冻结合同改写）

版本：0.1.0；日期：2026-10-02；依据冻结 API-03、CR-AI-007。路径仍为 `POST /api/v1/admin/ai/prompt-templates/{prompt_template_id}/versions`，仅作为可选 Router 存在，默认和当前生产组合不挂载。

请求：DeploymentAdmin Session Cookie、受信 Origin、CSRF、`Idempotency-Key`、强 `If-Match: "vN"`，唯一 `application/json` Content-Type；body 严格七字段：`task_type`、`system_template`、`user_template`、`output_schema_ref`、`schema_version`、`rag_policy_ref`、`provider_policy_ref`。正文最多由 Domain 各接受 65536 个规范化字符；HTTP 总编码字节最多 2 MiB，拒绝重复 JSON 键、未知字段、非标准数字常量、查询参数与弱/多个 ETag。Prompt 正文不得出现在响应、审计或普通日志。

成功：201，`data` 仅含 template UUID、version_no、TaskType、system/user SHA-256、四个 schema/policy 元数据、`etag`；外层有本次 `trace_id`，Header 有 `Cache-Control: no-store`、ETag 与 Location。同 Idempotency-Key 对同内容/同预期版本重放原不可变结果，响应 trace_id 为当前请求，其他结果字段不从当前可变状态重建。错误沿冻结公共错误码：无权/不存在 404、许可 403、缺 If-Match 428、版本/状态/幂等冲突 409、内容未被签名清单准入 422、运行依赖故障 503。公开装配必须有受信发行清单与真实审查证据，不能仅因本 Router 存在而开放。

当前验证仅为合成 Service 的 HTTP 合同；真实 PostgreSQL、正式密钥/内容审查、Windows Server 2025/Debian 13、安装/升级及 Gate 3 未验。无冻结 `/api/v1` Breaking Change。
