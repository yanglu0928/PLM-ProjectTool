# SOL-03-A04-P03-P03-P06-A03-P03：GLOBAL 候选管理员发布 HTTP

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P06_A03_P03_PUBLICATION_HTTP_PG_PASS`；可选路由及真实 ASGI/PG 验收通过，Windows 生产组合未挂载，项目成员候选仍不可见。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本任务。输入 Gate 2 API-01/04、CR-SOL-018、DEC-1148～1150、0158 与已验内部管理员 Owner。
- 单一问题：以独立、默认关闭的 HTTP 命令让 DeploymentAdmin 显式发布/撤回当前 GLOBAL ReferenceVersion 的非敏感候选标签。
- 模块/实体/API/权限：仅 Solution API 和应用组装可选注入点；发布事件仍由内部 Owner 写。新路径见 `docs/api-contract/solution-global-reference-publication-v1-increment.md`，不修改旧 `/api/v1` 路径、角色或依赖。
- 验收：默认 404、可信 Origin、Session/CSRF、严格 JSON/幂等键、管理员/License 与版本/事件号拒绝、最小响应、真实 PG 事件/Audit/重放和后端回归。
- 风险：默认入口误开、管理员响应泄漏原始名称/来源、HTTP 校验替代 Owner 权限、过期页面误发。通过可选挂载、白名单投影、Owner 双重认证/现时重证和预期事件号控制。

## 实施与验证

新增 `POST /api/v1/global/reference-solutions/{id}:set-candidate-publication` 的可选 Router；请求固定五字段、禁止查询参数和重复/额外 JSON key，要求可信 Origin、Session/CSRF、Idempotency-Key；只调用内部 Owner，不直接访问表。成功 200、`data`/`trace_id`、no-store，`data` 仅白名单事件身份/固定版本/事件号/状态/审定标签/原因/UTC 时间；项目端不得复用此管理员投影。`create_app` 参数默认 `None`，未注入时路径为 404。

合同定向 3 项/13 子例通过；Owner 补充 License 拒绝后定向合计 10 项/17 子例通过。Windows 11 隔离 PostgreSQL 18.6 真实 ASGI/Owner/Session 数据/Document/Evidence/确认/Audit/收据验证脚本退出 0：默认 404、恶意 Origin 403、无 Session 401、真实普通用户 404、额外字段 400、发布与撤回 200、原键原事件重放、过期事件号 409、事件/Audit 各两条、响应无原始方案名/来源指纹。HTTP 前置 `Sessions.validate` 为合成适配器，但内部 Owner 再以数据库中真实 Session/CSRF/DeploymentAdmin 证明；不能据此宣称 Windows 生产 Session 工厂已装配。后端全量 3482 通过、3 跳过、5350 子例通过。已有 Alembic 表达式/计算默认值比较警告保留，`command.check` 无新升级操作。

兼容/回滚：无 Schema/Migration/旧 API/依赖变化；仅移除可选 Router 注入即可关闭新 HTTP，既有事件、收据与 Audit 保留。下一项 `SOL-03-A04-P03-P03-P06-A03-P04` 在 Windows 显式写模式组合中按受控信任源挂载，并验证缺依赖失败关闭；其后再做项目最小 GLOBAL 候选读取及浏览器。正式服务账户/Server2025、20 并发与 Gate3/发行独立验收；Debian13 实机按用户指令跳过。

TraceLink：Gate 2 API-04 → CR-SOL-018 → DEC-1150 → 0158/内部 Owner → 本 HTTP/PG → Windows 组合 → 项目候选只读。
