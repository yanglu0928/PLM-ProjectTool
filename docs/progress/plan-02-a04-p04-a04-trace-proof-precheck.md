# PLAN-02-A04-P04-A04：WBS 统一 Trace 证明前置核查

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A04_P04_A04_PRECONDITION_BLOCKED`，已登记 `CR-PLAN-001`，未改运行代码。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04`|
|输入基线|冻结架构/DM-05/API-02与API-04、当前TraceLink V1、Plan 0167～0176|
|前置任务|Requirement/Solution/Evidence固定引用Schema及Win11/PG全量通过；统一Trace已具版本边和Owner Port，但白名单无WBS Item类型|
|涉及模块/实体|trace.domain `TraceVersionRef`、`trc_links` 类型CHECK及Plan WbsItem目标证明；不复制Trace表|
|涉及API/权限|冻结TraceLink创建/查询路径保持；新增受控类型需Plan Owner验证项目成员/License/固定版本和当前业务资格|
|验收标准|固定WBS Item可单独表示并受权反向查询；旧PlanVersion语义不变；空/历史数据库升降、非法类型/跨项目/错版本、权限/License/失败关闭|
|风险|把PlanVersion边冒充单个WBS任务边、绕过统一Trace Owner、未Approved来源冒充正式事实、冻结类型集合静默变化|

现有 `PLN-02` 只标识PlanVersion，不能证明单个WBS Item。按用户持续授权先记录 `CR-PLAN-001` 再实施。拆分：`P04-A04-P01` 追加Trace类型与迁移（无Owner时继续失败关闭）；`P04-A04-P02` 实现Plan目标证明及反向查询合同；`P04-A04-P03` 在真实PlanVersion Owner中核对固定来源/Trace一致性。各片独立验收，不因Schema引用存在就称正式Trace完成。
