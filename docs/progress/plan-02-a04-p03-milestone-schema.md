# PLAN-02-A04-P03：关闭式 Milestone 与 WBS 关联 Schema

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A04_P03_MILESTONE_SCHEMA_PASS`，仅关闭式里程碑基础。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P03`|
|输入基线|冻结 DM-05 Milestone 至少字段及非负工期、SC-01 PlanVersion owned table、API-04固定版本；0172 PlanVersion/WBS/FS基础|
|前置任务|0172 Win11/PG18.6空库/已有WBS升降重升、约束/drift及全量通过；完整Approved Solution输入和Owner未开放|
|涉及模块/实体|plan.infrastructure；`pln_milestones` 和 `pln_milestone_item_refs`|
|涉及 API/权限|无公开API/业务写；两表DML/TRUNCATE关闭，PlanVersion及批准指针仍关闭|
|验收标准|顺序0173、同Plan/Project/Version复合FK、名称/目标日期/非负工期/验收规则/状态边界、同版本关联WBS与唯一顺序、历史保护；空/有数据升降重升、负例/drift、定向/全量|
|风险|跨版本任务链接、未明确Gate来源即假定已通过、无验收规则里程碑、负工期、降级擦除历史|

GateRef 先作为有界逻辑引用；真实 Gate/Review/Evidence 由后续Owner逐项解析和授权，不在闭锁Schema中假造跨模块FK或Gate通过。关联表只保证同版本WBS；链接数量、日期/依赖一致性留同事务业务验证。整体Approved Solution未接通前不开放写口。升级前备份，空表可降，有历史拒降。

## 独立验收

- ORM/Migration `20261019_0173` 新增关闭式 `pln_milestones` 与 `pln_milestone_item_refs`：项目/计划/版本复合FK，目标日期有限、日工期非负、验收规则必填、GateRef有界、候选状态约束；链接WBS同版本复合FK并按里程碑去重/排序。两表DML/TRUNCATE关闭，PlanVersion/WBS/批准指针不放开。
- Win11/可弃PostgreSQL18.6：空库升至0173/降至0172；已有两个项目、Plan/Version及WBS升级保持不变；合法里程碑/关联、负工期/无限日期/空验收/跨项目、重复名称/关联/顺序、跨版本和跨项目WBS及历史拒降负例通过；清除合成里程碑后降级/重升，WBS仍在；三次Alembic drift无新增升级，退出0并清理临时实例。首轮测试将单表TRUNCATE预期为触发器拒绝，实际数据库先用外键拒绝；修正为核对父表保护触发器存在及子表触发器拒绝后完整重跑。
- 定向9项；最终代码后端全量 `3817 passed / 3 skipped / 5991 subtests`。未运行开发wheel，不能当作Pilot/Release包证据。

## 兼容、升级与遗留

0172→0173仅增闭锁表/索引/触发器，不改冻结API、角色、License或旧历史。升级前备份；两表无历史可降，有历史拒降并须向前修复或人工备份恢复。GateRef解析、日期/依赖/验收真实性及完整链接覆盖仍须后续Owner/Review校验；固定引用、整体Approved Solution输入、PlanVersion业务/API/UI/Output、正式信任/安装和Gate3/Pilot/发行均未完成。
