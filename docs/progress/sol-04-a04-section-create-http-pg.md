# SOL-04-A04：SolutionSection CREATE 可选 HTTP

日期：2026-10-09。结果：`SOL_04_A04_SECTION_CREATE_HTTP_PG_PASS`，限 Windows 11 一次性 PostgreSQL 18.6、真实 Session/ASGI 与合成 License；默认应用和当前 Windows 生产组合仍为 404。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A04。
- 输入基线：冻结 API-04 `SOL_SECTION_CREATE`、CR-SOL-012、已验证 SOL-04-A03 内部 Owner、0148 Guard/首次结果。
- 前置：Section 身份/权限/幂等/Audit 同事务及 PostgreSQL 负例已通过。
- 模块/实体/API/权限：仅 Solution 可选 HTTP 与应用工厂注入；不改实体、Schema 或内部 Owner。`POST /api/v1/projects/{project_id}/solution-sections`，ProjectManager/ImplementationMember。
- 验收：严格可信 Origin、Session/CSRF、Idempotency-Key、精确 JSON body；201 初态、Trace/ETag/Location/no-store；同键重放、冲突、跨项目/暂停成员/License 拒绝，默认路由 404，后端回归。
- 风险：可选路由误挂载或错误码泄露。依赖显式注入；不可见资源统一 404，未知内部错误统一 503 类别。

## 实施与验证

新增 `create_section_create_router`，只接受 `solution_outline_id` 与 `section_key`；参数 UUID 严格校验，业务 key 由 Owner 规范化。201 返回不可变初态快照和规范 Location。`create_app` 默认不注入该 Router。使用隔离 PostgreSQL 18.6 的真实 Session/ASGI/PG 夹具验证 PM、实施成员、重放、异载荷/重复 key、跨项目、无效父目录、CSRF/Origin/Session、暂停成员、License 和默认 404；数据库最终恰有两条 Section 及两条创建 Audit。原 PROJECT Reference 夹具也回归通过。首轮测试把无效 Outline 误期望为 409；按资源隐藏合同更正为 404 后重跑通过。

后端全量 `3386 passed, 3 skipped, 5100 subtests passed`。兼容/升级/回滚：冻结 `/api/v1` 内实现，无 Migration、依赖、前端或默认暴露变化；停止注入可选 Router 即关闭新入口，已创建历史不可删除。Windows 显式平台组合、只读接口/前端、正式目标账户/License、Server2025、性能、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。下一项 `SOL-04-A05` Windows 显式平台组合。
