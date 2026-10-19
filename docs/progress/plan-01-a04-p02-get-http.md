# PLAN-01-A04-P02：冻结 PLAN_GET HTTP

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A04_P02_GET_HTTP_CONTRACT_PASS`；只限可选详情合同，Windows真实组合未装。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A04-P02`|
|输入基线|冻结 PLAN_GET/LIST、API-01 页面/游标、A03-P03 当前授权只读 Owner、A04-P01 默认关闭 CREATE|
|前置任务|Plan GET 内部 Owner 实测通过；LIST 公开还缺独立签名游标与实际服务账户 key，不能提前暴露内部 after_plan_id|
|涉及模块/实体|Plan 详情 HTTP、应用工厂可选槽；不修改 Plan/Version Schema|
|涉及 API/权限|只开放冻结 `GET /api/v1/projects/{project_id}/plans/{plan_id}` 可选路由；当前 Project member、Session/Host/License 由现有层重验|
|验收|严格 UUID/无 query、200 data/trace/ETag/no-store、401/403/404/503安全映射、默认404、定向/全量/wheel|
|风险|把 CREATE 首次快照误当当前详情；LIST 若无专用游标会暴露可构造位置/跨Session续页|

本项将 GET 与 LIST 分开：GET 不依赖游标，可先安全实现；LIST 留后续 P03，先构建专用完整性游标，再接 HTTP/Windows key。仅 opt-in Router，Windows 真实组合尚未启用。

## 实施与验证

- 增加可选冻结 `GET /api/v1/projects/{project_id}/plans/{plan_id}` Router 与应用工厂插槽，默认无注入仍404。严格 Host、Session、canonical 双 UUID、无 query；仅投影当前授权的 Plan name/state/空批准指针/创建人/时间与强 ETag，200 `data/trace_id`、no-store，内部错误安全映射。
- 定向详情合同/内部读取 `8 passed / 9 subtests`，覆盖默认关闭、主响应、匿名/错误 Host/畸形身份/query、License/隐藏资源/无效投影；后端全量 `3801 passed / 3 skipped / 5967 subtests`。开发 wheel 1438 项，含独立 Plan 详情 Router，SHA-256 `fa31862e4bcf8d449f21c7e9e113a9d1b76fab4a1d2a3b99fc3681fd91ccd1ba`；不是 Pilot/Release 包。

## 兼容、升级与遗留

- 无 Migration、冻结路径/角色/License/依赖/旧数据变化；可撤可选 Router，Plan 历史保留。默认/Windows 当前组合未挂载，不能把合同测试称为真实服务可用。
- `PLAN_LIST` 仍需独立签名/范围绑定游标与当前服务账户 key；Windows 真实 HTTP/PG、PlanVersion/WBS/Output、正式信任和安装未完成，Gate3/Pilot/发行维持未通过。

Next：`PLAN-01-A04-P03` Plan LIST 专用游标合同与默认关闭网络列表。
