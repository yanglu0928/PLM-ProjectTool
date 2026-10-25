# PLAN-02-A04-P04-A04-P03-P04-S03-P03：PlanVersion DRAFT 聚合 Owner 前置核查

日期：2026-10-26。结果：`PRECHECK_ADJUSTED / APPEND_GUARD_REQUIRED`；无代码或业务数据变化。

## 编码前检查

|项目|结论|
|---|---|
|Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P03-P04-S03-P03`；完成内部PlanVersion CREATE原子聚合Owner|
|输入基线|Gate 2冻结DM-05/API-04；CR-PLAN-002/003；Migration 0187；S03-P01输入模型；P03 Approved Solution只读证明|
|前置任务|Plan身份Owner、严格快照输入、0170～0187关闭式Schema与当前批准Solution证明已具备；S02/P02均PASS_SCOPE_LIMITED|
|涉及模块/实体|Plan application/repository；PlanVersion、所有WBS及其requirement/solution/prototype/evidence refs、dependencies、milestones、conditions、roles、exclusions；Project授权/Review/License/Audit/Idempotency|
|涉及 API|本片仅内部Service，不挂载HTTP；冻结 `PLAN_VERSION_CREATE` 的API/Windows Router另立任务|
|涉及权限|PROJECT_MANAGER、IMPLEMENTATION_MEMBER；同事务重验Session/CSRF、Project ACTIVE、成员/操作角色与License；当前批准来源和所有可变指针须锁定或并发重查|
|验收标准|完整不可变快照单事务写入、跨表失败全回滚、强指纹幂等、Audit exactly-once、Approved来源和责任成员证明、固定引用完整性、output fail-closed；实际PostgreSQL并发/拒绝/回滚|
|风险|已有Plan tables都被数据库guard无条件拒绝DML；直接移除会破坏不可变历史。子表仅插入不等于来源/Review批准。Prototype FK仅证明Project归属，不能证明当前Approved。|

## 编码前结论与范围调整

- 0170/0171/0172/0173/0174/0175/0176及0186/0187的owner functions均为无条件 `RAISE EXCEPTION`；现有实现没有可复用的Owner installation migration。PlanVersion repo不可能成功插入。
- 已登记 `CR-PLAN-004`：新增0188将写guard改为仅允许INSERT并拒绝UPDATE/DELETE，保留所有独立no-TRUNCATE guard；迁移降级恢复拒写但保留历史。Owner与0188必须一并交付，不先开放孤立写入口。
- 按API-04，创建仅产生DRAFT版本，不移动Plan current-approved pointer。写事务须使用现有权限/License/Audit/receipt模式；`ApprovedSolutionInputProofService`须消费在同事务中锁定/复核过的来源视图，不能把只读证明当成竞态安全。
- S03-P03 实施分为两片：P03-A01完成0188 append-only guard转换及PostgreSQL行为负例；P03-A02消费P01模型/P02 schema实现Application Owner + SQL全聚合写入、幂等与Audit/rollback。两片都不挂HTTP。
- 影响：仅内部Plan写入栈，新增revision 0188；冻结API/授权范围/业务语义无变更。若0188验证失败，保留无条件关闭触发器与所有原代码。

## 实施拆分状态

P03-A01已按CR-PLAN-004实现并在Windows 11 / PostgreSQL 18.6隔离库验证，见 `docs/progress/plan-02-a04-p04-a04-p03-p04-s03-p03-a01.md`。下一项：

`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A02`：建立事务型PlanVersion DRAFT聚合Owner；在0188 append-only数据库门上实现授权/来源复核、完整快照原子写入、幂等与Audit/整体回滚的内部Owner验证。不得单独部署0188。Pilot/Gate/Release不变。
