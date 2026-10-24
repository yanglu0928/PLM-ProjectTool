# CR-SOL-021：StructuredSolutionSpec 送审前设计就绪与执行证明分离

- 日期：2026-10-19
- 状态：IMPLEMENTED（依据用户持续授权；A14-P02～P09 的类型合同、Trace、Review 状态/Owner、原子送审、HTTP、Windows 组合、前端和真实 Edge/PG 闭环均已验证；不表示专项批准、Gate 3、Pilot 或正式发行通过）
- 影响 WBS：`SOL-06-A14-P01` 起
- 原基线：Gate 2 冻结 `SOL_SPEC_VALIDATE` / `SOL_SPEC_SUBMIT_REVIEW`、DM-05 StructuredSolutionSpec、A13 `DEC-20261016-1208`

## 来源、冲突与证据

冻结业务要求先形成不可变专项设计，经类型化校验后进入统一 Review；Migration 专项载荷保存 `trial_plan`、`reconciliation_plan`、`rollback_plan` 和 `acceptance_criteria`。A13 为防止把计划文字误报成执行事实，将对应检查定义为 `TRIAL_EXECUTION`、`RECONCILIATION_PROOF`、`ROLLBACK_PROOF`、`ACCEPTANCE_PROOF`，并要求全部 PASS 才可送审。

当前没有试迁移执行、对账结果或验收结果的正式 Owner，这不是遗漏的字符串校验，而是时序冲突：专项设计未评审前不能把实施执行结果作为批准事实；若又要求这些结果先于 Review，所有 Migration 专项将永久 `ready_for_review=false`。同类问题也存在于流程角色/输入输出、接口运行/认证和权限职责冲突：送审前可证明的是设计声明完整，真实运行与客户验收只能在后续实施/UAT 形成。

## 方案比较与选定方案

### 方案 A：保持执行结果作为送审前置

继续要求试迁移、对账、回滚、验收及真实运行证明全部在 Review 前存在。优点是门槛最高；缺点是违反方案评审先于实施的时序，当前数据模型/API 也没有这些结果的 Owner，无法形成可用纵向链。未选。

### 方案 B：分离设计就绪与执行验收（选定）

`SOL_SPEC_VALIDATE.ready_for_review` 仅表示固定设计具备进入人工 Review 的前置条件：不可变完整性、当前 Requirement/Section/Evidence、系列最新 DRAFT、空或已证明 Artifact、精确 `IMPLEMENTS` Trace，以及类型化设计声明完整。类型检查代码调整为：

- PROCESS_MODEL：`GRAPH_STRUCTURE`、`ROLE_DECLARATION`、`INPUT_OUTPUT_DECLARATION`
- INTERFACE_SPEC：`BOUNDARY_MAPPING`、`OWNERSHIP_RUNTIME_DECLARATION`、`AUTHENTICATION_DECLARATION`
- MIGRATION_SPEC：`SCOPE_MAPPING`、`TRIAL_PLAN`、`RECONCILIATION_PLAN`、`ROLLBACK_PLAN`、`ACCEPTANCE_CRITERIA`
- PERMISSION_DESIGN：`MATRIX_DEFAULT_DENY`、`SCOPE_DECLARATION`、`DUTY_CONFLICT_DECLARATION`

这些 PASS 只证明已冻结 payload 具有相应非空、受界、结构一致的设计声明，不证明系统已运行、试迁移已执行、回滚成功或客户已验收。人工 Review、后续实施 WBS 和 UAT 分别形成批准与执行事实。

## Review 边界

- Review Subject 固定为 `subject_type=SOL-06`、`subject_id=spec_series_id`、`subject_version_id=structured_solution_spec_id`，策略 `STRUCTURED_SPEC_ALL_V1`。
- 仅 ProjectManager 可送审；Reviewer 为同项目当前合格成员。请求沿用冻结 `ReviewSubmissionRequest`，V1 要求 `due_at`、`submission_note` 显式为 `null`，不静默丢弃。
- Subject Owner 必须在 Review 创建/开轮的同一事务内重新评估当前事实与设计就绪，不信任旧 VALIDATE Audit；同 Key 回放仍重验访问，但返回首次 Review/Round。
- 只允许同系列最新 DRAFT 且 `ready_for_review=true` 送审。启动后绑定 Review/Round 并转 `IN_REVIEW`；终态 APPROVED/RETURNED/WITHDRAWN 原子映射到版本状态，批准新版本时把同系列旧 APPROVED 转 `SUPERSEDED`。不得覆盖 payload/来源历史。

## 兼容、迁移、回滚与风险

- 冻结 URL、角色和顶层结果不变；类型检查 `code` 是冻结 API 未枚举的报告细化，但已被当前前端严格校验，因此服务端与前端必须同一版本升级。旧 Audit reason 继续可按旧合同反读，不回写历史；新观察采用新 schema/reason 版本，禁止混淆。
- 后续独立迁移只为 SOL-06 Review 状态窄门开放既有 `version_state/review_ref/review_round_ref`，不增加 Root、删除字段或改写已有 DRAFT。必须验证空库、有数据升级、down、并发、终态和非空历史保护。
- 回滚优先关闭新送审路由；已创建 Review、状态、收据和 Audit 必须保留。若尚无新观察，可回退报告合同；已有新观察时不得把新旧 reason 互解。
- 风险：设计声明虽完整但质量仍不足，必须由 Reviewer 决定；UI 必须继续明确“就绪不等于批准/执行/客户确认”。真实试迁移、对账、回滚、验收、正式信任和 UAT 不因本变更通过。

## 验证计划

1. 新旧报告 reason 严格版本化、错误互解失败；四类型正负例与派生结论单元测试。
2. SOL-06 精确 Trace Owner 验同项目、同固定 Requirement 集、ACTIVE 链接、撤销/替代/跨项目和并发。
3. Review 状态迁移与 Subject Owner 验当前 DRAFT、最新版本、当下事实重证、终态消费和历史保护。
4. 原子 submit-review 验 Session/CSRF/License/ProjectManager、Reviewer 资格、收据/Audit、同 Key 重放与失败全回滚。
5. HTTP、Windows 组合、前端和 Edge/PG 独立验收；正式服务账户、三平台、性能和 UAT 仍由后续 Gate 关闭。

## 实施记录

- 2026-10-19 / `SOL-06-A14-P02`：V2 设计声明代码、`SPEC_VALIDATION_V2_*`、V1/V2 严格反读、当前评估器和前端兼容解析已完成；Windows 11 PostgreSQL 18.6 与 Edge 独立验收通过。Trace 仍为 `UNAVAILABLE`，因此未提前形成送审资格。详见 `docs/progress/sol-06-a14-p02-structured-spec-design-readiness.md`。
- 2026-10-19 / `SOL-06-A14-P03`：新增 SOL-06 固定目标 Owner，将精确 ACTIVE `IMPLEMENTS` 覆盖受控扩展至 SOL-05/SOL-06，并接入当前事实评估器与 Windows 显式组合；Windows 11 PostgreSQL 18.6 已证明旧目标、跨项目、撤销拒绝、精确当前集合、替代恢复和共享锁，Edge 已证明缺链明确失败。未创建 Review 或改变 DRAFT。详见 `docs/progress/sol-06-a14-p03-structured-spec-trace.md`。
- 2026-10-19 / `SOL-06-A14-P04`：新增 0165 状态窄门、不可变 Review 状态回执及 SOL-06 Subject Repository/Owner；开始与批准在同一事务重算当前事实，批准替代旧版，退回/撤回保留旧批准版。Windows 11 PostgreSQL 18.6 已证明既有 DRAFT 升降重升、真实 Review 生命周期、直接写/缺回执/篡改/有历史降级拒绝和 ORM drift 为零。尚未开放冻结送审 HTTP。详见 `docs/progress/sol-06-a14-p04-structured-spec-review-owner.md`。
- 2026-10-19 / `SOL-06-A14-P05`：新增仅 ProjectManager 可用的原子内部送审 Service 与独立策略；服务端由路径版本解析不可变系列，随后由 Subject Owner 在同事务锁内重证当前事实。Review 创建/开轮、SOL-06 状态、Audit 与持久收据原子闭合，同 Key 重放仍检查当前访问。Windows 11 PostgreSQL 18.6 已证明 Audit 故障零残留、同 Key 后续成功/精确重放、请求漂移冲突及旧批准指针保留。尚未开放冻结送审 HTTP。详见 `docs/progress/sol-06-a14-p05-structured-spec-submit-review.md`。
- 2026-10-19 / `SOL-06-A14-P06`：新增默认关闭的冻结送审 Router 与应用工厂插槽；严格四字段请求、null 元数据、canonical UUID、路径/响应身份、Trace/ETag/no-store 和公共错误映射，响应系列仅来自服务端派生事实。合同、全量回归和 wheel 入包通过；尚未装入 Windows 生产组合。详见 `docs/progress/sol-06-a14-p06-structured-spec-submit-review-http.md`。
- 2026-10-19 / `SOL-06-A14-P07`：送审 Router 只在 Windows `include_secret_write` 显式写模式装配；真实 Auth/License/Project/Reviewer/Document/Evidence/Trace/Review/状态/Audit/收据链全部接入。Windows 11 PostgreSQL 18.6 已证明默认关闭、跨项目/角色/License 拒绝、当前事实失败后同 Key 成功、精确重放、漂移冲突和唯一数据库事实。前端/浏览器尚未实施。详见 `docs/progress/sol-06-a14-p07-structured-spec-submit-review-windows.md`。
- 2026-10-19 / `SOL-06-A14-P08`：新增冻结送审前端 Client、Auth 写桥与固定版本详情动作；只允许 ProjectManager 在与当前 DRAFT 严格一致的现时就绪报告后选择 ACTIVE 成员，断连/503 保留原 Key 和评审人并要求显式重试，201 明确不代表批准。前端全量、类型检查和生产构建通过；Windows Edge 真实链尚未执行。详见 `docs/progress/sol-06-a14-p08-structured-spec-submit-review-frontend.md`。
- 2026-10-19 / `SOL-06-A14-P09`：Windows 11 实际 Edge 155 经生产 Vue、FastAPI/Uvicorn 和可弃 PostgreSQL 18.6 完成成员隐藏、负责人现时验证、ACTIVE 评审人、结果未知原 Key/正文重试、201 精确重放、跨项目清屏及唯一数据库事实；上游回放同时通过。Computer Use 未暴露 Edge 表面，改用本机 Edge DevTools 协议，不把内置浏览器冒充 Edge；无产品代码、Schema、API、依赖或客户数据变化。详见 `docs/progress/sol-06-a14-p09-structured-spec-submit-review-browser.md`。
