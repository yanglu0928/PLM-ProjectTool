# AI-04-A06-P04-P04-A05 AI_TASK Preview HTTP 合同

日期：2026-10-03；状态：`CONTRACT_PASS`；依据 CR-AI-016、DEC-731/737/738。该切片实施已登记的 `/api/v1` AI_TASK 请求收紧；响应 URL、状态码和安全投影保持不变，生产 Windows 组合与真实 HTTP/PG 链留 A06。

POST `/api/v1/projects/{project_id}/egress-previews` 现在按 `operation_type` 使用互斥请求形态：

- `AI_TASK` 必须提供精确 `ai_task_plan`，包含 `task_type`、`prompt_policy_ref`、`output_schema_ref`、`context_policy_ref` 和最多16个标量 `task_parameters`；禁止提交 `estimated_record_count` 与 `payload_fingerprint`。
- `RETRIEVAL_RUN/INDEX_BUILD/INDEX_REBUILD` 保持原字段，必须提交客户端已有的 `estimated_record_count/payload_fingerprint`，不得提交 `ai_task_plan`。
- 两种形态都保持严格字段集合、重复键拒绝、UTF-8/大小上限、Session/CSRF/Origin/幂等 Key 与安全错误映射。

这是 CR-AI-016 已批准并记录的有意兼容收紧；尚无正式发行依赖旧 AI_TASK 请求体，前后端将在同一发布切片升级。旧冻结 API 文件和提交 `64cdf09` 不回写；变更通过 CR、决策日志、进度和版本说明追溯。

验证：合同6项覆盖默认关闭、AI_TASK新形态、非AI旧形态、安全响应、额外/缺失/嵌套字段、大小写错误摘要、查询参数、Origin/Session/CSRF、幂等/业务错误映射；后端全量 **2205项运行、3项既有环境跳过、无失败**。开发 wheel SHA-256 `e424ed47c2fc910205d5c0878741c89eee130ff86754b9c68fdbc9c37c895c0a`。无 Schema、依赖、Provider调用或客户数据外发。

回滚只能与未发布客户端一起原子撤回；不得在服务端静默接受旧 AI_TASK 客户端摘要。下一切片 A06 装配 Windows 生产路由的真实 Task Policy、Prompt Owner、Document Owner、Plan Builder与Repository，并执行真实 HTTP/PostgreSQL 组合验证。
