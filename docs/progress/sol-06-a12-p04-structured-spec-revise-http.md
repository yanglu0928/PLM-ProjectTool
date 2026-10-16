# SOL-06-A12-P04：结构化专项修订 HTTP 合同

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVISION_HTTP_CONTRACT_PASS`；仅表示默认关闭的 ASGI 合同通过，尚未接入 Windows 平台组合或真实数据库 HTTP 链。TraceLink：冻结 `SOL_SPEC_REVISE` → A12-P01～P03 → 本项。
- 编码前检查：路径保持 `POST /api/v1/projects/{project_id}/structured-solution-specs/{spec_id}:revise`，正文与 CREATE 相同，仅含 `spec_type`、类型化 payload、Requirement/Section/Evidence/Artifact refs；不加入 If-Match、series、版本号或前驱字段，不改 `/api/v1` 冻结语义。
- 安全边界：先执行受信 Origin、Session/CSRF 和 Idempotency-Key 校验；拒绝查询参数、重复 JSON key、NaN、未知/缺失字段、非 UUID 路径和当前尚无 Owner 的 Artifact 引用。未经显式注入 Router 的默认应用继续返回 404。
- 响应：成功返回 201、`Cache-Control: no-store`、新固定版本 `Location`、统一 TraceId 和 CREATE 同形完整 DRAFT 投影；额外严格要求 `version_no >= 2` 且 `supersedes_version_ref` 精确等于路径版本。返回项目、前驱或版本号漂移均失败关闭，不生成 ETag。
- 错误：无权限/跨项目隐藏为 404；陈旧前驱映射 `CONFLICT_VERSION`，不允许状态映射 `CONFLICT_STATE`，项目归档、License、幂等冲突、输入和系统/来源错误沿冻结通用合同返回；不泄漏异常栈。
- 验证：相关合同/Service 定向 `13 passed / 42 subtests`；完整后端 `3660 passed / 3 skipped / 5783 subtests`；开发 wheel 1401 条目，SHA-256 `93fd429c82f0bd9805c4a2501846d3f2b3cbcf839e67568dfcdd4320ee66812e`，包含新 Router。
- 兼容性/升级：无 Migration、冻结请求字段、License 权益、角色或依赖变化；`create_app` 只增加默认为空的可选 Router 注入点，既有部署行为不变，无数据升级。
- 回滚：移除可选 Router 文件和注入点即可；已写版本/Audit/收据不受影响。本项没有客户数据外发或生产写入。
- 已知边界：Windows 11 组合、真实 HTTP/PG、前端和 Edge 尚未完成；正式服务账户信任、OutputArtifact、专项验证/送审、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 与正式发行仍未通过。
- Next：`SOL-06-A12-P05` 在 Windows 显式读写模式装配 revise Router，并以可弃 PostgreSQL 18.6 验证真实 HTTP、安全拒绝、重放和事务证据。
