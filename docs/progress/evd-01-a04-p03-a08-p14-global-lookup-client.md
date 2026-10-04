# EVD-01-A04-P03-A08-P14：全局管理员资格操作回查客户端

日期：2026-10-01；Phase 2 Platform Core；结果：`FRONTEND_GLOBAL_CLIENT_PASS / GLOBAL_UI_OPEN`。

编码前检查：输入 CR-EVD-004 双 Scope 增量、P12 项目客户端、P13 项目页面；仅扩前端 Session 传输与 Evidence 客户端/测试，不改后端、Schema、角色或冻结 API。GLOBAL 路径只允许当前 DeploymentAdmin、无强制改密且原 Key 合规；不借项目成员身份旁路。使用原操作号 JSON Body、CSRF、同源 no-store；复用严格最小响应验证，`COMPLETED` 不是当前状态证明。

新增 2 项 GLOBAL 正反例，定向 7 项 PASS、前端全量 1,049 项、typecheck/build PASS。管理员只走 `/api/v1/global/evidence/{evidence_id}:lookup-eligibility-operation`；项目身份不能调用，全局管理员无项目角色不能借项目路径。当前客户端未被全局 UI 调用，不能声称管理员已经可在页面恢复。

兼容：独立前端方法，无 API/Schema/依赖变化；无迁移。回滚不调用新方法，既有服务端收据保留。后续全局 UI、受权当前全局 Evidence GET、真实浏览器、正式目标信任源和 Gate3仍开放。
