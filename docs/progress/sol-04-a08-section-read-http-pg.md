# SOL-04-A08：Section 当前详情可选 GET HTTP

日期：2026-10-09。结果：`SOL_04_A08_SECTION_READ_HTTP_PG_PASS`，限 Windows 11 隔离 PostgreSQL 18.6、真实 Session/ASGI 和合成 License；默认应用与当前 Windows 显式组合仍未挂 GET。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A08。
- 输入基线：冻结 API-04 `SOL_SECTION_GET`、A07 已验证内部 Owner、现有 Outline GET 安全合同。
- 前置：项目成员读策略、同项目 Section 仓储及批准指针失败关闭已通过。
- 模块/实体/API/权限：仅 Solution 可选 HTTP 与应用工厂注入；无实体/Schema/Migration/角色变化。当前 Project member 由 Owner 复验。
- 验收：200 固定投影、Trace/强 ETag/no-store、默认 404、匿名/Origin/查询串/跨项目/不存在/暂停/License 拒绝，真实 ASGI/PG 与后端回归。
- 风险：内部错误泄露或误称 Section 已审批。错误映射最小化、非空指针由 Owner 复验，当前初态指针 NULL。

## 实施与验证

新增 `create_section_read_router`，只接受 canonical 路径 UUID、当前 Session 与可信 Host/Origin，不读取正文或扩展查询。返回最小 Section 身份、状态、批准指针、创建信息与 ETag。默认 `create_app` 不注入该路由。Win11 一次性 PG18.6 真实 ASGI/Session 验证 PM/实施成员/客户角色 200、Trace/ETag/no-store，默认 404、匿名 401、坏 Origin 403、查询串 400、跨项目/不存在/暂停 404、License 403；A07 内部 Owner 与原 PROJECT Reference 夹具回归通过。

后端全量 `3386 passed, 3 skipped, 5104 subtests passed`。兼容/升级/回滚：冻结 API-04 内实现，无新 Migration、依赖或前端变化；停止注入可选 Router 可回滚，Section 历史保留。下一项 `SOL-04-A09` Windows 显式只读/写组合；LIST 独立施工。正式目标账户/License、Server2025、性能、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。
