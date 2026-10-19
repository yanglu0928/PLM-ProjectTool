# PLAN-02-A04-P04-A02：关闭式 WBS → Solution 固定版本引用

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A04_P04_A02_SOLUTION_REF_SCHEMA_PASS`，限关闭式 Schema。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A02`|
|输入基线|冻结 DM-05/SC-01/API-04、P04前置核查；SC-01 指定 `pln_item_solution_refs`|
|前置任务|0174 WBS/Requirement固定引用在Win11/PG18.6及后端全量通过；三种上游正式版本表已有项目复合唯一键|
|涉及模块/实体|plan.infrastructure `pln_item_solution_refs`；上游 OutlineVersion、SectionVersion、StructuredSolutionSpec 仅作为复合FK目标|
|涉及API/权限|不开放API/业务写；新表DML/TRUNCATE关闭；Approved资格、当前成员、License及Trace由后续Owner证明|
|验收标准|单表显式三类型且恰一目标、同版本/项目WBS FK、上游固定版本/根/项目FK、类型内唯一及全局顺序；空/已有库升降重升、跨项目/错误类型/重复/历史/drift、定向与全量|
|风险|单UUID多态弱引用、跨项目引用、把专项Spec批准冒充整体方案批准、动态latest、SQL绕过Review/Trace|

选择SC-01原定单表而非三张平行表；使用显式 `source_kind` 与三个互斥的固定目标字段组，分别连接 `sol_outline_versions`、`sol_section_versions`、`sol_structured_specs` 的复合唯一键。部分唯一索引分别防止同一WBS重复引用同类版本；`ordinal` 在WBS所有Solution引用间唯一。静态FK只证明身份和项目，不证明当前Approved、整体Solution完整性或正式Trace；这些必须在后续业务Owner中独立证明。升级前备份；空表可降，有历史拒降。

实施及独立验收：ORM与0175迁移只追加关闭式 `pln_item_solution_refs`；Windows 11 / PostgreSQL 18.6 临时库完成空库/已有Plan/WBS及三类Solution历史升级、类型互斥、三类固定版本复合FK、跨项目/错误根/错误类型、重复/顺序、DML/TRUNCATE闭锁、有历史拒降、空表降级重升及Alembic drift验证。定向9项、后端全量3821通过/3跳过/5991子例。首轮负例测试因选用了已存在的Section/Spec版本，先触发唯一索引而未抵达预期FK；仅调整合成测试数据并重跑通过，产品约束未削弱。上游版本由仅限临时库的合成夹具注入，未作为正式批准事实。

兼容与回滚：0174→0175只增表、索引和触发器，不改冻结API、上游历史、权限或License。升级前备份；空表可降至0174，有历史拒降，需向前修复或按人工备份恢复。Approved来源资格、整体方案、Trace、PlanVersion业务Owner与HTTP/UI/Output仍待；Gate 3、Pilot及正式发行未通过。
