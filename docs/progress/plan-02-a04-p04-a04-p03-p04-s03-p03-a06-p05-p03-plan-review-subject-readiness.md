# A06-P05-P03 PlanReview Subject 当前就绪性核查

- 日期：2026-10-26
- 结果：`PRECHECK_COMPLETE_SUBJECT_OWNER_NOT_YET_REGISTERED`
- 范围：只核对冻结合同、PlanVersion现有来源/验证证明、Review通用装配及下一Owner的前置；本项没有产品代码、Schema或API改动。

## 编码前检查与证据

1. 冻结 API-04 已定义 `PLAN_VERSION_SUBMIT_REVIEW`：`POST /api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}:submit-review`，仅ProjectManager可发起，成功返回ReviewRef+RoundRef；计划必须通过层级、DAG、日期/负责人/验收和覆盖校验。通用Review create/start HTTP 不替代该业务原子编排。
2. `ValidatePlanVersion` 已有事务Owner、当前Approved Solution与来源证明、持久验证报告/Audit/Receipt，可作送审前事实输入；返回报告以不可变PlanVersion快照指纹绑定。送审Owner仍需在同一事务内重新读取/锁定DRAFT/latest PlanVersion并重证报告及输入来源，不能复用过期Validate作为当前授权。
3. Review应用核心提供独立 `ProjectReviewSubjectRegistry` 与只读Registry，未知Subject失败关闭；`windows_project_review` 的现有写/读Subject列表均无 `PLN-02`，当前没有Plan Subject Owner、Repository、SubmitReview route或Windows组装。
4. 0190现已提供状态白名单及事件闭合基础。后续Owner须用统一Review核心创建真实PROJECT Review/ReviewRound，主体形状固定为 `subject_type=PLN-02`、`subject_id=subject_version_id=PlanVersionId`，并将Version状态/引用、Review Round/快照/Assignment、事件结果、Audit和Receipt纳入同一事务；不得直接自建并行Review状态机。
5. 当前没有生产端合法Plan Review Subject，所以0190的真实合法正向事务/Reviewer决定尚不能由本项证明；保留为Owner PG组合验收，不把内部Schema Guard负例说成业务通过。

## 风险与下一项

- 风险：仅相信先前Validate会造成送审前来源已变更仍可送审。Owner必须在Review锁定前重跑当前来源证明/验证资格，并在复核失败时事务零残留。
- 风险：在通用Review Registry之外另建提交路径会绕开统一角色、Assignment、Round、回执和Review状态事实；下一任务仅通过正式Subject回调扩展Registry。
- 下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P04`，实现PlanVersion Review Subject最小送审资格/Start内部Owner与持久层；不接公开HTTP或终态决定，先按该切片前置核查及测试边界实施。
