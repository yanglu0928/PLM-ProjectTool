# SOL-06-A14-P01：StructuredSolutionSpec 送审前置核查

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVIEW_PRECHECK_PASS`；仅完成边界、冲突和实施顺序核查，不表示送审、评审或批准已实现。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A14-P01`|
|输入基线|Gate 2 冻结 `SOL_SPEC_SUBMIT_REVIEW`、DM-05 SOL-06、统一 Review Engine、Schema 0164、A13 类型化验证|
|前置任务|SOL-06 创建/详情/列表/修订/验证已在 Windows 11 完成真实 HTTP/Edge/PG 合成闭环；统一 PROJECT Review 已被 Requirement/Prototype 等 Owner 验证|
|涉及模块/实体|solution、review、trace、project、audit；SOL-06、RVW-01/RVW-02、TRC-01|
|涉及 API / 权限|冻结 POST `.../{spec_id}:submit-review`；仅 ProjectManager；Reviewer 为当前合格项目成员|
|验收标准|明确 Subject 身份、当前事实重验、版本锁定、终态消费、幂等/Audit、Schema 窄门和真实缺口|
|风险|信任旧 VALIDATE 报告；把执行结果作为送审前置造成死锁；Review 批准未原子写回版本；历史版或跨项目被送审|

## 核查结论

1. 统一 PROJECT Review 已具备创建、首轮启动、多人决定、SubjectSnapshot/Lock、Audit、持久幂等和终态回调；SOL-06 必须注册新的 Subject Owner，不新增第二套 Review 表或状态机。
2. Review 身份固定为 `SOL-06 / spec_series_id / structured_solution_spec_id`，策略为 `STRUCTURED_SPEC_ALL_V1`。`spec_series_id` 是逻辑 Subject，固定版本 ID 是 Round 的 `subject_version_id`；避免把每个版本误建成互不关联的 Review Subject。
3. 0164 仅允许完整 DRAFT 插入，所有 UPDATE 被 Guard 拒绝。后续必须用独立 Migration 打开 DRAFT→IN_REVIEW、IN_REVIEW→APPROVED/RETURNED 和旧 APPROVED→SUPERSEDED 的原子窄门，同时绑定现有 Review/Round FK；payload 和四类来源表继续永久不可变。
4. A13 的首次 Audit 是历史观察，Subject Owner 不得据此送审。必须在 Review 创建/开轮的同一事务、同一 SOL-06 series 锁内重建当前来源、设计检查、Artifact/Trace 和 latest DRAFT 身份；任一 FAIL/UNAVAILABLE 拒绝。
5. 当前 Trace 表允许 `SOL-06` shape，但现有 exact IMPLEMENTS 查询硬编码 `SOL-05`；需先扩展为受控 SOL-05/SOL-06 目标且由 Solution Owner 证明固定 Spec。非空 Artifact 仍因 OUT-02 Owner 未安装而关闭；空集合可继续明确 PASS。
6. 现有类型检查把试迁移执行/对账证明作为送审前置，和“先评审方案、后实施验收”冲突，导致 Migration 永久不可送审。已按持续授权建立 `CR-SOL-021`，选定设计就绪与执行证明分离；冻结路径/角色不变，报告代码采用新版本且不回写旧 Audit。
7. 送审只允许 ProjectManager；Reviewer 集合排序、锁用户并逐人重验当前项目成员资格。Review create/start、版本 `IN_REVIEW` 绑定、Snapshot/Lock、Audit 和 receipt 必须同一 UOW；客户端不能用通用 Review 两步调用替代。
8. APPROVED 终态在同一事务重验当前事实，当前版本转 APPROVED、同系列旧 APPROVED 转 SUPERSEDED；RETURNED/WITHDRAWN 映射 RETURNED。历史内容不覆盖，重放核对首次状态消费且不制造第二 Review。

## 实施顺序

- `SOL-06-A14-P02`：实施 CR-SOL-021 的版本化设计就绪类型检查合同与 evaluator；旧 Audit reason 反读保留。
- `SOL-06-A14-P03`：增加 SOL-06 固定目标证明与精确 ACTIVE `IMPLEMENTS` Trace 覆盖，并接入 evaluator。
- `SOL-06-A14-P04`：Migration 与 SOL-06 Review Subject Repository/Owner，完成开始/终态窄门和真实 PG 验证。
- `SOL-06-A14-P05`：原子送审 Service 与项目策略、Reviewer、收据/Audit、重放。
- 后续分别完成冻结 HTTP、Windows 组合、前端与 Edge/PG 验收，不在本任务提前装配。

本项为静态核查与正式变更记录；无程序、Migration、API、依赖、Secret、客户数据或外发变化。正式信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 和正式发行状态不变。
