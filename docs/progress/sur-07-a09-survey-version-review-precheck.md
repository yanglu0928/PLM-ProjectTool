# SUR-07-A09：调研版本校验与送审入口前置核查

日期：2026-10-25；结论：`SUR_07_A09_FRONTEND_GAP_PRECHECK_PASS`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `SUR-07-A09`；仅核查现有调研版本校验、原子送审与前端入口差距。|
|输入基线|冻结 API-04、`survey-command-v1-increment.md`、`survey-submit-review-v1-increment.md`；A08 包内调研 DRAFT 创建已验。|
|涉及模块|Survey 详情/版本 UI、Session 私有写桥、Survey Validate 和 Submit Review 客户端、ProjectMemberReadClient。|
|API|已有冻结 `:validate` 空正文幂等命令、` :submit-review` 原子命令；不得以通用 Review create/start 两步模拟。|
|权限|Validate 由服务端按项目写角色和当前事实重验；Submit Review 仅 ProjectManager，评审人必须从当前有效项目成员读取，最终资格由 Owner 事务重验。|
|验收|Validation 报告明确显示当前检查结果且不称批准；送审必须选当前客户评审成员并二次确认，未知结果保留同一评审人集合/操作号，201 只表示 IN_REVIEW。|
|风险|历史 Validation 报告会过时；客户端预筛不取代服务端来源/部门/评审人资格重验；客户批准必须由 Reviewer 实际决定。|

## 核查证据与拆分

后端 `SurveyVersionValidationService`、命令 Router、Survey Review Submission Owner/Router 已存在；Windows Survey 显式写组合装配命令和原子送审 Router。Review Submission 固定 `SURVEY_ALL_V1`，请求四字段，V1 要求 `due_at` 和 `submission_note` 为 null；ProjectManager 在同一事务中重验完整版本来源、部门、Reviewer 资格，创建并启动 Review、更新 `IN_REVIEW`、写 Audit/持久收据。通用 Review API 两步路径不能代替这个所有者命令。

前端核查发现 `ProjectSurveyDetailView` 仅列固定版本和查看问题/来源，没有 Validate、报告状态或送审入口；Survey API 缺版本验证/送审客户端，Session 仅有创建版本私有路径，没有这两条命令路径。现有 `ProjectMemberReadClient` 与 Handover 送审面板可用于当前成员候选及显式二次确认，但必须限制到 `CUSTOMER_MANAGER/CUSTOMER_MEMBER`、页完整、最多32人。

据此分为两个单一闭环：

1. `SUR-07-A10`：详情页当前固定版本 Validate 客户端、空正文 Session 桥及报告面板；显示 valid/blocking issues/warnings 与检查时间，重试同 Key，明确报告不改变状态、不是客户批准。
2. `SUR-07-A11`：ProjectManager 的 SurveyVersion 原子送审客户端和显式评审人面板；读取当前完整 ACTIVE 客户成员集合，确认后送审；未知结果保留原 Reviewer 集合/Key，成功只显示 IN_REVIEW/Review 入口。

静态核查期间无代码、Schema、API、配置、Secret、网络或数据变更；A09 本身不宣称以上前端闭环已实现。下一项进入 A10。
