# DOC-03-A04-A04-P04-P01：Parse Job/Outbox 同事务入队 Port

日期：2026-09-26；版本：`0.1.0.dev0`；状态：内部前置子项 PASS，上传 Commit/Abort 未完成。

依据冻结 DM-03、ADR-007、`CR-DOC-006` 和 `DEC-20260926-116`，jobs 模块新增受限 `ParseJobQueue` Application Port。调用方提供已有短事务，入队接口只保存上传/文档版本 ID、Scope/Project、原 actor 与 trace 引用；在该事务内同时登记 `DOCUMENT_PARSE` Job 和 `DOCUMENT_VERSION_COMMITTED` Outbox，不自行提交、不访问 Document 内部表、不携带文件正文、Token、Secret 或 Prompt。相同 UploadId/版本再次调用返回原 Job/Event；同 UploadId 变更版本或 actor 拒绝。重试请求的新 trace 不改写原始入队 trace。

Windows 11/Python 3.13 后端 500 项无失败（2 项符号链接权限跳过）；隔离 PostgreSQL 18 已验证调用方回滚、首次入队、同键重放/冲突、最小引用以及 GLOBAL/PROJECT Scope；开发 wheel 构建 PASS。无新迁移、公开 API 或依赖；目标库须已有 `0026`。

接下来必须在 Document 上传 Commit 中同事务执行 FileObject AVAILABLE、不可变 DocumentVersion、UploadIntent COMMITTED、此 Port、Audit 与幂等收据；Abort、正式 HTTP、Parser Worker 和发行环境仍待。不能将本 Port 的验证外推为完整上传已可用。
