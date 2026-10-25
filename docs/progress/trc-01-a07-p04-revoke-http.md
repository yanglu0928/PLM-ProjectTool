# TRC-01-A07-P04：TraceLink 可选撤销 HTTP

日期：2026-10-02；Phase 2；状态：**可选合同/真实ASGI-PG18 PASS，正式平台未挂载**。输入冻结API-01/02、CR-TRC-003、内部撤销P03、DEC-20261002-615；Gate 2原冻结提交保留。

新增精确`POST /api/v1/projects/{project_id}/trace-links/{trace_link_id}:revoke`可选Router，可信Origin/Host、当前Cookie Session与CSRF、严格强If-Match、Idempotency-Key、空请求体且不接受查询参数。Application在事务内再次验证当前License/Session/项目经理/关系归属及版本。成功只返回TraceLinkId/REVOKED、`ETag: "v1"`与`Cache-Control: no-store`；不暴露端点。默认应用与生产Windows组合均不挂载，关系Owner未实现。

验证：合同3/3覆盖默认404、200/强ETag/最小投影及Origin/Host/Session/CSRF/If-Match/Key/体/查询/错误安全投影。Windows11一次性PG18原Trace矩阵扩展真实Session的非经理404、CSRF403、缺版本428、错误体/查询400、失效License403、200及同Key重放、不同Key/载荷409；SQL确认一条REVOKED/v1、一份Audit与一份已完成收据；临时资源清理。后端1892运行/3跳过/无失败；开发wheel SHA-256 `8ba0a2cb87a0250c582d7eec113057dd28929bb863ab973149b8c4a5a80033e2`。

兼容/升级/回滚：仅可选Trace HTTP Router和应用工厂参数；无Schema/Migration/新依赖，升级无需数据操作，不传Router即关闭。正式目标账户信任、关系Owner、Trace创建/列表/通用图、Windows Server2025/Debian、性能/UAT/Gate及可用程序包仍待；本项不声称正式发行通过。
