# DOC-03-A04-A03-P04-P02-A01 可选上传创建 HTTP

日期：2026-09-26。依据冻结 API-02 上传协议、DEC-20260926-110 与此前内部 UploadIntent/请求级授权实现。

结果：固定 `/api/v1/global/document-uploads` 与 `/api/v1/projects/{project_id}/document-uploads` POST，仅显式注入 Router 时存在；默认应用保持 404。请求字段 `purpose`、`category`、`subtype`、`document_purpose`、`title`、`display_name`、`size_hint_bytes`、`mime_hint`、`document_id`、`supersedes_version_id` 映射至内部命令。服务端从路径决定 Scope/Project，从 Session 决定 actor；可信 Origin、Cookie/CSRF、Idempotency-Key、License Guard 均为前置。201 响应返回 upload_id、短时 upload_token、UTC expires_at，带 `Cache-Control: no-store`，不暴露 Storage Locator。

可选 `supersedes_version_id` 在既有 Document 创建与重放时核对当前 latest_version_ref；提供时进入幂等指纹，未提供时旧指纹保持不变。该字段不是 Commit 并发保护，Commit 仍需父 Document If-Match。无 Schema 变化或迁移。

验证：Windows 11/Python 3.13 后端 487 项无失败（2 项符号链接权限跳过）；可选路由契约验证默认关闭、PROJECT/GLOBAL 映射、Origin/Session/CSRF/Key/License 拒绝、错误安全投影；PostgreSQL 18 隔离合成库验证既有内部创建/重放和父版本不匹配拒绝；开发 wheel 构建通过。测试库删除，数据库服务已停止。

限制：HTTP 契约测试使用合成 Session/Guard/Service；未验证真实 Session、License、Project Role 与上传 Token 密钥来源的联合装配。默认和当前 Windows 生产组合均不挂载路由，不能称为用户可用上传。下一项建立独立 Token 密钥的目标账户安全来源及恢复，再做显式平台组合验证；Content HTTP/Commit/Abort/Parser Job 尚未实现。
