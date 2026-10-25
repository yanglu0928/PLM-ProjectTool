# ADR-012：维护准入与实际进程静止分离

日期：2026-09-30；状态：`ACCEPTED_UNDER_CR_PLT_004 / PARTIALLY_IMPLEMENTED`；原 Gate 2 冻结提交 `64cdf09` 不追写。

## Context

ADR-007/008 要求升级前先拒绝新任务、收敛 Worker，再备份和 Migration。HTTP 上传与 OCR 跨文件 I/O 和多个数据库短事务；仅停止一个进程、仅查布尔状态或按 UploadId 的本地锁均无法协调全部生产入口。`CR-PLT-004` 记录方案、迁移及并发验收。

## Decision

1. PostgreSQL 18 的单行 `plm.plt_maintenance_state` 保存 `RUNNING`/`MAINTENANCE`、单调版本及数据库时间。`0051` Migration 是 Gate 2 后可追溯增量。
2. 所有被允许的生产写窗口需先持同一固定键的会话级共享 advisory lock、读 RUNNING，窗口结束后显式释放；DB 不可用、状态非 RUNNING 或锁竞争失败关闭。HTTP 按非安全方法及实际有错误路径 Audit 写入的四个 GET content 下载准入；普通只读 GET/健康不占锁。不得把仅在事务内持锁或起点读状态视为完整门禁。
3. 状态转换以该键的限时排他锁等待共享窗口收敛，状态与 USER Audit 在同一事务提交。当前 Session+CSRF+DeploymentAdmin 身份在此事务内核验，不接受调用方声明操作员 UUID。
4. Windows 本机工具仅使用调用 OS 账户的 Credential Manager 数据库凭据，并要求交互式应用管理员口令；短期 Session 操作后撤销。工具不接收命令行/环境变量 Secret，也不作为普通 HTTP 路由提供。
5. 数据库连接意外断开会自动释放会话锁，而持锁进程可能继续文件 I/O。因此排他锁和维护状态仅证明健康连接下的准入协调，**不证明备份/迁移所需的实际静止**。进入备份/迁移前必须另行停止并枚举全部生产 API、Worker、清理与旧版进程，取得 OS 服务/进程退出和文件句柄收敛证据；证明不完整则不得执行。

## Evidence and remaining conditions

Windows 11 隔离 PG18：`0051` Schema、共享/排他锁、状态/Audit 原子切换、真实 Auth 管理员核验、本机工具内部 scrypt 登录/Session 撤销，以及三种显式 Windows 生产 API 组合的登录/上传/四 GET content 准入已验证。杀死持锁数据库 backend 后排他锁可得而原调用者退出报错，证实第5点风险。双 Worker、目标 OS 账户 ACL、Windows Server 2025/Debian 入口、20并发性能、旧版进程与备份恢复演练未通过；本 ADR 不能作为维护模式或 Gate 3 PASS。

## Alternatives / rollback

只停进程无法防竞态与重启；只查 DB 状态存在检查后继续 I/O 的 TOCTOU；长事务锁会拖累数据库且不能覆盖外部文件。回滚为未装配的门禁/工具停用及人工恢复匹配版本代码与数据库；已有维护历史的 `0051` 不自动降级、不删除 Audit。任何改变固定锁键、状态图或运维边界需新 CR 与跨进程验收。

Trace：V2.1 升级流程、ADR-007/008 → `CR-PLT-004` → `PLT-MAINT-01` → DB0051 / admission / transition / Windows CLI → A04～A06 待验。
