# SOL-06-A11-P04：结构化专项列表 HTTP 合同

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。TraceLink：冻结 `SOL_SPEC_LIST` → A11-P02 内部受权读取 → A11-P03 专用游标 → 本项。当前 Phase 2。
- 编码前检查：内部列表、独立签名游标和冻结路径已就绪。本项仅新增默认关闭的可选 GET Router 与 `create_app` 注入槽；不改 Schema、项目角色、写接口、License 权益或依赖。Windows 平台组合留 P05。
- Changed：新增 `GET /api/v1/projects/{project_id}/structured-solution-specs`，只接受唯一的 `page_size`/`cursor`，强制受信 Host、有效 Session、专用游标和项目成员 Service。返回最小不可变摘要、签名 `next_cursor`、`has_more` 与统一 `trace_id`，`Cache-Control: no-store`；不返回 payload/ref 正文。默认应用 404，只读组合中的同路径 POST 也隐藏为 404；错误不泄露内部异常。
- 验证：列表合同、游标及内部读取联合定向 11 项/25 子例通过，覆盖默认关闭、POST 隐藏、两页、摘要投影、游标不可读位置、跨会话/项目/查询/篡改、Session/Host、Owner 错误映射和损坏输出 503。后端全量 `3644 passed, 3 skipped, 5735 subtests passed`。开发 wheel 1398 条目且包含新路由，SHA-256 `e75942147e4ddf39db0a0a2ea48f24f761b4ccced84a67ce34093f342a0685bc`。
- 兼容性/升级/回滚：无 Migration、外部依赖、现有 GET/CREATE 行为或旧数据变化；不注入可选 Router 即恢复原默认 404。Windows Server 2025/Debian 13 未实测。
- 限制：Windows 组合尚未供给专项列表独立密钥，也未跑真实 Session/License/PG HTTP；前端/Edge 未实现。本合同摘要不证明来源现时有效或 Review 已批准。专项修订/验证/送审、OutputArtifact、章节六维、Gate 3/Pilot/正式 Release 仍待。
- Next：`SOL-06-A11-P05` 在 Windows 显式读/写模式供给独立列表游标密钥并装配 Router，以可弃 PG18.6 验证真实两页、成员、跨项目/Session/License 和默认关闭。
