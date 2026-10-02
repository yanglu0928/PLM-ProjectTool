# AI_PROVIDER_CREATE 实现增量（冻结合同不变）

版本：V1；日期：2026-10-02；实现任务：`AI-01-A03-P03-A02`。本文件仅细化 Gate 2 已冻结的 API-03 `AI_PROVIDER_CREATE`；不更改路径、角色、控制或结果语义。

`POST /api/v1/admin/ai/providers` 仅在显式注入创建 Router 时存在。请求需可信 Origin/Host、当前 `plm_session`、`X-CSRF-Token`、16～128可打印ASCII字符的 `Idempotency-Key`，`Content-Type: application/json`。JSON 必须且只能包含：`kind`、`display_name`、`endpoint_policy_ref`、`secret_ref`、`data_region`、`egress_class`、`capabilities`。`secret_ref` 为 canonical lowercase UUID；`capabilities` 为非空、不重复的冻结枚举数组。正文最大8192字节；重复键、未知字段、API Key/Secret 明文、原始 URL、异常浮点值和多余 query 均拒绝。

成功返回 `201`、`data: ProviderView`、`trace_id` 与同值 `X-Trace-Id`，并带 `ETag: "v0"`、资源 `Location`、`Cache-Control: no-store`。只返回受控端点策略、区域、外发类别、能力、固定遮罩 SecretRef、状态/配置版本/ETag；不回显 Secret 全值、密文或供应商内部响应。Provider 初态仅 `CONFIGURED`，创建不执行连通性测试、激活、AI 调用或客户数据外发。同一 actor/key/规范化 payload 返回原始首版响应；同 key 异载荷409。

错误按冻结 Envelope：格式400、会话401、CSRF403、无管理员权限404、License403、幂等冲突409、输入422、不可用 Secret/Provider503。默认应用与当前 Windows 平台组合未挂载此写 Router，返回404；待后续正式组合任务验证后才开放。
