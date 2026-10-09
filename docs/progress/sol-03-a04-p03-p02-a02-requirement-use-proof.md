# SOL-03-A04-P03-P02-A02：OutlineVersion 固定 RequirementVersion 当前批准证明

日期：2026-10-09。结果：`SOL_03_A04_P03_P02_A02_REQUIREMENT_USE_PROOF_PASS`；仅 Requirement 内部证明，目录版本写仍关闭。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A04-P03-P02-A02。
- 输入基线/前置：Gate2 DM-05/API-04、CR-SOL-002/016、Requirement 已有当前批准版本数据库端口、SOL-03-A04-P03-P02-A01 Section 稳定身份端口。
- 单一问题：目录固定 RequirementVersion 时，须在调用者事务内证明其同项目、当前批准、根 ACTIVE、版本 APPROVED 且有 Review 引用，不能直读 Requirement 内部表或依赖旧快照。
- 模块/实体/API/权限：Requirement Application 新增目录用途最小接口，复用其已有 Prototype 当前批准版本证明端口；不改变 Requirement 数据、角色、Schema/Migration 或公开 API。Owner 需先执行 Project 授权，本接口不作为客户端读取入口。
- 验收：同项目当前批准正例、跨项目/错版本/批准指针撤回/归档/端口故障失败关闭；真实 PG 根行锁与全量回归。风险：仅证明 Requirement 当前性，不替代 OutlineVersion 的计数、Trace、幂等/Audit 和正式 Review。

## 实施与验证

`OutlineRequirementUseProofService` 对已有 Requirement-owned 共享锁证明做严格身份/Review/摘要校验，只返回版本标识、编号、摘要及 Review 身份，不泄漏 Requirement 正文。定向 3 项/4 子例通过；Win11 隔离 PG18.6 合成 Requirement 的同项目、跨项目、旧批准指针、归档与 `FOR UPDATE NOWAIT` 根锁验证退出 0。后端全量 3435 通过/3 跳过/5243 子例，保留既有 2 条告警。

兼容/回滚：无数据库、公开 API 或依赖变化；撤去尚未接线的目录用途接口即可回滚，Requirement 历史不动。下一项 `SOL-03-A04-P03-P03` 组合 OutlineVersion Owner：原子固定有序 Section/Requirement/Reference、声明、现时证明、幂等/Audit 与 SQL 写 Guard 受限解锁。Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-002/016 → Requirement 当前批准端口 → 本目录用途接口 → OutlineVersion Owner。
