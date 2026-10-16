# SOL-03-A04-P03-P03-P05-A01：OutlineVersion CREATE 可选 HTTP 合同

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P05_A01_OUTLINE_VERSION_HTTP_CONTRACT_PASS`；仅可选路由合同，真实 ASGI/PG 和 Windows 组合另项。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / 本任务。输入基线：Gate2 冻结 API-04 路径/角色、CR-SOL-016/017、DEC-1141/1142、已验双 Scope Owner/0156 Guard。
- 前置：内部 Owner 及 PROJECT/GLOBAL 固定 Requirement/Reference 写链已在 Win11 隔离 PG 验证。可选路由默认不挂载；正式 Windows 信任源未供给不影响合同开发。
- 模块/实体/API/权限：Solution API、`create_app` 可选注入点；`POST /api/v1/projects/{project_id}/solution-outlines/{outline_id}/versions`；项目 PM/IM 权限继续由 Owner 现时校验，不在路由自建权限。
- 验收：Origin/Session/CSRF/Idempotency-Key、严格字段/路径/JSON、201 DRAFT 首响/Location/Trace、错误安全投影、默认 404 与后端全量。风险：合同测试使用假 Owner，不能宣称真实 HTTP/PG PASS。

## 实施与验证

新增可选 POST Router，固定路径和 DEC-1142 的有序身份/声明 DTO；严格拒绝未知字段、重复键、NaN、非法 UUID、非标准 JSON 和超 512 KiB 请求。可信 Origin、Session/CSRF、幂等 Key 先于业务调用校验；Owner 服务在工作线程运行，角色/License/来源证明仍在同事务执行。201 响应投影不可变首次 DRAFT 身份、摘要、声明、三类计数、前驱、创建信息和 Location/Trace，`Cache-Control: no-store`；不暴露正文、文件定位或 GLOBAL 管理员会话，也不制造未定义的版本 ETag。`create_app` 仅接受显式 Router，默认 404。

合同定向 4 项/17 子例通过，覆盖首响、默认关闭、Origin/CSRF/Key/路径/字段、重复 JSON、错误映射和跨项目结果失败关闭；后端全量结果见状态与版本说明。真实 ASGI/PG/Windows 装配、前端/UI 尚未验证。无 Migration/Schema/依赖变化；未接线时可撤新增 Router 和工厂注入点，既有首响历史不删。下一项 `P05-A02` 真实 Session/ASGI/PG 验收；Gate3 仍 BLOCKED。

TraceLink：Gate2 API-04 → CR-SOL-016/017 → DEC-1141/1142 → P04 Owner/双 Scope → 本可选 HTTP → ASGI/Windows/UI。

最终后端全量：3455 通过、3 跳过、5277 子例通过；本项未运行真实 HTTP/PG 组合。
