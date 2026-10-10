# DOC-03-A04-A03-P03-A01 内部 Content STAGED 登记

日期：2026-09-25；结果：内部 Content→STAGED 子任务合成 PASS，公开 Content 与完整重传未完成。追溯：冻结 API-02、DM-03、ADR-008、`0024`、DEC-20260925-104。

内部命令在短事务中检查注入授权 Port、创建者/Scope/Project、Token 摘要、数据库过期、Intent CREATED 和项目状态；事务外以 `upload_id` 作为确定性 FileObject ID 完成独占暂存、大小/类型/Hash 检查。流结束后重新验证物理字节，并在新短事务中重新授权、按 Project→Document→Intent 行锁检查状态，原子写入 `FileObject(STAGED)`、初始文件状态事件、`UploadIntent(CONTENT_READY)` 和 Audit。Token 原值与正文不进入数据库或日志，FileObject 仍不可被正式 DocumentVersion 引用。

Windows 11/Python 3.13：后端 471 项无失败（2 项符号链接权限跳过），PostgreSQL 18 独立临时库与合成文件验证正常暂存、Token/跨项目/异主体拒绝、单次事件/Audit、重复 PUT 拒绝、双请求并发只登记一次、上传中 Intent 终止与项目归档、Intent 过期及审计失败全事务回滚；开发 wheel 构建通过。测试仅使用合成授权和 Key，临时库/文件已删除，数据库服务已停止。无新 Migration、公开 API 或依赖。

已知窗口：若文件已暂存而后置事务拒绝或提交结果不确定，会留下无 FileObject 的不可见孤儿；不能盲删或假定未提交。DOC-03-A04-A03-P03-A02 须实现按固定 ID/Hash/文件身份的安全重传与孤儿恢复/TTL 清理。正式 Session/License/CSRF/Project Role 授权适配、生产 Token 密钥、HTTP、后续发布/Commit/Parser Job、Server 2025/Debian 13 与最终程序包未完成，不标 Gate 3 PASS。
