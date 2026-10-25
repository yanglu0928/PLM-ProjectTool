# PLAN-02-A04-P04-A04-P03-P02：PlanVersion 当前方案来源 Owner 前置核查

日期：2026-10-26。结果：`PRECHECK_PASS / SOURCE_OWNER_MISSING`；未新增 PlanVersion 业务写入。

## 编码前检查

|项目|结论|
|---|---|
|Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P03-P02`；只解决 PlanVersion 能否取得 Outline/Section/StructuredSpec 当前批准固定来源的同事务证明。|
|输入基线|冻结 Gate 2 DM-05、API-04 `PLAN_VERSION_CREATE` 与 `PlanVersionInput`；0170～0177 Plan Schema；Pilot-Chain-A03；SOL-03 Outline与SOL-05 Section/Spec Review/coverage Owner。|
|前置任务|Plan身份、WBS/Dependency/Milestone/固定引用 Schema 与WBS只读Trace已完成；Outline/Section/StructuredSpec分别有当前事实、Review/覆盖证明。历史 Plan 前置中“没有Outline/Section审批链”的描述已被后续WBS取代。|
|涉及模块/实体|Plan application；PlanVersion及固定 OutlineVersion、SectionVersion、StructuredSpecVersion、RequirementVersion、Review/Trace投影。只读证明，不写 Plan/WBS。|
|涉及 API|本片不新增/修改 HTTP。验证冻结 `POST /api/v1/projects/{project_id}/plans/{plan_id}/versions` 的未来来源前置；引用集合使用固定version ID，不接受 current/latest。|
|涉及权限|未来调用者必须在同一业务事务内重验当前Session、ProjectManager/ImplementationMember、Project和License；跨项目/旧Session/失效License拒绝。来源Owner不得自行扩展调用者权限。|
|验收标准|对同项目现时批准的固定Outline版本，复核Outline来源与coverage；对完整精确的Section/StructuredSpec固定集合逐项复核当前批准指针、Review终态、Project/根身份和现时来源；缺失/重复/多余/陈旧/跨项目/未批准引用失败关闭；无DB/API变化。|
|风险|不能把Outline单独批准推成其Section已批准；不能把StructuredSpec单项批准推成整体方案批准；不能漏掉Outline覆盖证明列出的Requirement全集；不能用合成Owner输出直接作为生产业务事实。|

## 代码事实与决定

- Plan 当前只有身份创建/读取、Schema、WBS Trace读取；没有PlanVersion application create/source-proof Owner，现有PlanVersion/WBS子表仍是闭锁数据结构。
- Solution 侧已有 `OutlineVersionCurrentFactsService` 与完整 `OutlineCoverageProofService`，后者调用经授权的 Requirement Inventory、当前 Section 指针、Section Review/当前六维证明并返回精确 `section_version_ids`；Section 固定版本载荷包含 `structured_spec_refs`。
- 关键兼容边界：`OutlineCoverageProofService.prove` 当前仅接受 DRAFT `Validate` 或 DRAFT/IN_REVIEW 的 current-facts 查询，**拒绝 APPROVED Outline**。因此现有“Review前就绪证明”不能直接声称是PlanVersion当前来源证明；读取历史批准行或复用旧Audit也不够。Plan路径必须从 Outline当前批准指针 + Review终态 + 同事务覆盖重算开始。
- Section侧已有 `SectionStructuredSpecQualificationService` 重新证明Spec固定引用的当前指针/Review/来源资格。未来组合应通过窄Port复用这些正式Owner，不读写ORM、不复制完整资格逻辑。
- 选定分片：P02前置核查确认需要独立的已批准Outline来源证明，不可直接复用Review前Owner。下一项仅新增 Plan-owned 内部 `ApprovedSolutionInputProof` 及其聚合服务/窄Port：读取并锁定Outline current approved pointer、证明终态Review绑定、复算Approved Outline覆盖；覆盖Owner只能扩展到在同一事务证明Outline根当前指针及APPROVED状态的调用路径，不能放宽DRAFT/IN_REVIEW合法性。然后用其返回的精确SectionVersion集合与每个Section当前StructuredSpec资格组装固定方案集合。输入顺序/重复/多余/遗漏须严格校验并绑定fingerprint。该服务先由调用者在同一事务完成Session/Project/License授权；不写库。
- PlanVersion DRAFT原子创建、WBS/Dependency/Milestone写入、公开HTTP、UI/校验/送审/包内E2E属于后续独立WBS，不在此片顺手实现。

## 后续验证计划

下一 WBS `PLAN-02-A04-P04-A04-P03-P03`：在Plan application实现上述纯内部Approved来源聚合证明与独立负例测试，注入当前Outline根/版本/Review/Requirement inventory/Section current-facts/Section-Spec资格Ports；覆盖完整Approved集合、Outline指针漂移、终态Review错误、覆盖缺失、Outline批准但Section未批准、Spec陈旧/撤销、跨项目、重复/重排/增删引用、指纹不一致及事务失效。无HTTP/Schema/Migration。其后再进入PlanVersion原子写Owner与完整冻结请求载荷。

本项只读源码/合同核查，无功能测试；没有变更API/Schema、权限、业务数据或审批状态。Pilot/Gate/Release状态不变。
