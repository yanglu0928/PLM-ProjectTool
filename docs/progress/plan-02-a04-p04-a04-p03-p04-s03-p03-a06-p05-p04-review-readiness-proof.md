# A06-P05-P04 PlanVersion Review 当前就绪Proof

- 日期：2026-10-26
- 结果：`READINESS_PROOF_PASS_OWNER_COMBINATION_PENDING`
- 变更：同事务只读资格Proof与Plan/PlanVersion排他锁Repository；无Migration/API/HTTP/状态写/Review创建。

## 实施

- `PlanVersionReviewReadinessService` 只接受固定project/plan/version及服务器侧Session上下文，要求锁定事实为同project的最新DRAFT且无Review引用，并重新评估当前验证报告。失败一律收敛为不可用，不返回客户内容。
- Repository锁顺序为Plan身份后PlanVersion集合，与既有版本创建Owner兼容；持锁期间重建固定版本快照，拒绝较旧版本或已停用Plan。
- 复用 `PlanVersionValidationService.evaluate_snapshot_in_transaction` 中现有纯规则与Approved Solution/SourceProof；不调用公开Validate、不建嵌套UoW、不写Audit/Receipt。新方法不自行授权/提交；后续Subject Owner必须先完成当前Session/PM权限并在同一事务持有该锁。

## 验证

- 定向Plan readiness/validation/migration tests：11 passed。
- 后端全量：`4155 passed, 3 skipped, 6206 subtests passed`。
- Windows 11隔离PG18通过：全迁移到0190、Alembic ORM drift=0；在合成Plan下建立两个真实DRAFT PlanVersion，latest版本取得Proof、旧版本被拒，evaluator只对latest调用一次、未生成Plan Audit。标记 `PLAN_VERSION_REVIEW_READINESS_PG_PASS`。
- PG锁集成中的evaluator用Mock证明同事务委托和无写边界；Review Owner/真实当前Approved来源正向送审仍未装配。当前评估方法复用既有已验PlanVersion当前来源评估逻辑，但本新证明没有被真实SubmitReview链调用。
- 0190合法Review事件闭环、跨项目/错绑/无事件、事件历史降级拒绝仍待后续Owner PG组合验收；本项不代表Review功能可用或Gate通过。

## 下一项

`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P05`：PlanVersion Review Subject的Review Create/Start Owner，把当前Proof、Review/Round记录、0190 START结果、Audit及幂等Receipt编排到同一事务；先做其编码前核查。
