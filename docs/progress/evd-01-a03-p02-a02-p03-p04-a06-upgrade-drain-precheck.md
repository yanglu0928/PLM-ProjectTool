# DOCX 解析版本升级排空前置核查

日期：2026-10-01。WBS：`EVD-01-A03-P02-A02-P03-P04-A06`。结论：`PRECONDITION_BLOCKED`，仅影响正式部署升级排空验收，不推翻 V1/V2 结果在隔离库中的共存证据。

Parser Worker 已有 PostgreSQL 维护共享锁、协作停止与 `quiescent()` 静止边界；维护转换持排他锁并将状态切至 MAINTENANCE。原有 Windows 三角色 SCM runner 在合成工作/心跳场景通过，但不能以源码或数据库状态推定目标账户的旧 Worker 已退出。本机运行只读 `service_inventory_windows ALL` 返回 API、Audit Worker、Parser Worker 三项 `installed=false`，报告固定为 `DIAGNOSTIC_ONLY` 且 `backup_or_migration_authorized=false`。当前没有可据以演练升级的正式服务安装、目标账户/信任源或旧版 V1 运行中作业。未执行实际停服、生产备份或迁移。

正式关闭条件：在受控目标安装中进入维护态、让旧 Parser Worker 完成或按既有恢复流程处置 RUNNING V1 尝试，取得三个服务的 SCM 状态与 PID/标记、未知旧进程与数据库会话/文件 I/O 静止证据；在同一排他维护窗口复核后才允许复制或迁移。若任一未知或失联，拒绝升级；失败按人工备份恢复原代码和数据库，不删除 V1/V2 ParseRecord。此流程受 [CR-EVD-001](../changes/CR-EVD-001-docx-section-source.md) 和既有维护/发行门禁约束。

Changed：仅本核查记录及状态指针。生产代码、API、Schema、权限、依赖、Migration 与发行包均未变化；新功能测试未运行。Gate 3 与 Release Gate 保持 OPEN。下一独立任务：Evidence 候选创建的事务/收据/Audit 前置核查。
