# DOC-03-A04-A03-P03-A02-P02 未登记 Content 孤儿恢复

日期：2026-09-26。追溯：冻结 API-02 `DOCUMENT_UPLOAD_CONTENT`、DM-03 崩溃恢复矩阵、ADR-008、DEC-20260926-106。结果：内部合成恢复 PASS，公开 HTTP/TTL 清理未完成。

暂存写入从文件独占创建开始持有操作系统非阻塞排他锁，关闭句柄后由系统释放；恢复端只在同一确定性 Locator 的普通单链接文件能够取得该锁时检查。其请求正文须完整匹配声明 Length/SHA-256；暂存文件在持锁期间需通过身份、Size、Hash、扩展名/MIME/文件特征检查，随后重新授权并在既有 Project→Document→Intent 行锁顺序下原子登记 STAGED/Event/Intent/Audit。活跃写入、残缺/损坏或类型不符、Intent 状态变化均失败关闭；不覆盖、不删除未知文件。

Windows 11/Python 3.13：474 项后端测试无失败（2 项符号链接权限跳过）；PostgreSQL 18 临时库和合成文件验证审计回滚后的孤儿可恢复、活动写入锁拒绝、关闭后完整文件可恢复、损坏孤儿拒绝、只登记/审计一次，以及上一项权限/Token/并发回归；另验证合成子进程异常退出后锁释放与重新接管。开发 wheel 构建通过。无 Migration、公开 API 或新依赖。

下一项 P03：按 TTL、数据库状态和文件身份受控清理未登记孤儿；必须避免误删活动上传及任何已登记 FileObject。正式 Session/License/CSRF/Project Role、Commit/Abort、Parser Job/Outbox、Server 2025/Debian 13 和可用程序包仍待，不标 Gate 3 PASS。
