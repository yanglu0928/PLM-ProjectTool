# PRT-01-A11-A05-P04-P08：Requirement 验收标准稳定引用重复读取前置核查

2026-10-08 / 状态：`PRECHECK_COMPLETE_IMPLEMENTATION_PENDING`，生产入口与性能验收不变。

编码前检查：Phase 2；输入为 P04-P06 Requirement 表约16条查询/资格及 P07 Review 流水线无稳定收益；前置为已通过的单次完整范围扫描、当前批准 Requirement/Review/Prototype 隔离 PG/HTTP 正反例。仅检查 Requirement/Prototype Owner 边界和读取仓储，不改生产代码、API、Schema、权限或锁。目标是选择一个单一重复往返候选并列出等价性与安全验收；风险为把快照中的文字验收条目错误当成稳定的验收标准 ID，或失去“当前批准版本”失败关闭。

候选：`SqlAlchemyRequirementVersionValidationRepository.lock_snapshot` 已在同一事务读取并共享锁定 `RequirementAcceptanceCriterionRow`，但构造的 `RequirementVersionValidationSnapshot.acceptance_criteria` 只包含文字字段，不包含 `acceptance_criterion_id`。Prototype Owner 随后对每个当前批准 Requirement 再调用 `SqlAlchemyRequirementAcceptanceRefsProof.prove_current_acceptance_refs`，该方法另做当前根/版本 JOIN + `FOR SHARE` 和验收标准行读取/序号校验，然后仅返回 ID。两次读取有重叠，但后者还证明根 ACTIVE、指针当前、版本 APPROVED、Review 引用非空、验收标准数量/序号和 ID 唯一性；不能只删除调用或从文本推断 ID。

下一步仅在 Requirement Owner 内设计同事务返回稳定 ID 的内部证明：仍核对现有全部当前性条件、保持项目共享锁和版本/验收行锁、保留原公开 Port 行为；用调用计数证明实际减少往返，再跑缺失/重复/序号断裂/指针漂移/跨项目/撤权、完整后端及真实 PG/HTTP 20 并发网络复验。若增加内部 DTO 或修改共享仓储不可保持原合同，须先在 CR-PRT-005 记录差异、迁移/回滚和失败关闭方案，不能提前改生产。无当前升级操作；本前置记录可撤而不影响历史。

本项未测新网络 P95，也未重跑全量测试；P04 已有真实 Uvicorn 20并发约594/632ms依旧 FAIL。Prototype 正常生产入口关闭，Gate3和可用包仍未通过。
