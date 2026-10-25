# A06-P05-P05 PlanVersion Review Create/Start Owner

- 日期：2026-10-26
- 结果：`OWNER_PERSISTENCE_AND_0190_START_PASS_SCOPE_LIMITED`
- 前置核查：[`P05-P05编码前核查`](plan-02-a04-p04-a04-p03-p04-s03-p03-a06-p05-p05-precheck.md)
- L2路径身份决策：[`DEC-20261026-PLAN-REVIEW-PATH-01`](../decisions/decision-log.md)

## 变更

- 新增`PlanReviewSubjectOwner`，以`PLN-02`绑定固定PlanVersion；只允许最新DRAFT且无Review指针，Create/Start都复核同一行锁。Start在同一事务使用P05-P04只读Proof，复核当前来源/校验并验证客户评审人资格；Proof失效统一拒绝，不记录来源正文。
- 新增Plan Review SQL仓储，锁顺序保持Plan identity→PlanVersion集合。统一Review插入首轮后，Owner将PlanVersion推进到`IN_REVIEW`并追加0190不可变`START`结果；错误更新/事件写入失败会使调用方事务整体回滚。
- 新增`PlanVersionReviewSubmissionService`，按同一UoW验证Session/CSRF、License、ProjectManager授权及评审人，校验路径Project/Plan/PlanVersion精确归属，再预留幂等Receipt并调用统一Review的同事务Create+Start；成功Audit/Receipt与首次201在唯一commit中闭合。重放仍检查路径归属和当前Subject访问，不再次建Review/Round。
- 未增加Migration/API/公开HTTP/Windows组合。由于Plan Subject尚未实现终态 callbacks，明确不注册到要求完整生命周期的Review Registry；本服务目前是内部可注入能力，不代表用户可从程序界面使用送审。

## 验证

- 定向Owner测试：5 passed；覆盖最新版本限制、绑定身份/当前Proof委托、Review状态绑定、Project授权拒绝、错Plan路径在Receipt前拒绝。
- 后端完整回归：`4160 passed, 3 skipped, 6206 subtests passed`。
- Windows 11隔离PostgreSQL 18验证全量迁移至head、Alembic ORM drift=0；由真实Review创建/Start持久化层在同一UoW写入Review、首Round/STARTED事件、PlanVersion `IN_REVIEW`、0190 START结果、两条Audit与SubmitReview Receipt；同Key精确重放返回原Round。
- 在同一隔离PG18验证当前事实Proof拒绝时零Review/Audit/Receipt残留；在Round与0190事件已写入后注入第二条Audit故障，Review/Round/START事件/Plan状态/两条Audit/Receipt全部回滚；用同一Key重试成功。
- PG组合验收中的Session认证、License、Project授权、外层Reviewer锁定、Subject reviewer facts及当前来源Evaluator使用测试替身。故仅证明事务持久化/数据库触发器闭环和失败回滚；没有证明真实Approved Outline/Section/Requirement来源的正向校验、真实Session/License/Project授权、生产装配，也没有证明Review终态。
- 无正式客户数据、外发、Secret或正式数据库操作。工作区原有`.tmp/`未触碰。

## 范围与风险

- 0190延迟约束在真实PostgreSQL最终commit接受真实PROJECT PLN-02 Review/Round/Actor事实及START结果，非法/缺事件状态无法提交；数据库组合测试不再用直接SQL伪造Plan状态。
- 本Owner未接公开HTTP或Windows启动根；浏览器、源材料正向送审、终态决策、正式信任和Gate/Pilot仍未通过。
- 数据Schema保持0190，无API Breaking Change。应用回滚为撤下未装配的内部Owner/Service；不降级Schema，不删除任何已发生的Review历史。

## 下一项

`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06`：依据DEC-20261026-PLAN-REVIEW-TERMINAL-WBS-01继续终态闭环；其前置核查已把工作细分为`...-P06-P01`Approved指针Schema和`...-P06-P02`终态Owner。真实来源正向验收仍是后续组合门槛；完成终态前P05链不挂载Registry/HTTP。
