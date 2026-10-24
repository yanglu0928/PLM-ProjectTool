# PLAN-02-A04-P04-A04-P01：TraceLink 固定 WBS Item 类型

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A04_P04_A04_P01_WBS_TRACE_TYPE_PASS`，仅类型与数据库CHECK。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P01`|
|输入基线|冻结Trace V1、Plan 0167～0176、已先行登记并同步的`CR-PLAN-001`|
|前置任务|A04前置核查已确认WBS目标类型缺口；CR记录影响/迁移/回滚/验证；Gate 2已通过|
|涉及模块/实体|trace.domain形状白名单、`trc_links`源/目标类型CHECK、Alembic0177|
|涉及API/权限|不改路径/Envelope或现有Owner注册；新增类型无Plan证明Port时继续`RESOURCE_NOT_FOUND`失败关闭|
|验收标准|旧类型/历史不变、新`PLN-02-WBS`仅PROJECT固定版本可表达、非法类型仍拒、空/有历史升降重升、已有新类型历史拒降、drift、定向与全量|
|风险|把类型可表示性误作WBS已授权/Approved、无Owner仍可创建、降级删除Trace历史|

P01只解决统一Trace类型表达及数据库CHECK，不安装Plan目标证明或创建正式边。`PLN-02`原PlanVersion语义保持；`PLN-02-WBS`的object_id为WBS Item ID、version_id为PlanVersion ID。上游Proof/权限/License/反向查询由P02独立验收。升级前备份；无新类型历史可降，有历史必须拒降。

实现与验收：TraceVersionRef及TraceLink ORM增加`PLN-02-WBS`，仅PROJECT可用；迁移0177扩展源/目标类型CHECK并增加项目Scope约束，不改旧行或现有类型。Windows 11 / PostgreSQL 18.6临时库完成空库/已有旧Trace行升级、旧类型保持、非法类型/新类型GLOBAL拒绝、旧历史可降重升、新类型历史拒降、Alembic drift；定向22项/23子例、后端全量3826通过/3跳过/5991子例。未注册Plan Owner时TraceTargetProofService仍`RESOURCE_NOT_FOUND`，没有把类型可表示性伪报为可创建正式WBS链路。开发wheel未验；P02/P03、真实权限/License/反向查询及Pilot/Gate/正式发行待。
