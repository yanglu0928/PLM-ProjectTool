# AI-03-A04-P03-A03-P01：PromptVersion 创建版本可选 HTTP 合同

版本：0.1.0；日期：2026-10-02；状态：Win11 合成 HTTP 合同 PASS；隔离 PostgreSQL 整链/生产装配未验。

依据：冻结 API-03 的 `AI_PROMPT_CREATE_VERSION`、已完成内部原子增版与 CR-AI-007。新增可选 POST Router 和 `create_app` 注入口，默认应用无路由。Origin/Session/CSRF、幂等键、强 If-Match、严格 JSON/重复键/总大小及路径/查询边界按 [运行时补充](../api-contract/ai-prompt-create-version-runtime-v1.md) 验收；返回仅版本元数据和 Hash，重复请求可使用原结果 trace_id 但响应外层 trace_id 属于本次请求。HTTP 层重算规范 Draft 指纹/正文 Hash/策略引用，与内部结果一致才投影，防止错配快照被报告为成功。

Changed/Files：AI 可选 HTTP Router、`create_app` 可选注入口、合同测试、API 补充、决策/本进度/状态。Migration：无。API：实现冻结路径，无 Breaking Change；当前生产仍未挂载。兼容/升级：默认应用 404 不变；仅显式注入 Router 增加功能，撤回 Router 可恢复原行为。版本说明：开发版 `0.1.0.dev0`，无数据库升级需求；生产可用性仍由正式信任锚/目标账户/整链验收约束。

Tests：合成 HTTP 定向3项通过，覆盖默认404、201最小响应/ETag/Location/同 Key 历史 trace 重放、Origin/Session/CSRF/If-Match/幂等、未知/重复 JSON 字段与2MiB边界、服务错误映射、结果错配503；后端全量2082项通过、3项既有跳过；开发 wheel 构建通过，SHA-256 `148a6b3210c14706ef3ca68817ceab9a40e0f5987900d0eaddc6c330b844cf39`。Golden Dataset 未运行：无模型推理。

Known Issues：尚未将真实 PG Session、审计/收据与签名准入串入 HTTP 整链；正式密钥/人工审查及生产装配未验，不能标 Gate3/可用包 PASS。Next：`AI-03-A04-P03-A03-P02` Windows 11 隔离 PG18 合成 HTTP 整链与重放/拒绝验证。
