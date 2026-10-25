# A06-P05-P02 PlanVersion Review 生命周期状态 Schema/Guard

- 日期：2026-10-26
- 结果：`SCHEMA_GUARD_PASS_OWNER_INTEGRATION_PENDING`
- Change Request：`CR-PLAN-007`（授权变更已先登记；未改写0188及Gate 2冻结提交）
- 迁移：`20261026_0190`，前序0189；新增 append-only `pln_plan_version_review_state_results`，替换 PlanVersion 根表 UPDATE 全拒绝为三列状态白名单守卫。

## 实施边界

- 仅允许状态列及Review/Round引用列参与：DRAFT→IN_REVIEW、IN_REVIEW→APPROVED/RETURNED、APPROVED→SUPERSEDED。其余PlanVersion快照列仍逐字段不可变。
- 每条生命周期事件绑定PlanVersion/Plan/Project、真实PROJECT Review/ReviewRound、Actor；校验 `PLN-02` 主体、固定PlanVersion、Round状态、Review终态/当前Round及真实Round事件。
- 延迟约束确保根状态变化必须有同事务一致的不可变事件；事件表禁止UPDATE/DELETE/TRUNCATE。
- 升级拒绝已有非DRAFT/Review指针历史；降级拒绝事件或任何非DRAFT/Review指针。0188保留，不作原地修改。
- 没有增加API、依赖或业务Owner；不代表Review送审/决定能力已经可用。

## 验证证据

- Windows 11隔离PostgreSQL 18一次性集群：0189→head、Alembic ORM drift检查、0190空状态降级至0189、再升级head全部通过；以合成Auth/Project/Plan/PlanVersion完成父级关系创建，DRAFT历史下空结构安全降级也通过。
- 数据库负例通过：修改PlanVersion内容字段和直接越权改为RESTRICTED均由`guard_plan_version_review_transition`拒绝；空事件表TRUNCATE亦拒绝。脚本输出`PLAN_VERSION_REVIEW_SCHEMA_POSTGRESQL_PASS`。
- 后端全量：`4151 passed, 3 skipped, 6206 subtests passed`。此前新增测试后首次定向发现ORM历史清单漏登记新表，已补正并通过全量回归。
- `git diff --check`、Python验证脚本执行和变更文件Secret扫描通过；无客户数据、无外发、无持久数据库写入。

## 尚未证明与后续

- 尚无PlanReview Subject/Owner，故未通过真实Review Owner执行一次合法START/APPROVED/RETURNED/SUPERSEDED正向闭环；也未声称该业务已可用。后续P05-P03核实Subject就绪条件，Owner落地后需补做正向闭环、错绑/缺事件/历史降级拒绝及事务回滚的组合PG验收。
- 该剩余验收不妨碍Schema独立任务收口，但不构成Gate/Pilot/Release结论。
- 下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P03` PlanReview Subject 当前就绪性证明。
