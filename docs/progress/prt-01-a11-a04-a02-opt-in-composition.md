# PRT-01-A11-A04-A02：Prototype Workflow 可选接线

日期：2026-10-08。状态：内部组合与合同通过；生产运行入口仍默认关闭。

编码前检查：遵循 Gate 2 冻结 `/api/v1`、`CR-PRT-005` 与 A11-A03 真实 Owner。只解决 Prototype 资格在 Registry、Checklist 记录、只读预览和阶段推进的显式装配，不调整 Schema、权限或旧三阶段合同。验收为默认拒绝、显式启用方可使用真实 Owner，且同一 Owner 服务两个 Prototype item。风险是过早打开运行白名单使未经真实 HTTP/PG/文件验收的资格进入生产；故现有 `production_login` 不注入 `artifact_storage`，在 A05 证据满足前保持关闭。

实现：可选 Registry 注入必须具备物理 `verify_content`；它复用 Requirement Owner 与 Requirement 资格仓储，并组合 Prototype 根、当前版本、审核、Audit、Document 实体 Hash 与 Link 等公开证明。Checklist 写入和 Stage Transition 的 Prototype allowlist 默认关闭；显式启用才接受 `PROTOTYPE_SCOPE_DECISIONS`、`PROTOTYPE_COVERAGE`，推进仅增加 PROTOTYPE→SOLUTION，且写时仍复验。资格预览路由同样默认拒绝 Prototype item，显式启用才返回 A04-A01 的最小混合主体投影。旧 Handover/Survey/Requirement 路径不变。

验证：定向 32 项/26 子例通过，覆盖默认关闭、显式开启、混合主体 Review/Evidence Basis、两 item 同 Owner 与不合格存储启动失败；后端全量 3243 项通过、3 项条件跳过、4791 子例通过。未做真实 Windows 11/PostgreSQL/HTTP/磁盘/并发验收，因此不开放生产实例、不宣布 Gate 3 通过。

升级/回滚：无数据库迁移或新依赖，部署同步代码即可；撤显式组合保持旧行为，已有历史不可删除。下一步 A04-A03 前端接线、A05 实际验收；达到 `CR-PRT-005` 规定证据后，再显式给生产组合注入真实本地存储并复测。

TraceLink：`CR-PRT-005` → A11-A03 Owner/物理校验 → A11-A04-A01 预览投影 → A11-A04-A02 可选组合 → A04-A03/A05。
