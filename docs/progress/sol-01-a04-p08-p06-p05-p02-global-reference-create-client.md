# SOL-01-A04-P08-P06-P05-P02：GLOBAL Reference Create 私有写客户端

日期：2026-10-09。结果：`GLOBAL_CREATE_CLIENT_PASS`；只验证客户端合同，未挂页面或执行真实浏览器创建。

编码前检查：依 P05-P01、冻结 API-04 六字段与 P06-P02～P04 HTTP/Windows/PG 证据。仅改前端 Session 私有写传输与 Solution Create 客户端/测试；无后端、Schema、公开 API、依赖或权限扩大。客户端不接收或传输确认 ID、客户正文和文件路径。

实现：SessionClient 保管 CSRF、同源 Cookie、无缓存/禁止重定向、原 Key、Abort 与单请求围栏；取局部 `fetcher` 防浏览器原生 `fetch` 错误接收者。严格客户端仅允许名称与有序固定来源六字段，要求当前 DeploymentAdmin、规范 UUID、集合唯一及有界大小，响应限定 201 安全字段/Scope/状态/ETag/Location/Trace；仅对已知错误码与 HTTP 状态配对报明确拒绝。网络丢失、超时、未知错误或 201 内容异常统一不确定，不自动换 Key/重试；P05-P03 页面负责预存原 Key 和锁定恢复。

验证：定向 4 项；前端全量 107 文件/1636 项、typecheck、生产构建通过。构建仍有既有主包大于 500 kB 提示。真实 Edge/PG、页面重取当前来源与确认、正式真人核查分别待 P05-P03/P04。兼容/升级/回滚：仅新增可调用客户端，不改旧页面/传输行为，无数据升级；可移除调用并隐藏入口，历史确认/Reference/Audit/收据保留。

TraceLink：冻结 API-04 → CR-SOL-006/007/009/010 → P06-P02～P04 → P05-P01 → 本 P05-P02 → P05-P03/P04。
