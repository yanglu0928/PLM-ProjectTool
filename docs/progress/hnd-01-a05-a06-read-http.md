# HND-01-A05-A06：Handover Analysis 五个读取 HTTP

日期：2026-10-05。结论：`HND_01_A05_A06_READ_HTTP_PASS`。下一项：`HND-01-A05-A07` Windows 生产组合与真实 HTTP/PostgreSQL。

## 实施结果

新增统一可选读取 Router，接通 Analysis LIST/GET、Version LIST/GET 与 Item LIST；默认应用五路继续 404。GET 只要求可信 Host 和当前 Session，不要求 CSRF；License、当前 User、Project 成员资格、项目/资源归属仍由 A02 Owner 在同一读取事务重验。

新增 Analysis、Version、Item 三类独立 HMAC-SHA256 cursor，分别绑定完整父级链、Session、Project、页长及服务端位置。列表验证页形状、资源归属和最后位置；详情拒绝 query。DTO 只投影固定引用与有界 JSON 输入规格，不跨 Owner 展开路径、正文或 AI 内容。

## 客观验证

- 新增 cursor/HTTP 7 项，与既有 A02 Owner 7 项合计定向 14 项通过；覆盖默认五路 404、五种投影、三类续页、错上下文、Host/Session、严格 query/UUID、安全错误。
- Windows 11 / PostgreSQL 18.6 复跑 A02 真实数据链：四角色当前成员、同时间 Analysis 完整 keyset、Version 倒序、Item 正序、安全固定引用、跨项目/撤权/License 拒绝、归档可读、业务零写与 Alembic drift=0 通过。
- Windows 11 / Python 3.13 后端全量 2704 项通过，3 项环境条件跳过。
- 开发 wheel 包含 Handover read/cursor 模块，SHA-256 `ab45d75740810d07a00057f9ae58e769ed5ba36071d3bab8613bced0f9704477`。

## 兼容、回滚与未关闭项

无 Schema/Migration、依赖、配置、Secret、外部网络或客户数据外发。当前只提供可选 Router；停止注入即恢复 404，数据不变。

A07 尚需为 Windows 服务账户建立三把独立 Vault key、失败关闭组合并完成真实 HTTP/PG；Server 2025、Debian 13、Gate 3 与正式发行仍按总状态跟踪。
