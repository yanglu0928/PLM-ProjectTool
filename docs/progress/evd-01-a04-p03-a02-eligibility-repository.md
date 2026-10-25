# EVD-01-A04-P03-A02：资格 Evidence 行锁与条件更新

日期：2026-10-01；Phase 2 Platform Core；结论：`INTERNAL_SQL_SHAPE_PASS / POSTGRESQL_PROOF_OPEN`。

输入为冻结 Evidence 状态/lock_version、CR-EVD-003 和 P02 首次裁定策略。前置为 Evidence ORM/同事务 UoW；本项仅增加 Evidence 模块最小持久层，不挂资格 API，不改 Schema。

`lock` 按 EvidenceId、scope、ProjectId 在调用方事务中 `FOR UPDATE`，仅返回固定来源、指纹、当前资格与版本。`decide` 只允许 CANDIDATE→ELIGIBLE/INELIGIBLE，WHERE 同时限定身份/范围/原状态/原 lock_version；成功才增加版本、记录理由/操作人/服务器时间并返回新版本，无匹配返回 None。正式命令还必须复验当前权限、Document 来源、If-Match、人工请求、License，写审计并完成幂等收据，不能直接暴露此存储 Port。

SQL 形状/失败关闭定向3项通过，后端全量1788项通过/3跳过。隔离PG18未运行，实际锁竞争/事务回滚/触发器未验证；当前不宣称数据库或资格功能 PASS。回滚撤未挂载 Port，无正式记录变化。
