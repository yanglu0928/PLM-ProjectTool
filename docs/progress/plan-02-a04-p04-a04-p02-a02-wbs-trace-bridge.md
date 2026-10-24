# PLAN-02-A04-P04-A04-P02-A02：WBS 固定引用 Trace 桥

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：独立桥合同验收通过，Windows组合待 P02-A03。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P02-A02`|
|输入基线|CR-PLAN-001新增`PLN-02-WBS`；P02-A01 Plan内部受权固定身份读取已验|
|前置任务|Trace三字段公开引用、目标证明Port及Section/Requirement桥模式已存在；PlanVersion/WBS仍关闭式Schema|
|涉及模块/实体|entrypoints桥适配；不修改Plan、Trace核心Schema或其他Owner|
|涉及API/权限|无公开路由/权限变更；resourceId为WbsItemId、versionId为PlanVersionId，PROJECT限定；错误不枚举未授权目标|
|验收标准|resolve/prove沿用同一事务、精确三字段/项目、撤权/License/未知错误映射、错类型/Scope拒绝；单元与全量通过|
|风险|把PlanId或动态latest当WBS身份、将未接Windows Trace路由误报可用、把DRAFT候选当Approved事实|

本片只建立可供显式注册的桥类，不在现有Windows Trace路由注册；P02-A03核查统一Trace反向查询和Windows组合。注册前新WBS Trace仍默认关闭。

验收：定向15项/18子例，覆盖resolve/prove同事务、WBS/版本/项目精准传递、错类型/Scope拒绝、撤权/License/内部故障安全映射；后端全量3833通过/3跳过/6005子例。无Migration/公开API/旧数据变化；移除桥类即可回滚，0177新类型和P02-A01 Plan证明保持关闭状态。PG精确读取已在P02-A01独立验收，本片未声称Windows HTTP/真实Trace图通过。
