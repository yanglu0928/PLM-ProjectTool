# DOC-03-A04-A04-P04-P04-A01：可选 Commit/Abort HTTP 契约

日期：2026-09-26；版本：`0.1.0.dev0`；状态：可选 HTTP 契约 PASS，Windows 正式组合尚未挂载。

按冻结 API-02 和 `DEC-20260926-118`，新增 GLOBAL/PROJECT 上传 Commit 与 Abort 的可选 Router，默认应用保持 404。两操作均要求可信 Origin、当前 Session/CSRF、Idempotency-Key、空请求体，并由内部服务在事务内重查创建者与 License；Commit 对既有 Document 使用强 If-Match 父版本，返回不可变 DocumentVersion 与 Parse Job 引用；Abort 返回 ABORTED 与 cleanup_pending，不声称正文已删除。错误信息仅按公共错误码投影，正文、绝对路径和内部 traceback 不外泄。

Windows 11/Python 3.13 后端 507 项无失败（2 项符号链接权限跳过）；4 项新增 HTTP 契约测试覆盖默认关闭、GLOBAL/PROJECT、版本条件、Origin/Session/CSRF/幂等、非空请求、越权、许可和安全错误映射；开发 wheel PASS。无 Migration、新依赖或冻结路径变化。当前仅合成服务 HTTP 测试，真实 Session/License/Project Role 与 PostgreSQL/临时文件的端到端组合留给 P04-P04-A02；P03-P02 物理清理仍受停写证明缺失阻塞，见对应前置核查。Server 2025、正式发行信任源与 Gate 3 未通过。
