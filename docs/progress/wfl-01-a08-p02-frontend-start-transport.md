# WFL-01-A08-P02：Workflow START 前端安全传输桥接

2026-10-02 / Phase 2 / `FRONTEND_TRANSPORT_PASS`。编码前检查：冻结 `WORKFLOW_START` POST、P01 前端只读视图、P02/P03/P04 后端受权首启与 Windows 显式组合已具备。仅在 SessionClient 增加私有 CSRF/原始 v0 强 ETag/幂等 Key 的空体 POST，不添加页面或业务结果解析，不扩大 Scope/API/Schema/依赖。

实现：客户端先核规范非零 ProjectId、精确 `"v0"`、16–128 可打印 ASCII Key 和当前可写 Session；同源、无缓存、禁止重定向、单请求空体调用固定路径。401 清当前内存身份/CSRF，超时或网络异常不自动重试；原 Key/版本由调用方保留用于结果核查。CSRF 仅在私有 SessionClient 中，不暴露于序列化对象。

验证：新增4项会话桥接测试覆盖固定请求、非法 ID/版本/Key 本地拒绝、只读会话拒绝/401 清理、超时不并发/不自动重试。前端全量59文件1175项、typecheck及production build通过。未做真实浏览器、页面/回执或正式信任验收；现有非发行包尚未重建。

兼容/升级/回滚：未接页面，当前 UI 不变；无后端/数据库迁移。可撤未调用方法。下一项 `WFL-01-A08-P03` 解析并约束首次启动回执，明确与当前 Workflow GET 分离。A07 Owner/Gate、正式信任、Server2025/Debian、UAT/Gate3仍开放。
