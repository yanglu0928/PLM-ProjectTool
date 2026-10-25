# TRC-01-A08-P03：Trace supersede HTTP 前置核查

日期：2026-10-02；Phase 2；结果：**PRECONDITION_BLOCKED，转同事务三字段解析 P04**。P02 仅内部 PM 命令已在隔离 PG18 通过，不等于冻结公开请求可直接接线。

冻结 API-02 的 `ResourceVersionRef` 公开形状只有 `resource_type/resource_id/version_id`，不允许客户端提交 `owner_module`、Scope 或 ProjectId。现有 `SupersedeTraceLink.replacement` 是可信内部 `TraceEdgeShape`，包含已解析 Scope/Project；`DocumentVersionTraceOwner.resolve` 可以证明三字段引用，但必须使用命令自身事务和当前 Session/License。若 HTTP 先开另一个事务解析再调用现有 Service，旧边锁、Document 版本锁和新边提交并不处于同一事务，资料/权限变化可发生在两步之间，违反 P01 的原子证明与冻结安全协议。直接让客户端填写内部 Scope/Owner 则破坏冻结合同；不允许这两种绕过。

P04 只补 Trace 内部“原始三字段边 → 当前调用方事务下 Owner 解析”的窄 Port/命令入口，保留原内部已解析入口和相同状态/权限/收据语义。解析必须由注册 Owner 对每个端点同事务给出可信 Scope/Project，并拒绝未注册类型/跨项目/变化后的失效版本；Receipt 指纹应取冻结三字段输入而非推断字段，同 Key replay 不可被失效端点挡住，但必须重验当前 License/Session/PM/旧边归属。若设计要求改变既有状态命令或冻结请求，再单独登记 Change Request；不静默扩字段。

本项仅静态核查冻结 API、Trace Owner/Service/事务边界；无代码、Schema、API、数据或依赖变更，无新业务测试。默认及 Windows 正式组合的 supersede 路由均不存在；关系 Owner 身份、正式目标账户信任、Server2025/Debian、Gate 3/UAT/可用发行包均未通过。P04 完成并验真实 PG 后才考虑可选 HTTP 的 P05。
