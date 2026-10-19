# PLAN-01-A04-P01：冻结 PLAN_CREATE HTTP

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A04_P01_CREATE_HTTP_CONTRACT_PASS`；仅可选合同/默认关闭，Windows真实组合未装入。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A04-P01`|
|输入基线|冻结 `POST /api/v1/projects/{project_id}/plans`、API-01 响应/幂等、P02 内部创建 Owner、现有 SolutionOutline 可选 HTTP 模式|
|前置任务|0169/PlanCreateService 的 PG/Auth/License/并发/审计回滚已通过；正式 Windows 目标账户依赖仍未装配|
|涉及模块/实体|Plan create API 与应用工厂可选入口；不修改 Plan 表/版本/WBS|
|涉及 API/权限|仅冻结 PLAN_CREATE；Session/CSRF/Origin/Idempotency-Key、项目 PM/实施成员由 Service 重验，默认应用保持404|
|验收|严格 JSON/UUID/query/header、201 data/trace/ETag/Location/no-store、401/403/404/409/422/503安全映射，默认关闭、定向/全量/wheel|
|风险|HTTP 装配绕过正式信任源、错误暴露内部信息、接入 Windows 前即误称可用|

只新增 opt-in Router 与应用工厂插槽，不接 Windows 运行组合；实际 PG/HTTP 与生产 Vault/License 信任留后续独立 WBS。不能由该任务证明 Pilot 或正式 PLAN_CREATE 可用。

## 实施与验证

- 增加冻结 `POST /api/v1/projects/{project_id}/plans` 可选 Router 与 `create_app` 注入槽；默认无注入仍404。唯一 JSON `name`、canonical Project UUID、无 query、Origin/Session/CSRF/Idempotency-Key 严格校验，返回 201 `data/trace_id`、强 `"v0"` ETag、Location 和 no-store；错误安全映射且不返回 Traceback。
- Plan API 自有有界严格 JSON/UUID 解析；初稿调用 Solution 模块私有解析函数，编码检查发现跨模块内部依赖，实施前即移回 Plan API 并复跑定向/全量，未形成冻结合同或数据偏差。无业务数据迁移。
- 定向创建合同/Service `7 passed / 21 subtests`，覆盖默认404、认证/CSRF/Origin/query/多余字段/重复 JSON、响应最小投影、错误映射和错误 Project 结果关闭；最终代码后端全量 `3798 passed / 3 skipped / 5958 subtests`。开发 wheel 1437 项，含 Plan API `_request` 和 create Router，SHA-256 `0a39a45cada6a084f9b2e3e053354cef148a5f5f19986d3d58ab0305012a99e4`；不是 Pilot/Release 包。

## 兼容、升级与遗留

- 无 Migration、冻结 URL/DTO/角色、License、依赖或历史数据变化；应用不注入新 Router 时旧行为不变。可撤可选 Router/槽；若将来启用并产生 Plan 历史，不可删除已有业务/Audit/收据。
- 尚未在真实 PG+HTTP/Windows 平台组合或正式服务账户信任下验证；PLAN_LIST/GET、前端、PlanVersion/WBS/Output 未完成。Gate3/Pilot/发行不变。

Next：`PLAN-01-A04-P02` 冻结 PLAN_GET/LIST 网络读取合同与专用分页游标前置核查。
