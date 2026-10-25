# PAR-01-A05-P01-P04-P03-P04 Parser 过期取消候选扫描

日期：2026-09-30；Phase 2；编码前检查完成；Windows 11 内部验证 PASS。

当前 Phase：Phase 2 Platform Core。
当前 WBS：为上一步已验的 Parser 到期取消恢复增加可轮询的候选发现和单步调度，不在扫描事务中变更业务终态。
输入基线：Gate 2 冻结 Job/Outbox、ADR-007、ADR-011、CR-PAR-001/002 和 `PAR-01-A05-P01-P04-P03-P03`。
前置任务：取消请求 Owner、真实租约到期恢复及确认丢失核验在 Windows 11 内部 PASS；Gate 3 未通过。
涉及模块：Jobs 候选 Port/Repository；Parser 调度应用层。
涉及实体：Job、JobLease、JobAttempt；调度不新增表。
涉及 API：无公开 `/api/v1` 变化。
涉及权限：仅同一受控 SystemActor 启动/运行前重复校验；候选不能授予业务权限，实际恢复沿用来源与当前代证明。
验收标准：真实 PG 时间过滤 PROJECT/document/DOCUMENT_PARSE/CANCEL_REQUESTED 的到期活代，稳定游标和有限单步；未到期、其他 Owner、错误代数不候选；竞争后由恢复再次验证；确认丢失只读验证，不重复写；真实 PG/HTTP 合成来源及后端回归 PASS。
风险：候选畸形或已被他方改变可导致头部阻塞；游标跳过被拒候选，周期结束复位；不得将本项称为独立生产进程或 Server 2025/Debian 验收。回滚为停用调度，保留历史；无 Schema/数据迁移。

实施：Jobs `ExpiredParserCancelCandidates` + PostgreSQL 非锁定单候选查询，按 `lease_expires_at/job_id` 游标有序；Parser `ParserExpiredCancelSweep` 将候选转换为原代命令，真正变更仍交前一步恢复 Owner 重锁重核，未知提交回执只读确认，同一 SystemActor 两次校验。后续周期在本轮游标耗尽后复位，单步只处理一个候选，不在扫描事务中变更终态。

验证：Windows 11 隔离 PostgreSQL18/真实已提交合成文件/HTTP 用户取消：未到期空扫描，两个到期 Job 有序候选与有/无 ParseRecord 恢复，身份源失效零写，恢复提交后回执丢失只读核验、唯一 Audit。单元测试覆盖另一 Worker 抢先收口的 `SUPERSEDED`、扫描期间身份变化和不同身份注入拒绝。后端 Python3.13 全量 1638（3 既有跳过）、wheel PASS；PoC PG 验后停止。无 API、Schema、依赖或生产数据迁移。

剩余：此调度步骤尚未装入独立 Parser Worker 进程；正式 Windows 运行账户 SystemActor/License/Project 来源、维护模式与进程信号、Server2025/Debian 仍按后续任务验证。不能据本项关闭 Gate3 或宣称程序包可用。
