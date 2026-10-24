# Evidence 候选创建事务前置核查

日期：2026-10-01。WBS：`EVD-01-A03-P03-A01`。结论：`PRECONDITION_READY`，不是候选创建功能 PASS。

冻结 API-02 要求受权 POST 创建 CANDIDATE、强制 Audit 与幂等控制。当前 Evidence 已有 `EvidenceCreateAccess`（当前 Session/CSRF、GLOBAL 管理员或 PROJECT PM/IM）及 DOCUMENT/真实解析节点来源证明；数据库已有 `evd_evidence_records`，通用幂等收据和 Audit 服务也存在。尚无 Evidence 候选创建 Service、Repository、同事务收据/Audit 或公开 Router。

定位证明涉及文件 I/O，应在写事务外完成；在其后写入前，必须再次核对当前身份/角色和固定 DocumentVersion。Document 现有 `get_version_for_trace(transaction, query, document_id, version_id)` 是跨模块 Application Port，调用方 UOW 内复核当前授权、可用版本，并为 Document/Version/FileObject 加共享行锁；Evidence 不需要直查 Document 私有表。项目成员事实也可由创建权限 Port 锁定。之后在同一事务内 reserve 收据、插入 CANDIDATE、写强制 Audit、complete 收据；任何一步失败全部回滚，成功重放不复制 Evidence/Audit。

本项为代码/基线静态核查，没有写业务库、运行新功能测试或修改生产代码/API/Schema/Migration。下一任务只实现内部候选创建与同事务存储/收据/Audit，真实 PostgreSQL 并发/回滚和 HTTP 装配分项验收。正式 Session/License 及 Gate 3 仍未完成。
