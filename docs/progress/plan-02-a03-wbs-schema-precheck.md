# PLAN-02-A03：PlanVersion WBS/FS/Milestone Schema 前置核查

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A03_PRECHECK_PASS`，仅表示分片与安全边界明确，不表示 WBS 可用。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A03`|
|输入基线|冻结 DM-05 PlanVersion/WbsItem/Dependency/Milestone、SC-01/02/03、API-04，以及0170关闭式版本根表|
|前置任务|0170 Win11/PG18.6 空库及既有Plan升级/降级/重升、drift与全量测试通过；整体 Approved Solution 来源未接通|
|涉及模块/实体|plan.infrastructure；WbsItem、FS Dependency、Milestone、Requirement/Solution/Evidence固定引用|
|涉及 API/权限|本项不开放 API；后续仅当前 Project member 读，写须 ProjectManager/ImplementationMember 与统一 Review/Trace 授权|
|验收标准|确定独立 Schema 切片、同 Plan/Project/Version 复合关系、六级与仅FS的约束位置、空/有数据迁移测试和历史保护|
|风险|跨版本父子/依赖、无环未验证即送审、非法层级、动态引用、过早放开 PlanVersion/批准指针、未追溯 WBS Task|

核查冻结实体与当前 ORM/Migration：0170 只有版本根表，无 WBS、依赖、里程碑或固定引用。不能凭计划身份或空版本根表报告完整计划。数据库负责项目/版本归属、稳定编码、层级 1..6、仅 FS 和不允许自依赖等局部不变量；父层级连续、依赖 DAG、日期/工期/范围覆盖、负责人/验收及跨模块引用授权须在同事务业务 Owner 与送审验证中核查，不能用局部 CHECK 冒充整体校验。首次版本业务创建仍等待已批准 Solution 固定集合；所有新增表保持写入关闭，批准指针仍为空。

按单一问题分片：`PLAN-02-A04-P01` WbsItem 身份/层级闭锁 Schema；P02 同版本 FS Dependency 闭锁 Schema；P03 Milestone/关联 Schema；P04 固定 Requirement/Solution/Evidence 引用及 Trace 所需关系。每项独立 ORM/Migration、空库和有历史升降级、负例、drift、定向/全量测试，才可单独标 PASS。之后才安装真正的 Approved Solution 输入证明、PlanVersion Owner、验证/Review/Trace/HTTP/UI/Output。此处仅核查，不改运行代码或冻结合同，无需 CR。
