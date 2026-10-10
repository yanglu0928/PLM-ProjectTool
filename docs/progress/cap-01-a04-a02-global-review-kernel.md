# CAP-01-A04-A02：Review GLOBAL 同事务持久内核

日期：2026-10-05。结论：`CAP_01_A04_A02_GLOBAL_REVIEW_KERNEL_PASS`。下一项：`CAP-01-A04-A03` Capability Review Subject Owner。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A04-A02
输入基线：冻结GLOBAL/PROJECT Review合同、Schema0034/0035、CR-RVW-003、DEC-836
前置任务：A04-A01前置核查与CR已完成并同步
涉及模块：review persistence/application；audit；Subject Port合同
涉及实体：Review/ReviewRound/Assignment/Decision/Snapshot/SubjectLock/RoundEvent
涉及API：无公开HTTP；PROJECT service/router保持原样
涉及权限：本项为受信caller事务内核；Session/Admin/reviewer资格/License/幂等由A03外层Owner接入
验收标准：GLOBAL提交、非终态/终态决策、撤回、Audit和Subject消费同事务；PROJECT回归零破坏
风险：伪Project、GLOBAL/PROJECT串读、终态未消费、合成Subject被误称生产Owner
```

## 实现

新增 `GlobalReviewPersistenceService` 与 `SqlAlchemyGlobalReviewRepository`。GLOBAL submit 在调用方事务中创建 Review Identity 和首轮完整结构，并强制执行 Subject prepare/lock 两次复核；决策和撤回复用既有领域状态机，终态必须由 Subject Owner消费并再次断言。所有 Review 表均写入 `scope=GLOBAL/project_id=NULL`，Audit 使用 DEPLOYMENT scope。

既有 Subject DTO 从“只接受PROJECT”收敛为冻结合同已有的 GLOBAL/PROJECT 双Scope，并明确 GLOBAL Review 只能接受 GLOBAL basis；PROJECT原规则不变。既有 PROJECT service、仓储、Router、URL、权限及结果DTO未改写。本项内核不创建UOW、不认证、不保留幂等收据、不提交事务，也未挂公开HTTP；这些必须由后续受信外层Owner完成。

## 验证

- Windows 11 / PostgreSQL 18.6 一次性数据库升级至Schema0092且Alembic drift为零；真实Review GLOBAL表完成两人APPROVED和独立WITHDRAWN，2个主题锁均释放，6个RoundEvent、7个DEPLOYMENT Audit、0条PROJECT污染。标记`CAP_01_A04_A02_GLOBAL_REVIEW_KERNEL_PASS`。
- PostgreSQL夹具使用绑定式合成Subject，只证明Review会调用和绑定Port，不作为Capability生产Owner或正式指针证据；A03必须替换为真实Capability锁与来源重验。
- 首轮夹具把RoundEvent期望数误写为7，数据库正确生成6而使断言失败；按STARTED/DECISION/COMPLETED/WITHDRAWN实际事件重新核算后修正夹具，从全新库完整重跑通过，产品实现未放宽。
- Review全量103项、后端全量2551项通过，3项既有条件跳过，0失败；此前一次从`tests/unit`作为顶层发现导致38个既有包导入错误，不计产品证据，已按仓库命令从`apps/backend/tests`重跑通过。
- 开发wheel Review 103项通过，SHA-256 `79345662fc3e278059db17f2e4917e04031b00226ec8dd2ec43408da6f92dbf7`；仅开发检查产物。`compileall`与`git diff --check`通过。

## 兼容、回滚与剩余边界

无Migration、公开API、依赖、网络、Secret或客户数据变化。可不装配GLOBAL persistence关闭新调用；既有PROJECT行为不变，已提交Review/Audit历史保留。当前尚无真实Capability Subject、Session/Admin/Reviewer资格/License/幂等外层命令，也未更新Capability状态或正式指针；这些分别留A03/A04，Gate 3继续阻塞。
