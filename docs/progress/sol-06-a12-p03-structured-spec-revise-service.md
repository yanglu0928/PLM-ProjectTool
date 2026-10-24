# SOL-06-A12-P03：结构化专项独立修订 Service

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVISION_SERVICE_PG_PASS`；仅表示内部应用服务通过，不代表 HTTP、Windows 平台装配或用户界面已开放。TraceLink：冻结 `SOL_SPEC_REVISE` → A12-P01 修订语义 → A12-P02 受锁 Repository → 本项。
- 编码前检查：沿用 0164 完整不可变 DRAFT、当前来源证明、项目 Auth/License、通用幂等收据和 Audit；新增独立项目操作 `SOL_STRUCTURED_SPEC_REVISE`，仅 ProjectManager/ImplementationMember 可写。本项未更改冻结 `/api/v1`、Schema、AI/插件或 License 权益。
- 命令与绑定：客户端输入只含路径 `ProjectId + spec_id` 和 CREATE 同形的完整六字段快照；显式拒绝客户端提供 series/前驱。请求指纹绑定项目、路径版本和完整正文；Service 在系列锁内读取当前 base 后注入固定 series/前驱，且类型必须与系列一致。
- 首次执行：每次先验证 Session/CSRF、License 和当前项目角色；新 Key 才检查路径版本仍为系列最新、状态为 `DRAFT`/`RETURNED`/`APPROVED`，随后重新证明 Requirement、Section、Document 与 Evidence 来源，创建 replacement DRAFT，追加 `SOL_STRUCTURED_SPEC_REVISED` Audit 和 `V1_SOL_STRUCTURED_SPEC_REVISE` 首次 201 收据后统一提交。
- 重放：同 Key 在重新鉴权后直接重建并核对首次不可变结果；要求其前驱仍等于原路径 `spec_id` 且正文逐字段一致。系列后来新增更高版本时仍返回原 201，不重复来源读取、版本写入或 Audit；同 Key 改正文返回幂等冲突。
- 真实验收：Windows 11 可弃 PostgreSQL 18.6 上完成错误 CSRF、跨项目、License 拒绝、来源拒绝、同号双线程仅一次写入、异号同前驱竞争仅一个成功、后续版本产生后原结果重放、实施成员修订和 Audit 故障全事务回滚。目标系列 v1→v6 完整，独立修订收据和 Audit 各 4 条。
- 验证：定向 `18 passed / 807 subtests`；完整后端 `3656 passed / 3 skipped / 5762 subtests`；开发 wheel 1400 条目，SHA-256 `f8aae5b1ed141af10eef8be7e872ceb20c370cdc12bcba42e78350e97416eaff`，包含修订 Service。
- 兼容性/升级：无 Migration、冻结 API 字段、License 权益或依赖变化；既有 0164 数据无需升级。新增权限名尚未由公开 Router 调用。
- 回滚：可撤内部 Service 和新增策略；已写不可变版本、Audit 与收据必须保留。真实验收只使用验证器创建并清理的可弃数据库，未外发客户数据。
- 已知边界：默认关闭的 HTTP 合同、Windows 组合、前端和 Edge 尚未实现；正式服务账户信任、OutputArtifact、专项验证/送审、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 与正式发行仍未通过。
- Next：`SOL-06-A12-P04` 实现默认关闭的冻结 revise HTTP 合同与严格 201 投影，不接 Windows 生产组合。
