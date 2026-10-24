# Capability GLOBAL Review V1 增量合同草案

日期：2026-10-24；状态：`CR-CAP-005 APPROVED_FOR_IMPLEMENTATION / HTTP_NOT_IMPLEMENTED`。原 Gate 2 API-02/API-04 冻结提交 `64cdf09` 保持不变。

|Operation|方法与路径|受权|成功|边界|
|---|---|---|---|---|
|`GLOBAL_REVIEW_GET`|GET `/api/v1/global/reviews/{review_id}`|当前 DeploymentAdmin + License + 精确 `CAP-01` GLOBAL Scope|200 固定首轮/决定投影、强 ETag、Trace/no-store|只暴露元数据，不读文档正文；未知 Subject 404|
|`GLOBAL_REVIEW_DECIDE`|POST `/api/v1/global/reviews/{review_id}/rounds/{round_id}:decide`|当前 assigned DeploymentAdmin + License + Origin/CSRF|200 决定与汇总状态、强 ETag、Trace/no-store|精确 `{decision,comment}`、幂等号；`RETURN` 必须有实质意见；同事务消费 Capability 终态|

本表为后续实现的增量合同，不代表路由已注册或可用。字段/状态/错误的严格 JSON Schema 与独立合同测试在 A02/A03 定稿；若与此草案不兼容，先修订 CR 和迁移/回滚，再编码。不得把项目 Review 路径重命名或把合成提交当真实批准。
