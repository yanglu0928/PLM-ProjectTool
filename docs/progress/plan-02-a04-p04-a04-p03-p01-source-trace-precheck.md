# PLAN-02-A04-P04-A04-P03-P01：PlanVersion 来源/Trace 一致性前置核查

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`PRECONDITION_BLOCKED`；未开放 PlanVersion 业务写入，也不表示 WBS 已可正式批准。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P03-P01`|
|输入基线|冻结 DM-05、API-04 `PLAN_VERSION_CREATE/VALIDATE/SUBMIT_REVIEW`、CR-PLAN-001；已验 0170～0177 Schema、WBS 固定身份 Owner、Trace 图 HTTP/Win11 组合|
|前置任务|Outline、Section、StructuredSpec 的固定 Approved Solution 集合及受权证明；PlanVersion 创建/验证/送审 Owner|
|涉及实体/API|PlanVersion、WbsItem、固定 Solution/Requirement/Evidence 引用、TraceLink；本项仅核查，不修改冻结 API|
|验收标准|确认是否可在真实 Owner 同事务固定来源、证明精确 WBS Trace、验证六级/FS DAG 和送审资格；不可用时明确独立上游任务|
|主要风险|把草稿、合成批准或 StructuredSpec 专项批准替代整体 Approved Solution；仅有 WBS 身份边却无来源一致性；提前开放 PlanVersion 写入|

## 当前代码事实

1. `modules/plan` 目前只有 Plan 身份创建/读取及 WBS 只读 Trace 证明；`pln_plan_versions` 与 WBS/Dependency/Milestone/固定引用均为关闭式 Schema，没有 PlanVersion 创建、验证或送审应用 Owner/HTTP。图查询只读，不会自动建立或核对正式来源边。
2. StructuredSpec 已有专项 Review Subject、送审和终态；Outline/Section Version 虽有创建、读取及验证基础，但仓库没有 `SOL_OUTLINE_VERSION_SUBMIT_REVIEW` / `SOL_SECTION_VERSION_SUBMIT_REVIEW` 的运行实现或对应 Review 终态 Owner。其 `current_approved_version_ref` 不能由现有业务链安全产生。
3. 冻结 API-04 要求 PlanVersion 输入为 Approved Solution Outline/Section/StructuredSpec 的固定集合。仅凭外键存在、状态字段可写或合成测试数据都不足以证明这一资格。因此本片前置不满足，不能实施“真实 PlanVersion Owner 内来源/Trace 一致性”的验收或提前宣布 P03 完成。

## 后续顺序

- 转 `SOL-03-A06-P01`：对 Outline Version 的正式 Review/批准链做编码前核查，复用统一 Review 而非新造审批状态机；随后独立实施 Schema 窄门、Owner、原子送审、HTTP/Windows/UI/真实 PG-浏览器。
- Section Version 的正式 Review/批准链另列独立任务；两者及 StructuredSpec 均具真实 Approved 固定版本后，补 Solution 集合资格证明，再开展 PlanVersion 创建/验证/送审和本 P03 的来源/Trace 一致性验收。
- WBS Trace 图的已验只读能力保留；不回填旧历史、不将 AI 建议自动转为业务事实。独立正式服务账户信任/安装与 Gate 3/Pilot/Release 状态不变。

验证方式：冻结合同与当前代码/迁移静态交叉核查；本片无程序、Schema、API、角色、License 或数据变化，未运行功能测试。
