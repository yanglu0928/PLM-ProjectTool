# SOL-06-A15-P02：结构化专项终态 Review Windows 组合

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVIEW_TERMINAL_WINDOWS_PASS`；证明冻结通用 Review 决定可由已分配 Reviewer 推进 SOL-06 批准或退回，不表示任何真实客户专项已批准。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A15-P02`|
|输入基线|冻结 `REVIEW_DECIDE`、A15-P01、A14-P04 SOL-06 Owner、A14-P07/P09 送审链|
|前置状态|SOL-06 可形成真实 IN_REVIEW Review/Round；Owner 内部终态生命周期已验证，生产通用注册表缺 SOL-06 是唯一当前问题|
|涉及模块|Windows Solution/Project Review 组合与对应单元/真实 HTTP-PG 验收；无前端或读取 API|
|涉及 API / Schema / 权限|严格复用冻结通用 `:decide`、assigned reviewer、现有角色/License/Review Schema；无 Migration 或合同变化|
|验收标准|默认关闭；SOL-06 注册；APPROVE 当前事实重证；RETURN 实质意见；Session/CSRF/License/项目/assigned reviewer/隔离；同 Key 重放/漂移；Review/SOL-06/Audit/收据同事务|
|风险|复制两套 Owner 依赖导致送审与终态规则漂移；批准时沿用历史验证；终态部分提交；其他 Subject 注册回归|

## 实施结果

- 抽取 `create_windows_structured_spec_review_subject`，由送审组合和通用终态组合共享同一个正式 Owner 构造：Document/Evidence 固定来源、Requirement/SOL-06 Trace、当前事实 evaluator、Reviewer 资格、状态 Repository 与 Audit 均一致。
- `create_windows_project_review_router` 仅在完整 Document 下载/解析依赖同时存在时注册 `SOL-06`；缺任一依赖仍启动失败关闭。无来源依赖的既有四类 Owner 行为不变，完整组合现注册 HND-02、SRV-02、REQ-03、PRT-03、SRV-05、SOL-06。
- 没有新增 SOL-06 专用批准路径。实际 Reviewer 继续使用冻结通用 `REVIEW_DECIDE`；Owner 在 APPROVE 的同一事务重新证明最新 IN_REVIEW 固定版本、设计就绪、来源、Trace 和 Reviewer 当前资格，RETURN 只拒绝/退回绑定版本而不伪造批准。

## 验证证据

- 组合/生产入口/通用 Review 合同定向：`60 passed, 82 subtests passed`。
- Windows 11 / PostgreSQL 18.6 两套全新可弃数据库真实 HTTP 链退出0：
  - APPROVE：默认路由、跨项目、非 assigned reviewer、License 均拒绝；Evidence 临时失效时同 Key 404 且无 Decision，恢复后同 Key 200；精确重放 200、载荷漂移 409；新版本唯一 APPROVED，旧批准版 SUPERSEDED。
  - RETURN：空白 comment 422；实质 comment 200；精确重放 200、漂移 409；目标版本 RETURNED，旧批准版仍唯一 APPROVED。
- 两条终态均逐库确认唯一 Decision、唯一 SOL-06 终态结果、绑定 `V1_REVIEW_DECIDE` 收据，以及同一成功 Trace 下 `REVIEW_DECISION_RECORDED` 与 `STRUCTURED_SPEC_VERSION_*` 两条 Audit；Review、Round、专项状态全部一致。
- 后端全量：`3748 passed, 3 skipped, 5854 subtests passed`。
- Python 3.13 开发 wheel 共 1415 项，包含共享 Owner 与 Windows 通用组合，SHA-256 `4bf3510734becb1a35d64376ce99925eeaa57d24f9286a812ecf62a64f85ebe4`。该 wheel 不是 Pilot 或正式发行包。

## 偏差、兼容与回滚

- 初次 wheel 命令从错误工作目录引用虚拟环境路径失败；随后发现仓库 `build/` 目录遮蔽同名模块且测试虚拟环境不含 pip。最终使用虚拟环境中已固定的 setuptools `build_meta` 直接构建并核对内容/Hash；失败尝试未生成验收证据，也未改变依赖。
- 无 Migration、冻结 API/角色/License/依赖或旧数据变化；后端同版升级即可。可从通用注册表移除 SOL-06 停止新终态写入，但既有 Review、Decision、专项状态、Audit 和收据必须保留。
- `REVIEW_GET/LIST`、前端 Reviewer 页面和 Edge 决定链仍未实现；当前后端能力不等于可发现、可操作的最终 UI，也不关闭 Gate 3、Pilot、正式信任、性能或多平台发行要求。

Next：`SOL-06-A15-P03` 实现 SOL-06 当前/固定版本 Review 读取授权、只读 Subject Registry 与默认关闭的冻结 `REVIEW_GET` 投影；不提前开放 LIST 或前端决定页面。
