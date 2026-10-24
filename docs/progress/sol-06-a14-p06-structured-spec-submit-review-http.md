# SOL-06-A14-P06：结构化专项冻结送审 HTTP 合同

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_SUBMIT_HTTP_PASS`；已完成默认关闭的冻结 HTTP 边界，不表示 Windows 生产组合、前端、浏览器、正式信任或 Gate 3 已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A14-P06`|
|输入基线|API-04 冻结 `SOL_SPEC_SUBMIT_REVIEW` / `ReviewSubmissionRequest`、CR-SOL-021、DEC-1210、A14-P05 内部服务|
|前置任务|统一 Review 状态 Owner、当前事实重证、原子提交/收据/Audit/重放均已通过|
|涉及模块/实体|solution API、通用应用工厂；无新实体|
|涉及 API / Schema / 权限|实现冻结 POST 路径和四字段请求、201 Review/Round 投影；新增 opt-in 工厂插槽；Schema/角色/License/依赖不变|
|验收标准|默认 404；受信 Origin/Session/CSRF/Key；canonical UUID；精确字段与 null 元数据；安全错误映射；201 身份/Trace/ETag/no-store；异常结果失败关闭|
|风险|静默丢弃期限/备注；客户端伪造 series；路径/响应错绑；错误泄露；默认应用意外开放|

## 实施结果

- 新增 `create_structured_spec_review_submission_router`，实现冻结 `POST /api/v1/projects/{project_id}/structured-solution-specs/{spec_id}:submit-review`。Router 仅可显式注入 `create_app`，默认应用保持 404。
- 请求必须精确包含 `reviewer_ids/policy_ref/due_at/submission_note`；策略固定 `STRUCTURED_SPEC_ALL_V1`，Reviewer 使用 canonical lowercase UUID，后二者 V1 必须显式为 `null`。未知/缺失字段、查询参数、错误 Content-Type/JSON 均失败关闭。
- 客户端不提交系列；201 投影返回内部服务派生的 `spec_series_id`、路径绑定版本、Review/Round、规范 Reviewer、提交人/UTC 时间、IN_REVIEW/首轮与 `"v1"` ETag。外层 Trace 与响应 Header 一致，所有成功/错误响应 `no-store`。
- Service 错误仅映射为冻结公共错误：隐藏资源/权限 404、License 403、业务/Reviewer 资格 422、锁/幂等/版本/归档冲突 409，其他情况 503；不回传异常文本。
- `docs/api-contract/structured-spec-submit-review-v1-increment.md` 固化本次实现边界；DEC-1210 同时补记 P05 服务端版本到系列绑定决策。

## 验证证据

- 合同及关联回归：12 项通过、44 个子例；覆盖默认关闭、Origin、精确字段、null 限制、UUID 规范、查询参数、Content-Type、响应字段集、Trace/ETag/no-store、异常投影和全部服务错误映射。
- 后端全量：`3747 passed, 3 skipped, 5846 subtests passed`；`py_compile` 与 `git diff --check` 通过。
- Python 3.13 开发 wheel 共 1415 项，包含新 API Router，SHA-256 `bfe1afd2d5ea63e69d5a3573127b9dac7214bb143df2c0bc32db06567242e709`。该 wheel 不是 Pilot 或正式发行包。

## 兼容、升级与回滚

- 无 Migration、冻结路径/请求/角色、License、依赖或旧数据变化。`spec_series_id` 是服务端既有事实的响应投影，不成为请求授权输入；P05/P06 必须同版本部署。
- 当前不在 Windows 生产组合中创建 Service 或挂载 Router；删除可选工厂参数/Router 可回滚，P05 已产生的测试历史只存在可弃环境。
- 后续一旦实际入口产生 Review、状态、Audit 或收据，只能关闭入口并保留历史，不得删除或重写。
- 正式服务账户/公钥信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 和正式发行状态不变。

Next：`SOL-06-A14-P07` 将送审 Router 仅装入 Windows 显式写模式，组合正式设计的 Auth/License/Project/Review/SOL-06 Owner 依赖，并以 Windows 11 PostgreSQL 18.6 真实 HTTP 验证成功、重放、漂移/角色/License/隔离与唯一数据库事实；默认和只读模式保持关闭。
