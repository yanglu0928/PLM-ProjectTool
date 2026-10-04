# DOC-03-A04-A03-P03-A02-P01 已登记 Content 安全重传

日期：2026-09-26。追溯：冻结 API-02 `DOCUMENT_UPLOAD_CONTENT`、DM-03、ADR-008、DEC-20260926-105。结果：内部合成验证 PASS；公开上传和孤儿接管未完成。

同一创建者在 Token 未过期、Scope/Project 与当前授权仍有效时，CONTENT_READY 可使用原 upload_id 重传。必须读取整个请求正文并核对声明长度/SHA-256；FileObject 必须仍是同 Scope/Project、确定性暂存 Locator、STAGED 状态且 DB 元数据匹配；暂存实体再次校验 Hash/Size，随后在短事务重新授权、按 Project→Document→Intent 行锁复核。成功返回原文件元数据，不新增 FileObject、事件或 Audit；不同正文/声明、非法 Token、跨主体、文件损坏和状态变化失败关闭。Commit 后的状态不在本次重传范围。

Windows 11/Python 3.13 后端 472 项无失败（2 项符号链接权限跳过）；PostgreSQL 18 临时库/合成文件验证相同正文重传、缺失/不同正文、异声明、非法 Token/异主体、文件损坏再恢复、并发单次登记和单次审计；开发 wheel 构建通过。无 Migration、公开 API 或新依赖。

未登记孤儿文件不能只因 Hash 一致便接管：活跃上传可能仍持有可写句柄。P02 须先实现可证明无活动写入的租约/停写机制及接管，P03 再按 TTL、数据库状态和文件身份执行受控清理。当前保留孤儿、不盲删。正式 Session/License/CSRF/Project Role、公开 HTTP、Commit/Abort、Parser Job/Outbox、Server 2025/Debian 13 和可用程序包仍待，不标 Gate 3 PASS。
