# EVD-01-A04-P03-A08-P15：GLOBAL 当前 Evidence 客户端

日期：2026-10-01；Phase 2 Platform Core；结果：`FRONTEND_GLOBAL_CURRENT_PASS / GLOBAL_UI_OPEN`。

编码前检查：输入冻结 API-02 `EVIDENCE_GET` GLOBAL 路径、后端受权读与 P14 全局历史收据回查。前置存在；任务仅扩 Evidence 前端资格客户端的当前 GET 和测试，不改后端、Schema、权限或冻结合同。当前 Session 必须是 DeploymentAdmin、未强制改密；响应需要有效 `data/trace_id`、匹配 EvidenceId 和强 ETag。历史回查 `COMPLETED` 仍不可替代此 GET。

GLOBAL 客户端使用 GET `/api/v1/global/evidence/{evidence_id}`，保留项目原有读取语义并复用严格解析；项目身份本地拒绝。定向 6 项、前端全量 1,051 项、typecheck/build PASS，包含管理员成功读取后续已撤销状态、项目身份拒绝和 ETag 不匹配。客户端没有自动清理本地待核对记录，也不产生正式业务事实。

兼容：前端方法增量，无 API/Schema/依赖变化；无迁移。回滚停用新方法，历史 Evidence/收据不变。全局管理页面、真实浏览器、正式目标信任及 Gate 3 仍开放。
