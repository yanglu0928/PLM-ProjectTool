# AI-04-A06-P08-P03 过期 AI Task 崩溃对账

日期：2026-10-03；状态：`EXPIRED_TASK_RECONCILIATION_PASS`；依据 CR-AI-018、DEC-753/758～760、P08-P02。

通用 Jobs claim 现在排除 Lease 已过期的 `ai/AI_TASK_EXECUTE` RUNNING Job，避免越过Provider发送栅栏后自动创建下一Attempt并重复外发。新增AI Owner专用对账：锁定一个过期Job及其当前Lease/Attempt、Task/current Invocation；RUNNING Invocation保守收敛为`AI_PROVIDER_OUTCOME_UNKNOWN/retryable=false`，PENDING Invocation收敛为`AI_WORKER_LEASE_EXPIRED/retryable=true`（仅表示后续显式新generation资格）。Lease置EXPIRED，Job/Attempt/Invocation/Task与Project Audit同事务FAILED；Audit失败全回滚，旧Worker fencing不能覆盖。

Changed/Files：Jobs Lease claim过滤；新增`reconcile_expired_task.py`、`expired_task_reconciliation_repository.py`、单元和Win11/PG验证；CR/DEC/状态/版本说明。Migration/API/Dependencies：无。Compatibility/Upgrade：仅收紧AI Owner的过期Job处理，Document/Audit等现有Jobs恢复不变；需部署对账循环后才具运行闭环。Rollback：停止AI消费/对账并撤过滤和Owner，但不得把已FAILED历史复活；未对账RUNNING保持只读等待向前修复。Known Issues：生产Worker/对账循环装配、用户取消、显式Retry generation、Server 2025/Gate 3/UAT/可用包仍待。

验证：Windows 11/PostgreSQL 18.6真实AI Task链完成一次合成Adapter调用后把Lease安全推进为过期；通用claim未领取该Job，Audit故障时全回滚，随后专用Owner原子UNKNOWN/FAILED；重复扫描为空，旧Worker写被拒。单元3项、后端全量2259运行/3跳过；开发wheel SHA-256 `e8fbcb05e52d93da3f2344b8bddafacdd6fca5847fa0e1341bbefbdc672a0504`。零真实Provider/客户数据外发。
