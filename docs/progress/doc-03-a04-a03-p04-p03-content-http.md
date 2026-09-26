# DOC-03-A04-A03-P04-P03 流式 Content HTTP

日期：2026-09-26；追溯：冻结 API-02 `DOCUMENT_UPLOAD_CONTENT`、DM-03、DEC-20260926-113、内部两阶段 Content 与 P04-P01/P02 授权。

实现：显式 Windows `--platform-write` 装配 GLOBAL/PROJECT 固定路径 PUT；可信 Origin、Session/CSRF、Upload Token、规范 Content-Length、`X-Content-SHA256` 和 `application/octet-stream` 为前置。HTTP 在 AnyIO 工作线程逐块拉取请求流，单块最多 1 MiB，不整体读取到内存；最大 100 MB。现有受控 Storage 完成类型、长度、摘要、文件形态校验，Content 首传/重传维持原数据库幂等。服务在流前和流后、数据库阶段前分别重查 License Guard，事务内重查当前 Session/角色/创建者。200 只返回 upload_id、大小、摘要、detected MIME，不返回物理路径，也不创建 DocumentVersion。

验证：Windows 11/Python 3.13 后端 495 项无失败（2 项符号链接权限跳过），开发 wheel 通过。隔离 PostgreSQL 18、真实 Session 行及临时文件目录下，创建意图后首传与同正文重传均 200，FileObject/Audit 仅一次；跨用户 404、改正文 409、许可拒绝 403、会话撤销 401；默认/只读模式 Content 为 404。另有单元测试验证流后许可失效阻止数据库 stage。临时数据库已删除，服务已停止，合成临时文件目录已清理。

限制：组合测试的 License 和上传 Key 为合成信任源，正式目标账户材料尚未供给；未验证真实代理限速、大文件并发/断线性能或 Server 2025。当前 FileObject 仍 STAGED，不可作为正式版本引用；Commit/Abort、Parser Job/Outbox 尚未实现。无 Migration 或新依赖；回退为不装配 Content Router，剩余暂存由已建受控恢复/TTL 清理处理。
