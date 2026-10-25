# PLAN-02-A04-P04-A03：关闭式 WBS → Evidence 固定引用

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A04_P04_A03_EVIDENCE_REF_SCHEMA_PASS`，限关闭式 Schema。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A03`|
|输入基线|冻结 DM-05/SC-01/API-04、P04 前置核查；SC-01 指定 `pln_item_evidence_refs`|
|前置任务|0175 WBS三类型Solution固定引用经Win11/PG18.6和后端全量验收；Evidence身份/Scope/Project字段已存在|
|涉及模块/实体|plan.infrastructure引用表；evidence.infrastructure仅补充供复合FK引用的唯一键，不改其业务Owner|
|涉及API/权限|无API或业务写；新表DML/TRUNCATE闭锁；Evidence资格、成员/License、Trace由后续Owner重验|
|验收标准|固定Evidence ID、GLOBAL/PROJECT Scope及Project归属由FK/CHECK交叉证明；同版本WBS、顺序/去重、空/有数据升降重升、跨项目/假Scope/历史/drift、定向/全量|
|风险|单列ID FK无法证明引用声明的Scope/Project；GLOBAL误指PROJECT、PROJECT跨项目、引用已撤销证据、无Trace|

Evidence现有主键 `evidence_id` 唯一，但无可供 `(evidence_id,scope)` / `(evidence_id,project_id)` 外键指向的复合唯一键。为严格证明固定引用的身份归属，在原Evidence表上增加两个冗余但必要的复合唯一约束；新引用表分别以复合FK对Scope及Project核对。GLOBAL 的来源项目为空，PROJECT 来源项目必须等于WBS项目，且通过复合FK指向真实Evidence项目。上游资格可变化，静态FK不证明ELIGIBLE或用户授权；Owner必须逐次重验。升级前备份；空引用表可降，有历史拒降。

实现与验收：ORM/迁移0176追加Evidence复合唯一键及关闭式WBS Evidence引用表。Windows 11 / PostgreSQL 18.6临时库完成空库/已有Plan/WBS/Evidence升级、GLOBAL及同项目PROJECT正例、假Scope/跨项目/缺来源项目/重复/顺序负例、DML/TRUNCATE闭锁、有历史拒降、空表降级重升和Alembic drift；定向9项、后端全量3823通过/3跳过/5991子例。首轮真实DB负例发现SQL CHECK接受NULL结果，PROJECT缺来源项目被错误放行；在正式ORM及迁移中加入显式`source_project_id IS NOT NULL`后重跑全部DB验证通过。上游Evidence由仅限临时库的合成夹具注入，不是已合格证据或客户确认。

兼容与回滚：0175→0176不改冻结API、Evidence Owner或旧历史；新增Evidence复合唯一约束会扫描并短时锁定已有表，生产升级需备份及维护窗口。空引用表可降至0175，有引用历史拒降，须向前修复或人工备份恢复。开发wheel本轮未验：现有虚拟环境无`pip`且本地`build`目录遮蔽模块入口。Evidence当前资格/撤销、Project授权、License、Trace及Plan业务Owner仍待；Gate3/Pilot/正式发行未通过。
