# DOC-03-A04-A04-P04-P03-P02：已登记文件物理清理前置核查

日期：2026-09-26；状态：PRECONDITION_BLOCKED，不执行生产或本地已登记正文删除。

依据冻结 DM-03、ADR-007/008 及项目开发 Skill 的编码前检查：Abort P01 已能把有内容的 Intent 原子置为 ABORTED、FileObject 置为 CLEANUP_PENDING，但当前 `CommitUploadService` 在首次短事务预检后、第二次提交前于事务外执行文件提升；`ReceiveUploadContentService` 也在两次事务之间持有文件操作。仓库尚无覆盖这两个窗口的生产停写证明或同一 upload_id 的跨进程互斥。若只凭数据库 ABORTED/CLEANUP_PENDING 与文件 Hash 删除，已经通过预检的并发请求仍可能稍后操作同一路径，形成误删/孤儿或假 REMOVED。仅文件 Hash、TTL 或一次数据库行锁不足以证明安全。

解除条件：建立可在 Windows 11/Server 2025 目标账户运行、覆盖 Content/Commit/Abort/清理整个外部 I/O 窗口的可靠互斥或维护模式停写栅栏；清理前后核对 Scope、Intent、FileObject、零正式版本/保留引用、规范 Locator、文件身份/Hash/Size，异常和中断须保留 CLEANUP_PENDING 并可对账重试；验证活跃写入、崩溃、双路径硬链接、仅最终文件、损坏和审计失败。该安全机制若改变冻结设计，先建 CR 并保留原版本。未满足前，P03-P02 不标 PASS；转独立的 Commit/Abort HTTP 契约工作，Abort 仅返回待清理，不宣称物理销毁。
