# DOC-01-A05-P03 内部受权下载快照编排

- 日期：2026-09-26；状态：内部 Application Service 合成端到端 PASS；下载 HTTP 尚未开放。
- 基线：冻结 DM-03/API-02、下载前验证快照 DOC-01-A05-P01、受权来源 DOC-01-A05-P02；决策 `DEC-20260926-130`。
- 实现：先获取当前受权 Actor/Version/FileObject 来源，完整复制并验证私有快照；交付快照前再次验证 Session/License/Project/Document/Version/FileObject 并比较来源。源文件缺失或 Hash/大小/身份异常时，在独立短事务记录无路径、无正文的 `DOCUMENT_DOWNLOAD_INTEGRITY_FAILED` Audit，不擅自改变 FileObject 状态；Audit 不可写时同样拒绝。权限/状态变化时关闭快照，响应调用方必须关闭成功快照。
- 验证：Windows 11/Python 3.13 后端 534 项无失败（2 项既有符号链接环境跳过）；单元测试 4 项覆盖成功关闭、状态变化、完整性失败及 Audit 失败；隔离 PostgreSQL 18.6 + 临时物理文件同链路验证好文件字节、坏文件只一条 Audit 且文件状态不变、复制后 RESTRICTED 关闭快照；开发 wheel PASS。首次合成测试因 `available_at` 早于数据库创建时间被既有约束拒绝，修正测试时间后通过；没有改变 Schema。临时库/文件删除，测试服务停止。
- 无 Migration、新依赖或公开 API 变化。并发临时磁盘容量、HTTP 流式响应/中断清理、正式发行信任源和目标环境仍待；本项不把内部快照视为已交付下载 API。
