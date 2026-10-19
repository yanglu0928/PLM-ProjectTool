# SOL-06-A14-P05：结构化专项原子送审内部服务

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_SUBMIT_INTERNAL_PASS`；已完成冻结送审的内部受权事务链，不表示 HTTP、Windows 生产组合、前端、浏览器、正式信任或 Gate 3 已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A14-P05`|
|输入基线|冻结 `SOL_SPEC_SUBMIT_REVIEW`、CR-SOL-021、A14-P04 统一 Review 状态与 Subject Owner|
|前置任务|最新 DRAFT、现时就绪重证、精确 Trace、0165 状态窄门与 Review 生命周期均已通过|
|涉及模块/实体|solution、project、review、platform idempotency；`StructuredSolutionSpec`、`Review`、`ReviewRound`|
|涉及 API / Schema / 权限|新增内部 Service、版本到系列身份解析和 `SOL_SPEC_SUBMIT_REVIEW` ProjectManager 策略；冻结 URL/JSON、0165 Schema、License 权益和依赖不变；尚未装配公开入口|
|验收标准|Session/CSRF/License/ProjectManager/Reviewer 当前事实；服务端从路径版本解析系列；Review 创建、开轮、状态、Audit 与收据同事务；同 Key 精确重放；请求漂移冲突；任一步失败全回滚|
|风险|让客户端声明 series 导致错绑；先创建 Review 后状态失败留下中间态；重放不复验访问；审计失败遗留 Review 或 PENDING 收据；锁顺序倒置|

## 实施结果

- 新增 `StructuredSpecReviewSubmissionService`，固定操作 `V1_SOL_SPEC_SUBMIT_REVIEW`、结果 `V1_SOL_SPEC_REVIEW_SUBMISSION`、Subject `SOL-06` 与策略 `STRUCTURED_SPEC_ALL_V1`。只接受 ProjectManager，Reviewer 最多 32 名并按 UUID 规范排序。
- 冻结路径只提供 `structured_solution_spec_id`；服务端在调用方事务内解析不可变 `spec_series_id`，不接受客户端系列声明。身份解析不预先取得行锁，随后由 Subject Owner 按既有系列 advisory lock 顺序锁定并重新验证最新 DRAFT、Reviewer 与全部当前事实，避免行锁到系列锁的顺序倒置。
- 首次提交在单一事务内保留持久幂等号、创建 PROJECT Review、启动首轮、绑定 SOL-06 状态回执、写 Review Audit 并完成 201 回执。License 在写前和提交前各检查一次；异常由 Unit of Work 回滚，不暴露中间 DRAFT Review。
- 重放从 Review 持久事实恢复首次 Review/Round，不重新解析客户端外的系列身份，但由 SOL-06 Owner 重新锁定 Subject 并检查当前访问；同 Key 不同项目/版本/Reviewer/策略指纹返回 `CONFLICT_IDEMPOTENCY`。
- 新增独立项目策略 `SOL_SPEC_SUBMIT_REVIEW`，角色仅 `PROJECT_MANAGER`，不扩大 ImplementationMember 或客户角色权限；未修改冻结 HTTP 请求/响应。

## 验证证据

- 定向单元与回归：31 项通过，另有 809 个权限矩阵子例；覆盖规范 Reviewer、内部系列解析、请求绑定证明、收据、重放当前访问、License/角色/缺身份失败和既有 Review 持久化/Owner 合同。
- 后端全量：`3744 passed, 3 skipped, 5832 subtests passed`；`py_compile`、`git diff --check` 通过。
- Windows 11 / PostgreSQL 18.6：在 A14-P04 的真实五版本/三轮 Review 链上，对最新 DRAFT 注入 Audit 失败，Review、Round、SOL-06 状态回执和平台收据计数均保持不变，版本仍为无 Review 指针的 DRAFT；使用同一 Key 随后成功创建并开轮。
- 成功后原 Key 精确重放同一 Review/Round，改变 Reviewer 集合返回冲突；数据库仅一条新 Review、Round、START 状态回执和平台完成收据，Trace 下恰有 `REVIEW_CREATED`、`REVIEW_STARTED` 两项 Audit，旧 APPROVED 指针保持不变。
- 开发 wheel 共 1414 项，SHA-256 `7a5d195f3922dcc68151b517fc8f8da10ee89f65167dd8e2cb6a75ea5b1e1e36`；仅为开发验证产物，不是 Pilot 或正式发行包。

## 偏差、兼容、升级与回滚

- 冻结端点只含版本 ID，而统一 Review 的 Subject 根是系列 ID。按 CR-SOL-021 在服务端同事务解析不可变系列，并由 Owner 再锁定/重证；未增加请求字段或改变冻结响应。
- 为保持锁顺序，身份解析只读不可变映射，不在取得系列 advisory lock 前持有版本行锁。真正的并发与现时资格由 Owner 在同事务锁内裁决，单元和真实 PostgreSQL 链均通过。
- 首次尝试 `python -m build --wheel` 因当前环境 `build` 包无可执行入口未产出新包；改用已安装 pip 的 `--python` 指向 Python 3.13 后端环境，并以 `--no-deps --no-build-isolation` 本地构建成功，没有下载或改变依赖。
- 无 Migration、冻结 URL/JSON、License、依赖或既有数据变化。尚未公开装配，可撤内部 Service/策略；一旦后续入口产生 Review、状态、Audit 或收据，回滚只能关闭入口并保留历史，不得删除或改写。
- 正式服务账户/公钥信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 和正式发行状态不变。

Next：`SOL-06-A14-P06` 实现默认关闭的冻结送审 HTTP 合同，严格要求 `due_at` 与 `submission_note` 显式为 `null`，并保持路径版本、201 ReviewRef/RoundRef、错误映射与无缓存边界；Windows 组合另项验收。
