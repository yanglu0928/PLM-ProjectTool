# A06-P05-P06-P03 PlanVersion Review Registry / Windows 显式组合前置核查

- 日期：2026-10-26
- Phase：Phase 2 Platform Core
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P03`
- 前置：P06-P02 `PASS_SCOPE_LIMITED`；CR-PLAN-009 / Migration 0210；统一Review Registry、Windows PROJECT Review composition、PlanVersion validation evaluator。
- 结果：`PRECHECK_PASS_WITH_COMPOSITION_REQUIREMENTS`

## 编码前检查

- 输入基线：Gate 2冻结Review/API；CR-PLAN-007 0190、CR-PLAN-008 0200、CR-PLAN-009 0210；P05创建/Start Owner、当前Readiness proof、P06-P02终态Owner。
- 涉及模块/实体：Review `ProjectReviewSubjectRegistry`、PROJECT Review/Round与既有权限/License/Audit/Receipt；Plan `PlanVersionReviewSubjectOwner`、Plan/PlanVersion/ReviewStateResult/Approved pointer、当前验证报告与Approved来源。
- API：本片不新增或改动API契约；仅把PLN-02 Owner加入既有显式PROJECT Review composition。当前冻结通用Review Create/Start routes仍由现有命令校验Project Manager、Session/CSRF/Origin、License及Subject当前事实。
- 权限：终态Owner复核当前Project成员/Customer confirmer身份；批准时在同一事务重评当前不可变版本来源/校验；withdraw仍要求Project Manager。所有Review/Plan变更、Audit与Receipt位于同一事务，Registry未知Subject fail-closed。
- 预期修改：Windows PlanVersion composition、Windows PROJECT Review composition/production_login显式挂载；根默认模式维持既有关闭态；组合测试与本前置/结果记录。
- 验收：真实Win11 PG18.6完整迁移及显式组合回归批准/退回/撤回、指针唯一性、当前来源Proof失败关闭、Scope隔离、重复Subject注册失败、default/login-only不挂载。不得以Mock证明正式信任或Gate通过。

## 风险与决定

Registry现有Review composition直接面向通用PROJECT Review命令。Owner注册后通用Review API也会调用它；因此必须保持通用命令的Project Manager策略，并由Plan Owner在Create/Start/terminal阶段分别锁定固定版本与当前Proof。不能只增加owner到注册列表便宣称可用。

Plan终态批准需要当前来源Evaluator。现有Windows PlanVersion组合已构建`PlanVersionValidationService.evaluate_snapshot_in_transaction`及相同Source Proof图，应复用，不能另实现一份Solution/Requirement当前事实核查。Session、License、Authorization拒绝必须失败关闭。

PROJECT Review router只由ProductionLogin组合函数调用；编码前已核对调用位于显式平台Write组合路径。保持普通默认/login-only应用不挂载，并不改变冻结API合同。

本片限定为已验收Plan Owner注册进显式Windows PROJECT Review组合，复用当前ValidationService evaluator；不增加专用SubmitReview route、不改公共API/角色/许可、不放宽默认模式、不出客户网络。当前无需新CR。下一步实现组合注册/依赖复用并做定向合同及Win11隔离PG18验收。
