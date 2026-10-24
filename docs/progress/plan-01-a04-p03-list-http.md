# PLAN-01-A04-P03：冻结 PLAN_LIST 与专用游标

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A04_P03_LIST_HTTP_CONTRACT_PASS`。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A04-P03`|
|输入基线|冻结 PLAN_LIST、API-01 Page/签名游标/默认排序、A03-P03 当前授权读取及 P02 默认关闭详情|
|前置任务|Plan 内部列表/PG/撤权通过；当前内部 `plan_id ASC` 未对外，公开前应按 API-01 默认追加记录 `created_at DESC,id DESC` 稳定排序|
|涉及模块/实体|Plan read Service/Repository、专用 cursor codec、列表 Router/工厂槽；不改 Plan 数据表|
|涉及 API/权限|`GET /api/v1/projects/{project_id}/plans`；当前成员、Session/Host/License、page_size 1～200，游标绑定 Session/Project/page_size/排序位置|
|验收|默认50、最大200、严格唯一 query、篡改/跨范围拒绝、真实 PG 双页与同时间戳 tie、撤权/终态、合同/全量/wheel|
|风险|公开内部 plan_id 位置、跨项目续页、同时间戳丢项、错误/重复页、缺生产独立 cursor key 却默认启用|

本项专用 32 字节 HMAC key 只在测试显式注入；正式 Windows 当前账户 Vault/服务账户来源单独 WBS，不使用临时生成的生产 fallback。Plan 项目成员均能读取本项目身份且无逐项隐藏，签名位置即可；若未来加入逐项隐藏需重新评估加密游标。默认应用保持404。

## 实施与独立验收

- 当前 Plan 列表改为 `created_at DESC, plan_id DESC`，Repository 以两个位置字段进行严格 keyset 续页，最大200项，不使用可构造的裸 `after_plan_id` 公网参数；当前项目成员、Session 与 License 每页重验。排序改变仅影响未公开的内部读取，决策 `DEC-20261019-1228` 已先登记。
- 新增 Plan 专用32字节 HMAC-SHA256签名游标，绑定家族、Project、Session摘要、页大小查询指纹和创建时间/Plan ID位置；严格编码/完整性/规范时间与UUID校验，篡改及跨范围统一拒绝。不复用 Solution 私有工具或生产密钥。
- 新增冻结 PLAN_LIST 可选 Router/工厂槽，默认无注入仍404，GET 无缓存并返回 `data.items/next_cursor/has_more` 与 `trace_id`；只读组合的 POST 仍404，CREATE 先装配时不被列表的关闭入口遮盖。严格 Host/Session/Project/唯一 query、默认50/最大200及安全错误映射。
- Win11可弃 PostgreSQL 18.6 真正创建/读取/撤权/License/零读 Audit 复验通过；另在同一可弃库插入同时间戳的合法 Plan 夹具行，实际 SQL 两页与签名续页均按 ID 降序、不重不漏。夹具行不是正式业务事实。定向 LIST 合同5项/19子例、内部读取5项；最终后端全量3806通过/3跳过/5986子例。开发 wheel 1440 项，确认包含游标/Router，SHA-256 `dc66e61c5b3b44e221f5bca8c5a89280b9856a851cc3d9a6ad7564bdbf45a71e`；不是 Pilot/Release 包。

## 兼容、升级与遗留

- 无 Migration、冻结 URL/DTO/角色/License/依赖/旧数据变化；未显式注入时旧行为不变，可撤可选 Router 并保留 Plan 历史。已发布客户端不存在，因此内部排序变更不构成公开 Breaking Change。
- 当前 `ix_pln_plans__project_state` 尚未覆盖时间降序排序，大规模列表性能未验；正式索引/性能按后续 WBS 验收。Windows 服务账户专用 Vault key、真实 HTTP/PG 装配、前端、PlanVersion/WBS/Output、正式信任/安装仍未完成；Gate3/Pilot/发行不变。

Next：`PLAN-01-A04-P04` Windows 服务账户专用 Plan cursor key 与真实 CREATE/GET/LIST HTTP-PG 组合。
