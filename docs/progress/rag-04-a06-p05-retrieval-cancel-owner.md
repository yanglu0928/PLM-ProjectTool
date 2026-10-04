# RAG-04-A06-P05：Retrieval 双路径同 Owner 取消

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_04_A06_P05_RETRIEVAL_CANCEL_OWNER_PASS`

## Changed

新增唯一 Retrieval 取消 Owner 和 PostgreSQL Repository，并由两个冻结入口复用：

- `POST /api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}:cancel`
- 通用 `POST /api/v1/projects/{project_id}/jobs/{job_id}:cancel` 的 `('rag','RAG_RETRIEVAL')` Owner 注册项

每次取消都重验 License、Session/CSRF、当前 Project 成员与对象级权限；创建者或 ProjectManager 可取消，其他主体统一隐藏。两个入口各有版本化幂等 Scope，但进入同一锁定、状态变更和 Audit 核心，不允许出现两套取消状态机。

PENDING Job 在同一事务先进入 `CANCEL_REQUESTED` 再同步关闭 Job/Run，形成 Schema0090 固定的 Job v2、Run v1、零 Lease/Attempt/结果；RUNNING Job 只先进入 Job v2 `CANCEL_REQUESTED`，当前 Worker 通过专属 Reconciler 释放 Lease、关闭 Attempt/Job/Run并形成 Job v3。Worker 未响应且 Lease 到期时，过期 Reconciler 以 `EXPIRED` 形态执行相同原子终结。所有写入在提交前执行 Schema0090 deferred constraints，并记录用户请求和 SYSTEM 终结 Audit。

冻结别名 Router 默认关闭，严格要求 Origin、Session、CSRF、幂等键、强 If-Match 和仅含 `reason` 的 JSON；只返回 Run/Job引用、状态、changed、Run ETag和安全状态 URL。通用 Job Router 本项不重复实现，只验证显式 Owner registry 分派；生产组合留 P06。

## Compatibility / Upgrade / Rollback

- 复用 Schema0090，无新 Migration、依赖、Provider I/O 或数据外发；冻结两个 URL 与协作取消语义保持。
- 首次取消响应由 Idempotency Receipt 指向不可变 Audit；RUNNING 请求即使随后进入 CANCELLED，精确回放仍重建首次 `CANCEL_REQUESTED`/Job v2，而不伪装当前响应。
- 默认应用仍不挂取消 Router，生产 registry 也尚未装配；可撤 Owner/Router/Reconciler关闭新取消，已记录的取消历史不可降级，必须保留并向前修复。

## Tests

- 应用/HTTP新增 9 项 PASS；RAG单元141项、相关取消/HTTP 18项PASS。
- Windows 11/PostgreSQL 18.6：真实别名HTTP PENDING直接取消与重放；真实通用Job registry RUNNING请求、当前Worker终结与回放；真实最短租约自然到期后的EXPIRED终结，全部原子PASS，三条链零Candidate。
- 后端全量2522项PASS，3项既有环境条件跳过。
- 开发wheel隔离导入：RAG141项、Create/Get/Result/Context+Cancel合同8项、Migration Contract4项PASS。wheel SHA-256：`5179db1356d9a8e70779457355e2d5dbc6eac8b196706f0bb650dc99578486eb`。

## Deviations / Evidence Corrections

首次过期夹具使用1秒Lease，被产品3秒下限按设计拒绝；第二次尝试直接改Job租约时间，触发通用Job资源版本自增，使其偏离Schema0090固定Job v2并被Reconciler按设计拒绝。这两轮均不计验收证据。最终使用合法3秒最短Lease自然到期，在全新隔离库完整复跑通过；产品代码未为夹具放宽。

## Result / Known Issues / Next

结果：`PASS`。双取消路径已共享一个写 Owner，PENDING/RUNNING/过期三种合法形态和首次响应回放均有真实数据库证据。

已知问题：生产 API 与第四 Worker 角色尚未装配新 Router/Owner/Reconciler；专用查询密钥来源、公平有界 Retrieval 循环、前端、真实浏览器闭环、正式质量/性能、Windows Server 2025、Gate 3、UAT和发行包仍待；Debian 13 按用户指令跳过。

下一项：`RAG-04-A06-P06`，完成 Windows 生产 API与既有第四 Worker角色组合，加入专用查询内容密钥来源和公平有界 Retrieval 循环。
