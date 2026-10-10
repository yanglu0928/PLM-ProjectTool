# AI_PROMPT_RETIRE 运行时补充（非冻结合同改写）

版本：0.1.0.dev0；日期：2026-10-02；依据冻结 API-03、CR-AI-009、DEC-692/694。路径仍为 `POST /api/v1/admin/ai/prompt-templates/{prompt_template_id}:retire`，仅可选 Router；默认登录和只读组合不挂载，Windows `--platform-write` 显式写组合装配。

请求：DeploymentAdmin Session Cookie、受信 Origin、CSRF、`Idempotency-Key`、强 `If-Match: "vN"`；唯一 `application/json` Content-Type、严格空对象 `{}`、最多2MiB。拒绝重复 JSON 键、未知字段、查询参数、弱/多个 ETag。URL 指定模板，不接受 Prompt 正文或退役策略覆盖。

成功：200，`data` 仅含 `prompt_template_id`、固定 `RETIRED`、首次 `etag`；外层 `trace_id` 属本次请求，Header 有 `Cache-Control: no-store` 与首次 ETag。原幂等键在当前身份/License 重验后返回0062首次结果，不从当前根推断历史。退役前旧活动版本仅作内部历史引用，不在响应标为活动。错误：无权/不存在404、许可403、缺 If-Match 428、版本/状态/幂等冲突409、依赖故障503。

本次仅 Win11隔离PG18/合成 Session和License链通过；正式发行信任/目标账户、Server2025/Debian、安装升级、Gate3/UAT未验。Router存在不代表生产可用。单向退役不需要 Prompt 内容签名清单；增版/激活仍需要正式准入。
