# PLAN-02-A04-P04-A04-P02-A01：Plan 内部 WBS 固定版本 Trace 读取

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：内部只读证明验收通过；Trace 桥待 P02-A02。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P02-A01`|
|输入基线|冻结API-04的PLAN_VERSION_WBS_LIST、CR-PLAN-001、0177 WBS Trace类型、Plan身份与版本/WBS关闭式Schema|
|前置任务|0177类型/旧Trace兼容已在Win11/PG18.6及全量通过；PlanVersion/WBS同项目复合FK已有|
|涉及模块/实体|plan.application只读证明服务、plan.infrastructure查询仓库、project授权操作白名单|
|涉及API/权限|无公开路由；同一Trace事务中验Session、License、当前Project成员`PLAN_VERSION_WBS_LIST`，只返固定身份不返正文|
|验收标准|固定WBS/PlanVersion/Project精确匹配，RESTRICTED拒绝、跨项目/错版本/撤权/License失败关闭；真实PG查询和定向/全量|
|风险|绕过Plan内部Owner直接读表、把DRAFT或合成WBS称为正式确认、以Plan根身份冒充WBS身份|

本片仅提供Plan模块的受权只读Port。随后P02-A02的Trace桥适配公开三字段引用并证明目标；P02-A03再验证统一Trace反向查询与Windows组合。PlanVersion创建/Review/来源一致性由后续业务Owner负责，未注册Trace桥前新类型仍失败关闭。

验收：`test_plan_wbs_trace_read.py` 覆盖精确身份、归档历史、无效输入、当前成员撤权、License/Session失效、错误仓库身份及RESTRICTED拒绝；Project策略清单更新为176项。定向19项/832子例通过；Win11可弃 PostgreSQL 18.6 `validation/plan-02-a04-p04-a04-p02-a01-wbs-trace-read/verify.py` 证明精确固定身份、跨项目/错版本拒绝；后端全量3830通过/3跳过/6001子例。测试数据为隔离合成身份，未用客户资料。无Migration、公开API或现有数据变更；撤新增Port/策略可回滚，旧Trace行为不变。开发wheel、Trace桥/反向查询、Plan正式业务Owner及生产信任未验。
