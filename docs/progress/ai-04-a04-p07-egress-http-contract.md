# AI-04-A04-P07：Egress Preview/Authorize/Revoke 可选 HTTP 合同

- 日期：2026-10-03
- 结果：PASS（Windows 11 合同验证）
- 依据：冻结 API-03 `EGRESS_PREVIEW_CREATE/GET/AUTHORIZE/REVOKE`、CR-AI-013、DEC-709～711

新增单一可选 Egress Router，覆盖 Preview 创建/读取、Authorize 与 Revoke 四个冻结路径。写操作要求可信 Origin、有效 Session、CSRF、持久幂等 Key；Authorize/Revoke 另要求强 `If-Match`。Authorize 的不可变 Preview 首版版本固定为 `"v0"`，正文中的 `expected_preview_fingerprint` 继续承担精确内容并发绑定；Revoke 使用 Authorization `"v0"`，成功返回 `"v1"`。

请求只接受精确字段、唯一 JSON key、规范小写 UUID/64位小写十六进制指纹和 UTC `Z` 时间。响应只投影 Provider/Model/策略、不可变来源引用、定量边界、指纹、风险、批准与状态元数据，不返回客户正文、API Key、Secret、内部路径、Provider 原始响应或 traceback。应用服务错误映射为冻结通用安全错误，不透传内部文本。

路由只通过 `create_app(ai_egress_router=...)` 显式注入；普通 `create_app()` 及当前生产组合对四条路径均保持 404。本项没有建立真实数据库组合、生产部署策略来源、Windows 平台装配或任何外发。

验证：合同测试 5 项 PASS，覆盖四路径默认关闭、201/200 安全投影、强 ETag、Session/CSRF/Origin/幂等、严格 JSON/时间/指纹/查询及错误映射；Windows 11 后端全量 2130 项运行、3 项既有环境跳过，零失败；开发 wheel SHA-256 `e83a9586fe28193ccd4ca201e5665525e6c534bad0ec4f1c9afd1973e6209bd9`。

边界：无 Schema/Migration/依赖变化；Server 2025、Debian 13、真实 PostgreSQL HTTP 链、正式信任/策略、真实外发、Gate 3/UAT/可使用程序包均未由本项验证。下一项 `AI-04-A04-P08` 进行 Windows 11 隔离 PostgreSQL 真实 HTTP 组合验证，仍不接真实 Provider。
