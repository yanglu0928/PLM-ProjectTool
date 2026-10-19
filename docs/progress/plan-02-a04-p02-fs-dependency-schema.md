# PLAN-02-A04-P02：关闭式 FS Dependency Schema

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A04_P02_FS_DEPENDENCY_SCHEMA_PASS`，仅关闭式依赖基础。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P02`|
|输入基线|冻结 DM-05 仅FS同版本无环、SC-01/03出入邻接索引、API-04 lag非零需单位/理由；0171 WbsItem|
|前置任务|0171 Win11/PG18.6空库/已有版本升降重升、隔离/历史/drift及全量通过；WBS Owner尚未开放|
|涉及模块/实体|plan.infrastructure；`pln_wbs_dependencies`，同PlanVersion的前驱和后继WbsItem|
|涉及 API/权限|无公开API/业务写；新表DML/TRUNCATE关闭；Version/WbsItem及批准指针仍关闭|
|验收标准|顺序0172、同Project/Plan/Version前后节点复合FK、仅FS、禁自依赖/重复边、非零lag单位/理由、索引和历史保护；空/有数据升降重升/drift/负例、定向/全量|
|风险|跨版本边、未验证环/日期关系即送审、含糊lag单位、直接SQL伪造依赖、降级删历史|

数据库只保证边的局部完整性；多边DAG、计划日期和工期一致性由后续同事务Owner/版本验证执行。整体Approved Solution输入未接通前不开放写口。升级前备份；空表可降，有历史拒降。

## 独立验收

- ORM/Migration `20261019_0172` 新增关闭式 `pln_wbs_dependencies`，两端分别以 Project/Plan/Version/WbsItem 复合FK固定，同版本边唯一，仅FS、不可自依赖，非零整数lag必须提供非空单位和理由；建出入邻接索引。DML/TRUNCATE关闭，既有PlanVersion/WbsItem和批准指针不放开。
- Win11/可弃PostgreSQL18.6：空库升至0172/降至0171；已有两个项目、Plan/Version、三条本版本WBS及其他版本/项目WBS升级保持不变；合法零与非零lag写入、重复边、非FS、自依赖、缺/畸形lag说明、跨版本/跨项目端点和历史拒降负例通过；清理合成依赖后降级/重升，原WBS保留；三次Alembic drift无新增升级，退出0并清理临时实例。
- 定向9项；最终后端全量 `3815 passed / 3 skipped / 5991 subtests`。未运行开发wheel，不构成Pilot/Release包证据。

## 兼容、升级与遗留

0171→0172只增闭锁表/索引/触发器，不改冻结API、角色、License或现有历史。升级前备份；依赖空表可降，有历史拒降并须向前修复或人工备份恢复。全图DAG、日期/工期/日历、完整WBS属性、Milestone/固定引用、正式批准输入/Owner/HTTP/UI/Output及正式信任/安装仍待，Gate3/Pilot/发行未通过。
