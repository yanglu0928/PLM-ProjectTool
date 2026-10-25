# PLT-PKG-01-A08-P09-P05-P03-A07-P03-P04-P02-A01：JBIG 阻断与带数据备份恢复演练

日期：2026-10-01；状态：`SYNTHETIC_BACKUP_BLOCK_RESTORE_PASS / PRODUCTION_UPGRADE_OPEN`。

编码前检查：Phase 2、Gate 2 已通过，Gate 3/发行仍未通过。输入为 CR-PKG-004、P04-P01 维护锁下 FileObject 全量预检及 Release 固定“人工备份→维护→停写→升级→Migration→健康检查”流程。本任务只验证备份数据能否在隔离环境恢复，以及 JBIG 命中时升级动作不得继续；不修改正式升级器、Schema、API、Parser、客户数据或系统服务。前置为本机 PostgreSQL18.6 临时集群与全新数据库已迁移到 `20260930_0051`，其 `data_directory` 和测试库空状态在脚本中逐项复核。涉及实体：合成 `auth_users`、`doc_file_objects`、维护状态；无公开 API/权限变化。验收为四类备份文件 Hash、完整数据库 dump/restore、JBIG 阻断后原 Schema 不变、受损隔离副本与恢复副本区分、测试源库清理/维护态复原。失败只停止演练，不对现网执行迁移/恢复。

`tools/tests/integration/verify_jbig_upgrade_backup_restore.py` 仅接受匹配的临时 PG 数据目录、固定本机 127.0.0.1:55483 测试库及新 ASCII 输出目录，绝不读取正式凭据。测试在完整 Schema0051 下创建纯合成用户与 JBIG TIFF FileObject，用 `pg_dump -Fc` 和文件复制保存数据库、data、config、license；进入 MAINTENANCE 后调用真实只读预检得 `BLOCK_JBIG`，检查迁移版本仍为0051、无合成升级标记。随后将同份 dump 恢复到两份全新隔离库，使其中一份合成用户记录受损，再证明另一份恢复库仍含原用户名、文件 SHA/长度与迁移版本；三个文件目录从备份复制后逐件 Hash 相同。两轮均退出0，源测试库已删除合成记录、恢复 RUNNING；临时 PG 已正常停止。第二轮忽略输出中的合成备份 SHA：数据库 `3ace2feaaebb5d07e4182e95a350ca43748a91a863686b0e9fc5122b70f7ea1d`，文件 `f2b05f4ab1a8b615f9d69238692423e638b1d30c994b15fbb511cab75bf049ea`，配置 `14c5bd2cdc8275d2d4ff83998ad65bf8df21a8fd7c183db6864881b2cd5af61d`，License 占位 `d5e6da558465a88502c98719732360235f518684ea09a41219a6ababbf04acc4`。它们不含客户数据、有效 License 或 Secret，二进制仅在本机临时目录，不入 Git。

边界：这是隔离副本恢复，不是覆盖原数据库/目录的现场恢复；未验证 pg_dump 备份期间并发写入、正式服务账户、真实 SCM/旧进程停写、备份加密/保管、损坏备份拒绝、升级器实际调用顺序、Migration 失败自动阻断或目标 Windows Server 2025。生产流程明确不自动回滚，恢复仍由实施团队人工完成。P04-P02 不能标完成；下一子任务须让正式升级入口只接受可复核的备份、维护状态、OS 进程/服务静止与预检结果，缺任一证据不得开始任何复制/Migration。现有进程/服务诊断恒标 `DIAGNOSTIC_ONLY`，不提供停写证明，故先补该前置并继续独立发行工作。`release_eligible=false`。
