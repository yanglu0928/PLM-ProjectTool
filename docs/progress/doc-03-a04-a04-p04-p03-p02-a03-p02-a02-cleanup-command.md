# CR-DOC-008/A03-P02-A02：已登记 Abort 文件内部清理与崩溃对账

- 日期：2026-09-26；结果：Windows 11/隔离 PostgreSQL 18.6 + 临时文件内部合成验证 PASS；未挂生产入口、未触碰用户正文。
- 决策：`DEC-20260926-134`。维护命令必须显式注入授权 Port，并在同 upload_id OS 栅栏内校验 ABORTED/CLEANUP_PENDING、Scope/Project、零正式版本、无保留时间、规范 Locator、Hash/大小。第一次没有任何物理文件且没有已持久化请求 Audit 时拒绝。通过校验后先短事务记录一次请求 Audit，之后逐路径删除，每步前再次读取候选；文件都不存在后在短事务行锁复核、写 `CLEANUP_PENDING → REMOVED` FileStateEvent 与完成 Audit。若上次请求后观察到文件已缺失，则以 `ABSENT` Audit 和独立 reason code 对账，不声称本次实际删除。
- 验证：隔离库覆盖暂存单文件、仅最终文件、同 inode 硬链接双路径、同 Key/状态重放、维护权限拒绝、首次缺失拒绝、额外硬链接拒绝、请求 Audit 失败时文件不删、双路径第一步后故障恢复、物理删除后完成 Audit 失败导致 FileObject/Event 回滚及下次缺失对账。合成数据均位于临时库/临时根，清理后关闭测试 PostgreSQL 服务。Windows 11/Python 3.13 后端 561 项无失败（2 项既有符号链接环境跳过）；开发 wheel PASS。
- Migration、公开 API、新依赖：无；版本 `0.1.0.dev0`。本项不证明正式目标账户 ACL、Windows Server 2025 或旧版无栅栏进程已经收敛。生产入口持续关闭，物理清理原阻塞只缩小为部署停写/账户与恢复演练，不据此关闭 Gate 3。
