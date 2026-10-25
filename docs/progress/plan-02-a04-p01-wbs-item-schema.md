# PLAN-02-A04-P01：关闭式 WbsItem 身份与层级 Schema

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A04_P01_WBS_ITEM_SCHEMA_PASS`，仅关闭式 WBS 身份基础。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P01`|
|输入基线|冻结 DM-05、SC-01/02/03、API-04；PLAN-02-A03 分片；0170版本根表|
|前置任务|0170已通过真实PG/全量；整体 Approved Solution 未形成，故只建关闭式表|
|涉及模块/实体|plan.infrastructure ORM/Migration；`pln_wbs_items` 身份、版本/项目归属、父子与层级|
|涉及 API/权限|无公开 API/业务写；新增表所有DML/TRUNCATE关闭，PlanVersion和批准指针保持关闭|
|验收标准|顺序0171、复合FK/唯一编码/父子同版本/根层与层级1..6/历史保护；Win11/PG18.6空库、有Plan版本历史升降重升、负例/drift、定向及全量|
|风险|跨版本/跨项目父子、重复根顺序、直接写入伪造正式WBS、降级擦除历史|

本片只建 WbsItem 结构身份，业务属性、FS依赖、里程碑、固定引用、完整父子level连续/DAG/日期/覆盖的业务验证留后续片；闭锁表不产生正式实施任务。局部约束不能替代 Owner 的全图校验。升级前备份，空表可降，有历史拒降。

## 独立验收

- Migration `20261019_0171`、ORM 添加关闭式 `pln_wbs_items`：PlanVersion/Plan/Project 复合FK，同版本父节点复合FK，版本内WBS编码唯一、同父顺序唯一（含NULL根），根level1/子level2..6、不可自指、名称/编码/状态局部约束与 SC-03 顺序索引。写入/修改/删除及TRUNCATE均由关闭式触发器拒绝；未触碰0170版本根Owner或Plan批准指针。
- Win11/可弃PostgreSQL18.6：空库升至0171/检查/降至0170；已有两个项目、Plan及PlanVersion历史后升级，验证保留；关闭写、重复编码、重复根顺序、跨项目版本、跨版本父节点、level7、自指和有历史拒降；清除合成WBS后降级/重升，已有版本仍在；三次Alembic drift检查无新增升级，退出0，临时库清理。
- 定向9项通过；后端全量 `3813 passed / 3 skipped / 5991 subtests`。未运行开发wheel打包，不能作为Pilot/Release包证据。

## 升级与遗留

0170→0171只增关闭式表/索引/触发器，不改冻结API、角色/License或已有业务数据。升级前备份；WBS空表可降，有历史拒降并须向前修复或人工备份恢复。完整父子level连续、FS DAG、任务分类/负责人/日期/验收、固定引用、Trace、版本Owner/HTTP/UI及正式Approved Solution输入待后续独立WBS；Gate3/Pilot/发行不因此通过。
