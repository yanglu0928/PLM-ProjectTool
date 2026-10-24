# AI Task 提交选项 V1 增量合同

日期：2026-10-03；WBS：`AI-05-A06-P01`；依据 CR-AI-021。此文新增辅助 GET，不改变冻结 API-03 写接口。

`GET /api/v1/projects/{project_id}/ai-task-options`，控制 `S,L`，仅 ProjectManager 与 ImplementationMember。响应 `200 data={task_policies,egress_policies,routes}`，`Cache-Control: no-store`；无查询参数、无分页，最多 64 个 Task Policy、部署 Egress Policy 与 200 条路由候选。

- `task_policies`：reference/version、task_type、purpose/output/context refs，以及参数名、类型、必填性、长度/数值/枚举约束；不返回 Prompt Template ID 或正文。
- `egress_policies`：reference、数据类别、记录/字节/Token/重试上限、风险码和 TTL；不表示已经授权。
- `routes`：Provider/Model ID、显示名、region、model key/revision；只包含当前 ACTIVE Provider、AVAILABLE 结构化 CHAT Model 与部署执行白名单交集。

响应不得含 endpoint URL、endpoint policy ref、egress class、SecretRef、API Key、Prompt内容或客户内容。无权/跨项目为404，会话401，License403，配置或投影异常503。路由为空是有效状态，前端必须关闭提交而非允许手填。
