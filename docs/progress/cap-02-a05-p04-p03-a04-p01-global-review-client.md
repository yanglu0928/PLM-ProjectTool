# CAP-02-A05-P04-P03-A04-P01：GLOBAL Capability Review 前端安全客户端

日期：2026-10-24；结果：`FRONTEND_CLIENT_PASS / UI_NOT_CONNECTED / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P03-A04-P01`，仅接 `CR-CAP-005` GLOBAL Review 读取/决定前端传输。|
|输入基线/前置|A03-P02 Windows 11 隔离 HTTP/PG 通过；新 GLOBAL 合同已登记，不改变 Gate 2 PROJECT Review 客户端。|
|模块/实体/API|前端 Capability Client/SessionClient；`GET /api/v1/global/reviews/{id}`、`POST .../rounds/{id}:decide`。无 Schema、后端 API、权限或数据迁移变动。|
|权限/风险|当前会话的被分配且未决定 Reviewer 才可提交；服务端仍独立重证。请求超时/不明回执不自动换号重试；不能把合成批准当客户确认。|
|验收|精确 CAP-01/版本/轮次/评审人/状态/ETag/Trace 投影，错误与不明结果，定向、前端全量/typecheck/build。|

新增 `GlobalCapabilityReviewClient`，读取需由调用页给出预期 Review/Capability 版本 ID，拒绝错绑、错策略、重复 Reviewer 或矛盾决定状态。决定操作仅接受本轮受分配且尚未决定的当前用户；SessionClient 内发送 CSRF、原幂等号和严格 `{decision,comment}`。项目 Review 客户端保持原样，尚未添加页面或导航入口。

测试：定向 3 通过；前端 178 文件/1941 项通过；`typecheck` 与生产构建通过。构建保留既有大 chunk 提示。未执行 Edge/PG 页面、固定包、真人决定或正式发行信任验收；Pilot/Gate/Release 不通过。
