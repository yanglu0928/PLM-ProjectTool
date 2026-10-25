# PLAN-01-A04-P05-A01：Plan 当前身份前端安全客户端

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A04_P05_A01_FRONTEND_CLIENTS_PASS`。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A04-P05-A01`，P05 拆分为客户端、页面、真实浏览器三项|
|输入基线|冻结 PLAN_CREATE/GET/LIST、A04-P04 Windows真实 HTTP/PG、前端既有 SessionClient 安全写桥和 SolutionOutline 客户端模式|
|前置任务|后端合成信任/Win11真实链已通过；页面尚无 Plan 身份 API 客户端，先固定严格解析与不确定写重试合同|
|涉及模块/实体|前端 Plan API 客户端和 SessionClient 的冻结 Plan CREATE 写桥；不改后端/Schema|
|涉及 API|仅调用现有 `POST/GET /api/v1/projects/{project_id}/plans` 及 `GET .../plans/{plan_id}`，不新增公开 API|
|涉及权限|只从当前 Session/Project 且 ProjectManager/ImplementationMember 发起创建；读取当前项目；不在前端声称正式授权替代后端检查|
|验收|DTO 精确字段、ETag/Location/trace、page_size 1～200/排序与 cursor、跨项目/畸形响应拒绝、不确定提交保留原幂等 Key、定向/全量/typecheck/build|
|风险|把首次 CREATE 响应当当前详情，客户端偷偷换 Key 重试，列表顺序仍按旧 Outline ID 升序校验，跨项目残留|

拆分决定：本项只构建安全传输边界，不上线可见 UI；P05-A02 接项目入口、列表/创建/详情，P05-A03 使用 Windows 11 Edge/PG 做真实交互。无 Scope/API/Schema 变更；默认入口保持现状。

## Changed / Files / Migration / API

- Changed：`SessionClient` 新增 PLAN_CREATE 冻结路径的安全 POST 桥，保留会话 CSRF/Idempotency-Key、同源、无缓存/禁止重定向及一次提交语义；Plan CreateClient 严格核对201首次结果/trace/ETag/Location，未知结果返回不确定并由后续页面持久保存原操作号；Plan ReadClient 严格核对 GET/LIST 精确字段、项目/身份、空批准指针、ETag、50默认/最大200、签名游标、时间降序及同时间戳ID降序（含微秒精度）。
- Files：`apps/frontend/src/modules/auth/api/sessionClient.ts`、新增 `modules/plan/api/planReadClient.ts` 与 `planCreateClient.ts`、两份定向合同测试。
- Migration：无。API：仅消费既有冻结 Plan 身份合同，不新增/修改后端 URL、DTO 或权限。
- Upgrade/Rollback：仅前端未接可见路由的客户端代码；可撤本项且服务器 Plan 历史不变。页面装配后需重新构建前端资源。

## Tests / Result / Known Issues / Next

- 定向2文件8项通过，覆盖安全路径/项目范围、精确 DTO、批准指针必须为空、强 ETag/Location、200页边界、时间与ID倒序及微秒、错误码与不确定写；前端全量153文件1839项、TypeScript/typecheck和生产构建326模块通过。既有主 chunk 超500kB提示仍在，未因本项消除。
- 本项没有显示入口也未运行真实浏览器；不能称 Plan UI 或正式 Pilot 完成。正式服务账户密钥/License信任、版本/WBS/输出、Gate3/Pilot/Release仍待。

Next：`PLAN-01-A04-P05-A02` 项目级 Plan 列表/创建/详情页面与安全跨项目清屏。
