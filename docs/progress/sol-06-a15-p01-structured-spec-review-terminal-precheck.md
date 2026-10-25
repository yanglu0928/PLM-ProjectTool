# SOL-06-A15-P01：结构化专项 Reviewer 终态闭环前置核查

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVIEW_TERMINAL_PRECHECK_PASS`；仅完成依赖与边界核查，不表示任何专项已批准或退回。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A15-P01`|
|输入基线|Gate 2 冻结 `REVIEW_GET/REVIEW_DECIDE/REVIEW_WITHDRAW`、CR-SOL-021、A14-P04 SOL-06 Subject Owner、A14-P09 实际送审闭环|
|前置状态|固定专项可从 DRAFT 原子进入 IN_REVIEW，Review/Round/Reviewer/收据/Audit 均已形成；终态 Owner 内部 PG 生命周期已验证|
|本项范围|只核对通用 Review 决定、读取、Windows 生产组合和前端缺口；无程序、Schema、Migration、API、权限、License、依赖或数据变化|
|验收标准|明确实际阻断、不可复用的假设、锁序/权限/重放边界和可连续实施的单问题分片|
|风险|把内部 Owner 测试误报成生产决定可用；没有 GET 就让前端盲写；为加速绕过 assigned reviewer、当前事实或幂等要求|

## 核查结论

1. `StructuredSpecReviewSubjectOwner` 已实现开始、决定前当前事实重证、终态消费与重放访问；批准会把本版转 `APPROVED` 并替代同系列旧批准版，退回/撤回转 `RETURNED` 且保留旧批准指针。A14-P04 已在真实 PostgreSQL 验证这些内部能力。
2. 冻结通用决定端点 `POST /api/v1/projects/{project_id}/reviews/{review_id}/rounds/{round_id}:decide` 已存在并装入 Windows 显式写模式，但 `create_windows_project_review_router` 当前仅注册 HND-02、SRV-02、REQ-03、PRT-03（证据依赖完整时再有 SRV-05），没有 `SOL-06`。因此实际 SOL-06 决定会按设计失败关闭为 404；不能把内部 Owner 验证当成生产可用。
3. 通用决定服务已经强制当前 Session/CSRF/License/项目成员、assigned reviewer、单人单次最终决定、RETURN 实质 comment、幂等 Key、同事务 Owner 重证、Review/Subject/Audit/收据原子提交。接入 SOL-06 时必须复用该路径，不新增业务专用决定端点或前端直写状态。
4. 内部 `ReviewReadService` 和严格快照 Repository 已存在，项目策略也包含 `REVIEW_GET`，但没有公开 Review GET/LIST Router，也没有实际 Subject `authorize_read` 生产注册。前端仓库没有通用 Review 客户端或 Reviewer 页面；A14 详情只显示送审回执，不能供另一登录身份安全决定。
5. 最短纵向闭环必须先让已分配 Reviewer 能读取固定 Review/Round，再做决定。为保持一个 WBS 一个问题，生产决定接线和真实 PG/HTTP 先独立完成；读取 API、Windows 装配、前端、Edge 分项推进。冻结 `REVIEW_LIST` 仍需后续补齐，不能把手工 UUID 导航视为最终任务中心。

## 实施顺序

- `SOL-06-A15-P02`：抽取/复用正式 SOL-06 Owner 组合，将其加入通用 Windows Review 决定注册表；真实 HTTP/PostgreSQL 验证 assigned reviewer 批准、RETURN、重放、当前事实/资格漂移、跨项目/非评审人/License 拒绝及唯一终态事实。
- `SOL-06-A15-P03`：实现 SOL-06 当前/固定版本 `authorize_read`，扩展只读 Subject Registry，并实现默认关闭的冻结 `REVIEW_GET` 投影；不开放 LIST。
- `SOL-06-A15-P04`：将 GET 装入 Windows 显式读模式并以真实 Session/PostgreSQL 验证身份、项目、历史轮、决策投影和不泄露边界。
- `SOL-06-A15-P05`：前端固定 Review/Round 读取与 assigned reviewer 决定页面；严格响应绑定、RETURN comment、未知结果原 Key/原正文重试，成功不扩大为客户确认。
- `SOL-06-A15-P06`：Windows 11 Edge→生产 Vue/FastAPI→PostgreSQL 18.6 完成另一身份批准与退回两条真实链。`REVIEW_LIST`/任务中心另行核查，不在 GET 页面中伪造发现能力。

## 兼容、回滚与状态

- 本项没有产品变更，可直接撤销文档。后续均复用冻结 `/api/v1`、现有角色和 License 权益；不新增微服务或中间件。
- 接入后可关闭相应 Router 回滚入口，但已形成的 Review、Decision、专项状态、Audit 和收据必须保留。任何失败不能只回滚专项状态而留下 Review 决定，或反之。
- Gate 3、Pilot、正式信任、性能、Windows Server 2025、Debian 13 和发行状态不变。

Next：`SOL-06-A15-P02` 将正式 SOL-06 Subject Owner 接入通用 Windows Review 决定组合，并完成真实 HTTP/PostgreSQL 终态验收。
