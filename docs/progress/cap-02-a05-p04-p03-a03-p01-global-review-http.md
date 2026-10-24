# CAP-02-A05-P04-P03-A03-P01：GLOBAL Capability Review 默认关闭 HTTP

日期：2026-10-24；状态：`HTTP_CONTRACT_PASS / WINDOWS_NOT_MOUNTED / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P03-A03-P01`，仅新增 `CR-CAP-005` 的 GET/DECIDE 传输与应用工厂可选插槽。|
|基线/前置|原 Gate 2 API-02 PROJECT 路径不变；GLOBAL 内部读取/决定单元与 Windows 11 隔离 PG 合成原子链已通过。|
|依赖/数据|无 ORM、Migration、第三方依赖、外部网络或客户数据变化；默认 `create_app()` 不注入 Router 时均 404。|
|安全|GET 可信 Host/当前 Session/License/精确 CAP-01 Scope；POST 可信 Origin、Session/CSRF、幂等号、严格两字段 JSON/UTF-8、当前受分配 Reviewer；返回 no-store/Trace/强 ETag，不返回正文/Secret。|
|验收|独立合同正负例与后端全量回归；Windows 启动、真实 HTTP/PG 与浏览器另片验。|

新增 `GET /api/v1/global/reviews/{review_id}` 返回唯一首轮的 Review/Capability 绑定、Reviewer/决定元数据和当前双 ETag；`POST /api/v1/global/reviews/{review_id}/rounds/{round_id}:decide` 仅接受 `{decision,comment}`，`RETURN` 必须有实质意见。命令仍由 Review/Capability 内部服务完成原子决定，Router 不直写数据库。公开错误码采用原 API 语义；错 Scope/未知 Subject 不回落至 PROJECT。当前仅 opt-in 应用工厂插槽，Windows 生产组合尚未注入。

验证：合同测试 4 项、15 子例，默认 404、GET 200、决定 200、错误/安全矩阵通过；后端全量 4087 通过/3 跳过/6129 子例，2 个现有警告。没有本片真实 Windows HTTP/PG、Edge 页面、真人决定或正式信任/安装证据；Gate/Pilot/Release 均未通过。
