# PLAN-02-A04-P04：WBS 固定来源引用 Schema 前置核查

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A04_P04_PRECHECK_PASS`；仅确立来源关系和分片，不表示正式追溯已可用。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04`|
|输入基线|冻结 DM-05 WBS固定Requirement/Solution/Evidence、SC-01 `pln_item_*_refs`、API-04 PlanVersion输入与Trace约束；0173闭锁WBS/Milestone|
|前置任务|0173 Win11/PG18.6及后端全量通过；整体Approved Solution和版本Owner未接通|
|涉及模块/实体|plan.infrastructure三类引用；上游RequirementVersion、Solution Outline/Section/Spec版本、Evidence；通用TraceLink仍由Trace Owner写|
|涉及API/权限|本项不开放API；所有引用表先闭锁，后续Owner在创建/读取/送审时逐节点验当前Project、批准状态、证据资格与License|
|验收标准|确定每类引用的DB可证明关系与Owner必须证明的状态/授权；按单一问题分片并定义空/有历史升降级及隔离负例|
|风险|使用动态latest、孤儿/跨项目版本、把专项Spec批准当整体方案批准、GLOBAL Evidence跨Scope误用、直接SQL绕过Trace/Review|

现有RequirementVersion有 `(requirement_version_id,requirement_id,project_id)`唯一键，可由WBS引用表复合FK固定；OutlineVersion、SectionVersion也有同项目复合键，StructuredSpec则按 `(spec_id,spec_series_id,project_id)`固定，Solution三类不可用单个无类型FK冒充。Evidence有GLOBAL/PROJECT二元Scope，其当前资格/撤销是可变事实，数据库仅能存固定ID/Scope/Project并与Evidence根核对，后续Owner必须重验资格。业务模块不直接读写上游内部表；数据库FK只维护引用完整性。TraceLink由统一Trace服务建立，不在plan复制平行Trace表。

分片：`P04-A01`固定RequirementVersion引用；`P04-A02`三类型Solution版本引用；`P04-A03`Evidence固定引用及Scope；`P04-A04`校验TraceLink与Owner所需证明合同。每片独立预检、ORM/Migration（如适用）、Win11/PG空/有数据升降重升、跨项目/版本/历史/drift、定向与全量；不得在来源真正Approved/授权证明前开放PlanVersion创建/送审。本项仅静态核查，未运行功能测试、未修改运行代码/冻结API，无需CR。
