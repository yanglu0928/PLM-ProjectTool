# A06-P05-P06-P04 PlanVersion SubmitReview HTTP 前置核查

- 日期：2026-10-26
- Phase：Phase 2 Platform Core
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P04`
- 基线：API-01/02/04冻结ReviewSubmissionRequest与`PLAN_VERSION_SUBMIT_REVIEW`；CR-PLAN-007～009及Migration 0190/0200/0210；P05原子Plan Submit/Start Owner、P06终态Owner与显式Windows Registry。
- 前置：P06-P03 `PASS_SCOPE_LIMITED`；PlanVersionReviewSubmissionService已有内部单事务同Key响应服务。
- 结果：`PRECHECK_PASS`

## 编码前检查

- 目标：为冻结业务Operation实现独立HTTP适配器并仅装入显式Windows平台Write组合；不得让客户端串行调用通用Review Create/Start冒充原子业务操作。
- 请求：POST `/api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}:submit-review`；无query。body严格四键`reviewer_ids/policy_ref/due_at/submission_note`；reviewer UUID互异、1..32个；policy固定`PLAN_VERSION_ALL_V1`；当前Review数据模型无due_at/submission_note，二者必须显式为null，非空/未知字段422或请求形态400，不能丢弃。Plan与PlanVersion都从路径固定。
- 安全：严格可信Origin/Host、当前Session+私有CSRF；要求打印ASCII 16..128字符Idempotency-Key；License和当前ProjectManager；授权人/Reviewer/Plan归属/Version最新性/来源Proof在同一个Unit of Work复核，Review/Round/Plan START结果/Audit/Receipt原子提交，之后License再复核。错误Envelope使用既有`ApplicationError`/trace_id，不回显内部异常。
- 成功：201；最小ReviewRef+RoundRef，`ETag: "v1"`、`Cache-Control: no-store`；不回显正文、文件位置、内部表或信任材料。异载荷同Key冲突；同载荷返回首次不可变引用。
- 依赖：复用P06-P03显式Review composition所使用的PlanVersionValidationService、SQL Reviewer qualification、Audit、Project authorization和相同Subject Owner回调；Review router / Plan业务路由同属显式write组合。普通默认与login-only须维持404。
- 测试：API形态/边界/Envelope/权限/重放合同；Win11隔离PG18真实HTTP到Submit Owner→Review/Round/0190 START/Audit/Receipt及同Key精确重放；拒绝非法来源/版本、Project、Reviewer及Audit故障整体回滚；default/login-only 404；Review/Plan既有端到端PG夹具回归。

## 偏差与决定

无API或Schema偏差，不需新增CR。冻结DTO虽定义`due_at`和`submission_note`，当前统一Review模型无对应事实；采用与其他SubmitReview一致的显式null兼容处理。当前Lesson：来源Evaluator必须使用和显式WindowsReview完全一致的构建图；任何合成授权或来源替身结果单独注明，不得写成正式验证。

前置满足。下一步实现PlanVersion SubmitReview Router和显式Write组合，保持默认/login-only未挂载。
