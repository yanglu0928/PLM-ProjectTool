# CR-SOL-024：SectionVersion 独立 Review 生命周期受控开放

日期：2026-10-23。状态：`APPROVED_FOR_IMPLEMENTATION`（依 CR-EXEC-001 持续授权；逐片客观验收前不标 PASS）。Gate 2 原冻结提交 `64cdf09`、CR-SOL-003/022/023 及已批准的 SOL-06 Review 历史均保留。

## 来源、冲突与目标

冻结 DM-05/API-04 明确 SOL-05 SectionVersion 独立 Review、`SOL_SECTION_VERSION_SUBMIT_REVIEW`、固定内容/Trace/Spec、通过后指向批准版本；AI 章节在人工评审前保持 DRAFT。当前 P12-P05-P04 已在 Win11 一次性库证明六维 `ready_for_review=true`，但没有 Section Review Subject/提交/终态 Owner。0160 的 `guard_solution_section_version_foundation()` 拒绝所有 UPDATE；0148 的 `guard_solution_identity_foundation()` 也拒绝 `sol_sections` 指针 UPDATE。直接用验证 Audit 或裸 SQL 更新为 APPROVED 会绕过统一 Review 与版本/指纹窄门。

## 方案比较与选择

- A（选择）：复用统一 PROJECT Review Engine 和现有 SOL-06 的创建/轮次/终态编排模式，为 SOL-05 增加独立 Subject Owner、同事务现时六维送审准备证明、受控生命周期 Guard 与不可变首次结果。`DRAFT→IN_REVIEW→APPROVED/RETURNED`；新批准版可将同 Section 旧批准版置 `SUPERSEDED` 并原子移动指针。终态必须校验精确 Review Identity/Round/版本内容指纹与分配客户确认人全部决定；AI/程序不代签。
- B（拒绝）：把最后一份 `ready_for_review=true` 验证报告直接转 APPROVED。报告只是某个时点的送审准备，Trace/Spec/Document/项目状态可能已变，且没有客户 Review 决定。
- C（拒绝）：让 Outline Review 一次性批准全部章节。冻结模型明确 Outline 与 Section 独立 Review，且每个正式输出固定批准 SectionVersion。

## 基线差异、迁移与回滚

这是为已冻结业务规则补齐施工时序，不新增 Scope 或 Breaking API。原 SectionVersion 内容、固定子集合和首次 201 不变；仅受控状态/Review 双引用及 Section 当前批准指针可以迁移。独立迁移需在原 0160/0148 Guard 上加严格状态边、不可变内容字段、同项目同主体 FK/Review精确绑定、先前批准版替代与提交闭合结果；不能静默解锁任意 UPDATE/DELETE/TRUNCATE。新 Review 历史存在时拒绝回降，不删除客户意见；停入口并前滚修复。若需额外持久结果表，另片ORM+迁移完成空库/历史库升降、head drift、非法DML/并发负例。

实施顺序：P13-P02 现时送审准备只读 Owner；P13-P03 Review Subject/受控状态Schema；P13-P04 Subject+提交服务；P13-P05 可选HTTP/Windows真实PG与终态客户模拟流程；P13-P06 前端/浏览器；然后 Outline Review/Plan。每片维护原权限：ProjectManager 发起、指定 1～N 当前合格客户确认人、统一 Review Engine 记录客户决定。`ready_for_review`不是批准，合成账户/决定只作内部验收。

P13-P03按DEC-20261023-1208再拆为P01“封闭、不可变结果历史表”与P02“受结果闭合约束的状态/指针Guard”；P01不允许任何新Review写入，也不把Schema存在当正式评审能力。原冻结版不追写。

## 验证与剩余风险

送审前同事务重采样六维事实，不复用旧 VALIDATE 收据；终态批准前重证现时资料/权限/固定版本与 Review 快照；退回意见必填、任一退回则轮次退回、历史永久保留。Win11/PG18 真实 Session/角色/跨项目/License/Trace撤销/Spec替代/Document失效/重放/并发/Audit/回滚、全量后端和前端/浏览器分层验收。正式客户签署、正式信任、Gate 3、Pilot/Release 均不因代码实现预先通过。
