# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P03-P03：PlanVersion Validate事务Owner编码前核查

日期：2026-10-26。状态：`PRECHECK_COMPLETE`；仅本项实现前静态核查。

## 编码前检查

- 当前Phase：Phase 2 Platform Core。
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P03-P03`。
- 输入基线：冻结API-04 `PLAN_VERSION_VALIDATE`、CR-PLAN-006与0189、A06-P02纯报告评价器、当前Session/License/Project授权、PlanVersion读取和Approved Solution输入证明Owner。
- 前置任务：0189已在Win11隔离PG18迁移验收；本表不独立部署。已有只读完整快照重建和项目写Owner基础设施。
- 涉及模块：Plan Application/Infrastructure、Project Authorization、Access/License、Solution Proof、Audit与IdempotencyReceipt；Windows显式内部组合；不含API router。
- 涉及实体：不可变PlanVersion/WBS聚合、当前Outline/Section/StructuredSpec与Requirement范围、AuditEvent、0189首次报告快照、通用幂等Receipt。
- 涉及API：无HTTP；提供内部命令/服务，不扩大公开入口。
- 涉及权限：有效32字节Session/CSRF、License、ProjectManager或ImplementationMember当前写操作权限；新操作需在项目授权注册表显式增加`PLAN_VERSION_VALIDATE`，其余角色拒绝。
- 验收标准：单UOW内授权重核、锁定指定Project/Plan/PlanVersion快照、当前Approved来源/覆盖证明、确定性报告生成、Audit/报告行/Receipt原子提交；同Actor/Project/Key/同目标重放返回首次完整字段和时间，不同目标冲突；Audit/结果/收据任一失败整体回滚；许可/撤权/跨Project拒绝；无状态迁移；default app不开放。
- 风险：来源证明失败是报告阻断事实而非验证操作故障，应安全投影固定问题码；18xx结果Report不可变且Audit触发器要求目标身份吻合。不得在重放时重跑当前来源证明或静默更新已存报告。

## 前置结论

- `SqlAlchemyPlanVersionReadRepository.get_current`对目标PlanVersion root持`FOR SHARE`并在同事务读取全部Owned rows，固定快照可用于串行化验证；快照按JSON-like字段映射回严格typed input。
- `ApprovedSolutionInputProofService`可重验当前批准指针/Review/Coverage/Section/Spec；Plan SourceProof另复核精确Requirement/Solution映射。仅Server当前证明能作为coverage scope，不接受客户端传入范围。
- 0189结果表以AuditEvent id为主键，通用Receipt引用同一ID；因此可在UOW中先写Audit、再插结果、最后完成Receipt，若任一步失败事务不提交。重放按当前actor/Project权限重验、锁定版本后从receipt audit id加载同范围不可变报告。
- 未发现需要再次调整CR-PLAN-006/冻结API或Schema的差异；本项只实现其受权事务Owner。公开HTTP与Windows安装组合留待后续独立WBS。

## 交付边界

- 本记录无代码/API/Schema/业务数据变化；无数据库迁移或外发。
- 下一项完成后接独立Validate HTTP合同与隔离PG验证；Gate/Pilot/正式Release尚未通过。
