# SOL-06-A14-P04：结构化专项统一 Review 状态窄门与 Subject Owner

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVIEW_OWNER_PASS`；已完成 SOL-06 的统一 Review 内部 Owner、数据库状态窄门和不可变生命周期回执，不表示冻结送审 HTTP、用户界面、正式信任或 Gate 3 已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A14-P04`|
|输入基线|CR-SOL-021、DEC-20261019-1209；A14-P02 V2 设计就绪；A14-P03 精确 ACTIVE `IMPLEMENTS`；统一 PROJECT Review|
|前置任务|结构化专项 DRAFT 创建/修订、固定来源重建、当前事实评估、精确 Trace 均已通过；0164 仍禁止任何状态更新|
|涉及模块/实体|solution、review、project、audit；`StructuredSolutionSpec`、`Review`、`ReviewRound`、不可变状态结果|
|涉及 API / Schema / 权限|新增 Migration `20261019_0165` 与内部 Owner/Repository；冻结 URL/JSON/角色、License 权益和依赖不变；尚未装配公开送审入口|
|验收标准|只允许最新 DRAFT 开始；同事务重算全部当前事实；开始绑定 Review/Round；批准唯一化并替代旧批准版；退回/撤回不改变当前批准版；直接写、缺回执、篡改、危险降级失败关闭|
|风险|复用历史 VALIDATE 误作现时证明；状态更新脱离 Review；同系列出现多个 APPROVED；退回误清批准指针；已有历史被降级删除|

## 实施结果

- 新增 `20261019_0165`，将 0164 的 INSERT-only 根 Guard 收窄为四类合法状态动作：`DRAFT→IN_REVIEW`、`IN_REVIEW→APPROVED/RETURNED`、旧 `APPROVED→SUPERSEDED`；身份、版本、前驱、正文摘要和创建信息继续不可变，系列 advisory lock 保持与创建/修订相同顺序。
- 新增 `sol_spec_review_state_results` 不可变回执，固定专项版本、系列、项目、Review/Round、事件、前后批准指针、Actor 和时间。数据库触发器核对 `SOL-06`、`STRUCTURED_SPEC_ALL_V1`、PROJECT Scope、固定 Round 版本、Review 终态和 Review 事件，并以延迟闭合触发器禁止“改状态但不写回执”。每个系列至多一个 `APPROVED`。
- 新增 `StructuredSpecReviewReadinessService`。开始和批准均在调用方事务、同一固定版本/系列锁内重新运行八维当前事实与 V2 类型检查；不读取或信任历史 VALIDATE Audit。Review 请求临时证明上下文只携 Session token 与 Trace，不持久化、不渲染、不写审计。
- 新增 `StructuredSpecReviewSubjectOwner` 与 SQL Repository。Subject 固定为 `SOL-06 / spec_series_id / structured_solution_spec_id`，策略固定为 `STRUCTURED_SPEC_ALL_V1`；所有 Reviewer 必须是当前项目合格成员。批准会先把旧批准版本转 `SUPERSEDED` 再将目标转 `APPROVED`；退回或撤回映射为 `RETURNED` 且保留旧批准版。
- 通用 Review 开轮命令现在把请求绑定的证明上下文传给 Subject Owner；既有 Owner 不消费该上下文，既有行为保持。终态消费在 Review 写入后、提交前完成，Owner 回执、Review 事件、Subject 状态和 Audit 同事务失败回滚。

## 验证证据

- 定向单元与合同：34 项通过，覆盖现时就绪、Owner 创建/开始/批准/撤回、Reviewer 资格、缺证明上下文失败、迁移链头及通用开轮回归。
- 后端全量：`3741 passed, 3 skipped, 5823 subtests passed`；`py_compile` 和 `git diff --check` 通过。
- Windows 11 / PostgreSQL 18.6：从 0164 的既有 DRAFT 数据升级至 0165，ORM drift 为零，空 Review 历史可降级/重升；真实统一 Review 完成第二版批准、第三版批准并替代旧批准版、第四版退回且保留第三版批准指针。
- 数据库负例：直接把 DRAFT 改为 APPROVED、只绑定 Review/Round 而不写状态回执、修改既有回执均被拒；产生 Review 历史后降级至 0164 被拒，历史与正文未删除。
- A14-P03、SOL-05 来源 Owner 及上游真实来源链在同次脚本回归通过。开发 wheel 共 1413 项，SHA-256 `6f8669ebdb7c284275f1047b293fdd7fedea298c80a7d64e8cd7c6ef0fa6c41e`；仅为开发验证产物，不是 Pilot 或正式发行包。

## 偏差、兼容、升级与回滚

- 首次真实链运行暴露 Review Repository 使用了不存在的 `latest_version_id` 属性；固定来源合同实际字段为 `latest_version_ref`。修正字段名后从新库完整重跑，未放宽验证。
- 首次新验证入口少引用一层历史夹具模块而无法启动；按 A14-P03 的真实依赖链补齐一级后重跑。此偏差只影响验证脚本，不改变产品行为。
- 首次后端全量因 ORM 历史库存断言未登记新回执表而 1 项失败；补入明确表清单后全量重跑为零失败。未修改数据库或业务断言。
- 升级必须先备份数据库，再由 0164 升至 0165；既有 DRAFT 原样保留。若尚无 SOL-06 Review 状态/回执，可降级；一旦存在任何新状态或 Review 回执，迁移主动拒降。运行回滚应关闭后续送审入口并保留 0165 及历史，不得删除回执或恢复旧批准状态。
- 本项无冻结 API Breaking、角色/License/依赖变化。原子 `SOL_SPEC_SUBMIT_REVIEW` 服务/HTTP、Windows 生产组合、前端、Edge、非空 Artifact、正式信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 和正式发行仍未完成。

Next：`SOL-06-A14-P05` 实现冻结 `SOL_SPEC_SUBMIT_REVIEW` 的原子内部服务，统一完成 Review 创建与首轮启动、持久收据/Audit、同 Key 当前访问重验和失败全回滚；不提前开放 HTTP。
