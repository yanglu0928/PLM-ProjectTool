# AI-04-A06-P04-P05 下游 PlanRef 绑定

日期：2026-10-03；状态：`PLAN_REF_BINDING_PASS`；依据 CR-AI-016、DEC-731/740。

AI_TASK 的授权、任务、授权快照和执行 Grant 现被同一个不可变 Content Plan 串联。授权创建要求 Preview 已有非空 PlanRef；Task 创建同时把该引用写入 Task 与授权快照；执行前置和 Grant 签发在同一当前事实读取中要求 Task、快照和当前授权引用完全一致。Grant 指纹包含 PlanRef，内容加载还必须按该精确 Plan ID 取回计划，不能只凭载荷摘要或来源摘要近似匹配。

旧 NULL 历史仍可读取和撤销，但不能新建 AI Task、签发执行 Grant 或通过执行前置。非 AI Egress 操作不受影响。公开 URL 和响应投影不增加 PlanRef，正文、Prompt、参数、storage locator 与 Secret 仍不进入响应、日志、Audit 或持久化 Plan。

Windows 11/PostgreSQL 18.6 真实 ASGI/数据库验证完成 Preview 201 与重放、Authorization 201、Task 202 与重放、License 403、旧请求 400，并证明 Preview Plan、Authorization、Task 与授权快照的 PlanRef 完全一致，执行前置通过且 Invocation 为 0。定向 33 项及后端全量 **2209 项通过、3 项既有条件跳过、无失败**。开发 wheel SHA-256 `0500de4bb38f766103ae0980fa83c0232424a362ca4d6e588c4d2c0fc5bd6338`。

兼容/升级/回滚：复用 Schema0072 已有可空不可变列，无新 Migration、依赖、冻结 URL/响应或 Provider 外发。升级后新 AI_TASK 链强制完整 PlanRef；旧 NULL 历史不回填。应用回滚只能停止新 AI_TASK 执行并保留已有 Plan/引用历史，不能恢复对客户端摘要的信任。当前尚无生产 Invocation 写入器，因此本项只把精确 Plan ID 带到 Grant 并为未来 Invocation 持久化建立失败关闭前置，不宣称 Invocation 行绑定已完成。下一项 `AI-04-A06-P05-P01` 核查并实现 Invocation 生命周期与持久化边界。
