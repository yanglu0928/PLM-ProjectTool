# PLAN-02-A04-P04-A01：关闭式 WBS → RequirementVersion 固定引用

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A04_P04_A01_REQUIREMENT_REF_SCHEMA_PASS`，限关闭式 Schema。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A01`|
|输入基线|冻结DM-05/SC-01/API-04、P04前置核查；现有 `req_requirement_versions` 同Project复合唯一键|
|前置任务|0173闭锁WBS/Milestone通过Win11/PG与全量；RequirementVersion持久键/Project归属存在|
|涉及模块/实体|plan.infrastructure `pln_item_requirement_refs`；只追加WBS与固定RequirementVersion关系|
|涉及API/权限|无公开API/业务写；新表DML/TRUNCATE关闭；Approved/当前成员/License/Trace由后续Owner证明|
|验收标准|顺序0174、同Project/Plan/Version WBS FK与RequirementVersion同项目复合FK、重复/顺序/历史保护；空/有数据升降重升、跨项目负例/drift、定向/全量|
|风险|把存在但未批准的RequirementVersion当可用输入、跨项目关系、动态latest、伪造Trace、误删历史|

只固定不可变版本ID及WBS覆盖顺序，不在闭锁表中伪造批准状态或TraceLink。上游版本状态可能变化，Owner在业务读取/送审时重验并建立正式Trace。升级前备份；空表可降，有历史拒降。

实现与验收：ORM及0174迁移增加固定RequirementVersion复合FK、同版本WBS复合FK、顺序及重复约束、检索索引和写入/截断闭锁。Windows 11 / PostgreSQL 18.6使用临时隔离库，空库及已有Plan/WBS/Requirement版本升级、跨项目与跨版本负例、关闭写、历史拒降、清空后降级重升、Alembic drift均通过；定向9项通过，后端全量3819通过/3跳过/5991子例。首轮临时夹具缺少上游RequirementVersion完整性触发器的临时关闭步骤，已仅修正合成夹具后重跑通过，正式迁移与运行代码没有绕过该触发器。夹具中的RequirementVersion仍为待确认状态，只证明固定键完整性，不证明Approved资格。

兼容/回滚：0173→0174只追加新表/索引/闭锁触发器，不改既有数据、冻结API、权限、License或业务Owner；先备份，空引用表可降至0173，有历史拒绝降级，须向前修复或经人工备份恢复。PlanVersion整体Approved Solution输入、资格重验及TraceLink仍待后续任务；Gate 3、Pilot与正式发行均未通过。
