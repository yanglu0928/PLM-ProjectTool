# PLAN-02-A04-P04-A04-P02-A03-P01：统一 Trace 图查询 HTTP 合同

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：可选HTTP合同验收通过，Windows真实组合待P02。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P02-A03-P01`|
|输入基线|冻结 API-02 `TRACE_GRAPH_UPSTREAM/DOWNSTREAM`；CR-PLAN-001 `PLN-02-WBS`；Trace 限深图/受权边/加密游标服务及 Plan WBS 桥|
|前置任务|Gate2冻结已批准；P02-A01/A02只读证明与桥合同通过；统一图服务存在，但公开图路由与Windows装配不存在|
|涉及模块/实体|Trace公开资源解析、Trace GET API、应用可选路由槽；不修改WBS/Trace Schema|
|涉及API|冻结 GET `/api/v1/projects/{project_id}/trace-graph:upstream` 与 `:downstream`，根节点采用三字段固定引用，受控关系/深度/节点/分页参数|
|涉及权限|Session、License、Project `TRACE_GRAPH_READ`、逐节点Owner当前授权；无权目标不枚举、筛选不完整标记truncated；默认应用不挂载|
|验收标准|严格参数/Host/Session/错误/响应合同、游标绑定及重新证明，定向与全量回归；Windows真实HTTP/PG留P02|
|风险|双事务间撤权、游标状态漂移、将未注册Owner/无权候选误当完整图、合成密钥误当正式信任|

本片只提供可选路由，不将其挂入Windows或默认应用。公开根引用在独立短事务解析，随后图服务在查询事务重新验证Session/License/Project及逐节点Owner；不能仅凭首次解析返回图。P02另验Windows当前账户游标密钥、真实HTTP/PG及WBS反向链；本片不称可使用图接口。

实现/验收：为`TracePublicEdgeResolver`添加受权三字段单根解析，图读取服务以固定根重新进入既有受权限深/分页图服务；新增可选GET双方向路由和应用槽，严格解析参数、Session/Host、错误及最小图投影；过时游标映射现有409`CONFLICT_VERSION`，不暴露内部错误。定向28项/28子例，后端全量3841通过/3跳过/6019子例。无Migration、旧数据及既有路由变更；可撤可选槽/服务/路由回滚。PG/Windows实测、正式密钥与Owner完整注册未验，默认仍404。
