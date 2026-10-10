# AI_PROMPT_ACTIVATE_VERSION 运行时补充（非冻结合同改写）

版本：0.1.0.dev0；日期：2026-10-02；依据冻结 API-03、CR-AI-008、DEC-688。路径仍为 `POST /api/v1/admin/ai/prompt-templates/{prompt_template_id}/versions/{version_no}:activate`，仅作为可选 Router；默认及当前生产组合不挂载。

请求：DeploymentAdmin Session Cookie、受信 Origin、CSRF、`Idempotency-Key`、强 `If-Match: "vN"`；唯一 `application/json` Content-Type、严格空对象 `{}`、最多 2 MiB。拒绝重复 JSON 键、未知字段、查询参数、弱/多个 ETag、非正版本号。URL 提供目标版本，不接受正文或策略覆盖。

成功：200，`data` 仅含 `prompt_template_id`、`version_no`、固定 `ACTIVE`、首次 `etag`；外层 `trace_id` 是本次请求，Header 有 `Cache-Control: no-store` 与首次 ETag。相同幂等键在当前身份/License 重验后返回首次不可变结果，不从根当前活动指针重建。错误：无权/不存在 404、许可 403、缺 If-Match 428、版本/状态/幂等冲突 409、当前签名清单未准入 422、依赖故障 503。

本次 Win11 合成签名清单及隔离 PostgreSQL 18 的 HTTP 链通过；正式审查/公钥/发行摘要、目标账户、Windows Server 2025、Debian 13、安装升级与 Gate3 未验证。公开生产装配必须继续满足 CR-AI-007 信任前置，不因 Router 存在而开放。
