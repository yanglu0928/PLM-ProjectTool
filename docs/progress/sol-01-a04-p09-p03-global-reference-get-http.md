# SOL-01-A04-P09-P03：GLOBAL Reference GET HTTP

日期：2026-10-09。范围：兑现已冻结 `SOL_REFERENCE_GET` 的 GLOBAL 详情路径和 Create201 的 `Location`；不实施 List/游标、前端、Schema 或新授权。

编码前检查：沿用 P09-P01 的冻结合同/Scope 对账及 P09-P02 的独立只读 Owner/Repository；当前 DeploymentAdmin Session、License、GLOBAL 行和固定来源均由 Owner 证明。HTTP 不复用 PROJECT 授权，Windows 仅显式 read/write 模式注入；未注入时 404。

结果：`GET /api/v1/global/reference-solutions/{reference_solution_id}` 返回当前 GLOBAL 版本、安全的固定 Document/Evidence 身份、ETag、`no-store` 与 TraceId；不返回脱敏确认 ID、客户正文、Secret 或“确认当前有效”断言。确认撤回后仅保留历史 Reference 可读，不改变当前来源再利用资格。Session/Origin/License/Admin/Identity/Query 失败关闭。

验证：合同定向测试及 Windows 11 隔离 PostgreSQL 18.6/ASGI/真实 Session 的 Create→Location→GET 与撤回后 GET、拒绝路径通过；全量后端结果见 STATUS。脚本使用合成资料和确认，不是客户真人业务确认。

兼容/迁移/回滚：冻结 API-04 GLOBAL GET 路径增量落地，无 Breaking Change、Schema/依赖/数据迁移；关闭可选路由可恢复 404，既有 Reference/确认/Audit 不删除。正式 License/账户、Server 2025、20 并发、Gate 3/UAT/发行尚未验证；Debian 13 按用户指令跳过。

TraceLink：API-04 → P09-P01 → P09-P02 → P09-P03 → P09-P04 List 专用游标 → P09-P05 前端。
