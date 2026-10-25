# P06-P02 PlanVersion Review 终态 Owner 编码前检查

- 日期：2026-10-26
- 结果：`PRECHECK_PASS_WITH_CR_PLAN_009`
- 当前Phase/WBS：Phase 2 / `PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P02`
- 前置：P05-P05内部SubmitReview/Create/Start Owner；P06-P01 Migration 0200 `PASS_SCOPE_LIMITED`；CR-PLAN-007/008；Review统一 PROJECT 决定持久化服务。

## 编码前检查

|检查项|结论|
|---|---|
|模块边界|仅扩展内部 `PlanReviewSubjectOwner` 与Plan终态Repository/只读Proof；复用Review Transition服务、当前Project reviewer资格、Audit/Receipt/UoW。不挂公共HTTP、Review Registry、Windows UI或生产服务。|
|锁和当前事实|Review决定Owner先持Review根锁；Subject Owner再按既有Create/Start一致顺序锁Plan身份与PlanVersion集合，要求该Version仍为本Plan最新 `IN_REVIEW`、Review/Round/SubjectVersion完全绑定，正文指纹与送审固定Review快照相同。Approved时在该事务重证当前批准Solution及来源/覆盖，不复用历史Validate报告或AI建议。|
|批准|真实Review APPROVED终态之后更新新Version `IN_REVIEW→APPROVED`、插入0190结果；旧Plan Approved指针若存在，旧Version须依据它自己的不可变Approved Review Actor/Round改为`SUPERSEDED`并写对应0190结果；最后由0200允许指针与`lock_version+1`同事务更新。唯一Approved、事件、指针由Deferred闭环共同约束。|
|退回|Review真实RETURNED时新Version变为Plan状态`RETURNED`并新增0190结果；旧ApprovedVersion及指针保持不变。当前评审Reviewer资格按终态Owner准入规则重新核验，不把评审提交者/项目经理混同为决定人。|
|撤回|0190不包含撤回：真实Review WITHDRAWN若被记作RETURNED会伪造Review事实并被数据库拒绝；留在IN_REVIEW则无法重新送审。已经先记CR-PLAN-009，追加0210以真实WITHDRAWN事实表达PlanVersion的RETURNED处置；编码前先提交CR和本核查记录。|
|同事务及副作用|Review转移Owner负责Review/Round/Decision/Event、持久幂等Receipt与其Audit；Plan Subject回调在同一tx重证/消费终态，写PlanVersion状态、0190结果、批准指针（若批准）和Plan生命周期Audit。任一失败包含最终决定及Receipt在内整体回滚。独立Owner不自行commit或嵌套UoW。|
|回放/访问|历史幂等回放不重新消费终态；仍检查当前Actor/Project/License由外层Review命令执行，并以固定Review结果重新核对本Plan历史Version与Round绑定；丢失/不匹配/跨项目拒绝。|
|验收|单测覆盖Review类型/状态、Reviewer资格、Plan锁/最新Version、固定指纹、Approved与Rejected/Superseded路径、Withdrawn、幂等/审计及故障回滚。Win11 PG18组合需完成真实Review表/事件Start→终态、0190/0200提交闭环、Audit/Receipt原子性、wrong Actor/Round/no result/multiple Approved负例、Migration drift及有Review历史拒绝降级。全部PG Session/Auth/License/Project/来源Port替身必须披露。|
|明确不做|冻结API和HTTP、UI/Browser、公开Registry/Windows组合、真实客户签批/真实Source正向证明与Gate关闭均不属于本WBS。普通成功的合成Review不等同客户确认。|

## 决策/差异记录

原P06父级核查曾概括为“批准/退回/撤回”但0190实际仅含批准、退回及替代，本项发现其中撤回与数据库事件契约不兼容。该差异先登记为`CR-PLAN-009`，追加0210；不改写0190或0200，不伪造退回事实。来源当前事实通过现有`PlanVersionValidationService.evaluate_snapshot_in_transaction`纯只读入口重算；现有DRAFT专用`PlanVersionReviewReadinessService.prove_in_transaction`不得原样调用终态状态。

TraceLink：Gate 2 Plan/API冻结 → CR-PLAN-007/0190 → P05-P05 Start Owner → CR-PLAN-008/0200 → P06-P01 → CR-PLAN-009/0210 → 本P06-P02 → 后续Registry/HTTP/Windows/浏览器与正式信任/UAT。

## 下一项

先实现CR-PLAN-009 Migration 0210与其数据库闭环，再实现/验收P06-P02 PlanVersion终态Subject Owner；不挂外部入口，不宣称Gate/Pilot/客户批准。
