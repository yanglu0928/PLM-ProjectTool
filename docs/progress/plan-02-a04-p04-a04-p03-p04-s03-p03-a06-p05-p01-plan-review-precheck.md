# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P01：PlanVersion送审前置核查

日期：2026-10-26。结果：`PRECHECK_COMPLETE_WITH_CR-PLAN-007`；仅静态核查/登记授权CR，无Schema/运行变化。

## 编码前检查与冻结合同

- 当前Phase：Phase 2 Platform Core。
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P01`。
- 冻结Operation：API-04 `PLAN_VERSION_SUBMIT_REVIEW`，PM角色、Session/License/CSRF/Idempotency/Audit，201 ReviewRef + RoundRef。
- 通用Review Kernel已有PROJECT Submission Owner、Subject Registry、Reviewer资格、同事务Create+Start/持久Receipt；Outline/Section Review Subject模式可作为窄范式。Plan尚无Plan Review Subject Owner及Submission Owner。
- 通用Frozen ReviewSubmissionRequest可复用reviewer_ids、policy_ref等，但Plan operation行未单列其具体body；编码前据既有Review Submission DTO与固定API向后兼容建立显式Plan请求合同，禁止无用户指定Reviewer时静默自动选人。
- 送审应PM-only；IM只可维护/创建/验证，不能代替PM提交。验证成功不等于Review批准；Review决策必须仍由合格Reviewer在统一Review流程作出。

## 阻断发现及CR

- PlanVersion DB模型含version_state/review_ref/review_round_ref，0188后触发器却对PlanVersion根行任意UPDATE报错；现有SubmitReview和Review Subject无法原子绑定状态。这是数据库事实，不可由API/服务层绕过。
- 已先登记`CR-PLAN-007`：追加0190，仅允许白名单状态/Review指针跃迁，PlanVersion内容仍不可变；每次状态改变用同事务append-only Review状态结果证明与真实Review/Round一致；有历史时拒绝降级。
- 这是需先执行的L3 Schema偏差；未改0188或冻结基线，不需用户再次批准但不得无验证部署。

## 下一步范围

- 先做`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P02`：实现CR-PLAN-007 Migration/ORM状态事件与触发器，并用隔离PG18验证空库、合法/越界状态更新、事件身份配对、不可变及历史安全降级；尚不挂Review API。
- 后续独立实现Plan Review Subject Readiness（当前Approved来源、Validate内容规则、任务完整性、Reviewer资格）与SubmitReview事务Owner；然后才接可选HTTP/Windows write路由与完整Pg/Review决定测试。
- API合同、Scope/License、Gate2原始冻结保持；不存在自动批准或AI事实。

## 已知限制

在CR-PLAN-007 Schema/Owner/Review资格完成前，PlanVersion可Validate并返回报告，但不可安全送统一Review；Pilot的项目→交接→调研→需求→原型→方案→实施WBS纵向链仍未闭合。Gate 3/Pilot/Release保持未通过。
