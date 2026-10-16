# SOL-03-A04：OutlineVersion CREATE Owner 编码前检查

日期：2026-10-09。结果：`SOL_03_A04_OWNER_PRECHECK_DEPENDENCY_IDENTIFIED`；只完成前置与 CR，正式 Owner 写仍 `PRECONDITION_BLOCKED`。

|检查项|当前结论|
|---|---|
|当前 Phase/WBS|Phase 2 Platform Core / SOL-03-A04|
|输入基线|Gate2 冻结 DM-05/API-04、CR-SOL-002、0137/0154、REQ-01 当前批准来源证明、SOL-04 Section 身份、SOL-01-A16 当前资格|
|前置任务|A03 封闭 ReferenceVersion FK/计数/Guard 已通过；当前 Owner 所需 GLOBAL 项目使用证明未具备|
|涉及模块/实体|Solution OutlineVersion、Section 身份、ReferenceRoot/Version/Eligibility，RequirementVersion；Document/Evidence/Review 仅经 Application Interface|
|涉及 API|冻结 `SOL_OUTLINE_VERSION_CREATE` 为 201 DRAFT，GET/VALIDATE/Review 独立；本项不开放路由|
|涉及权限|ProjectManager/ImplementationMember 受权创建；PROJECT 同项目；GLOBAL 参考可被项目使用但不得授予项目用户全局管理员或文档浏览权限|
|验收标准|同事务当前性/来源/计数/有序固定引用、持久同号首响、Audit 回滚与并发、SQL Guard、权限/异常/PG/全量测试；本前置仅识别可复用证明与缺口|
|风险|直接复用 GLOBAL 管理员资格命令会拒合法角色；仅信历史合格状态会接受撤回或过期来源|

## 证据与决策

1. 0154 已支持固定 ReferenceVersion 关联，但 0137/0154 仍拒目录版本 DML；Schema 不证明当前合格。冻结 `SolutionOutlineVersionInput` 必须含有序稳定章节、已批准需求、合格参考及缺失/冲突声明，CREATE 不等于 VALIDATE/Review。
2. Requirement `SqlAlchemyPrototypeApprovedRequirementVersionProof` 已能在调用者事务内锁定同 Project、当前批准指针及 Review；可设计经 Requirement Application Port 复用，但需为 Solution 用途建立明确接口边界。
3. Section 当前读 Repo 有根/批准指针一致性检查；目录 DRAFT 固定的是稳定 Section 身份，正式输出仍需明确 Approved SectionVersion。不能把 Section 身份误称已批准正文。
4. Reference `SqlAlchemyReferenceEligibilityRepository.current()` 锁定 Root 当前版本并读固定文档/Evidence 集合；原资格命令的 GLOBAL `qualify()` 要求当前调用者是管理员，不能直接用于项目角色。CR-SOL-016 已在编码前登记服务端最小现时证明替代。
5. `ProjectAuthorizationService` 尚无 `SOL_OUTLINE_VERSION_CREATE` 操作策略；也没有目录版本的持久首次 201 响应快照。必须在 Owner 开写之前分别补权限/结果与受限 Guard 计划，不能只改路由或关闭触发器。

## 后续顺序

先实现并验证 `A04-P01` 当前合格 Reference 项目使用证明（PROJECT/GLOBAL，Opaque、不提权、不外发正文）；再为 Owner 补认证/Project 权限、Section/Requirement 当前证明、不可变首次结果、受限迁移 Guard/审计并在隔离 PG 验证。再独立接 HTTP、Windows 显式组合、前端/Edge、VALIDATE/Review/Trace/Workflow。前置未满足前停止 A04 Owner 编码，可继续 P01 证明工作。无本次产品代码/Schema/API/依赖变化；未运行新测试。Gate3 仍 BLOCKED。
