# SOL-06-A14-P02：结构化专项设计就绪合同版本化

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_DESIGN_READINESS_PASS`；已完成 CR-SOL-021 的类型检查合同、历史 Audit 兼容和当前评估器接入，不表示 Trace、送审、评审、实施或客户验收已完成。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A14-P02`|
|输入基线|CR-SOL-021；A13 固定版本验证合同、当前事实评估器、HTTP 与前端报告；冻结 `SOL_SPEC_VALIDATE` 顶层响应|
|前置任务|A14-P01 已确定设计就绪与执行证明分离；V1 Audit reason 已在持久化重放中使用，必须保留原义|
|涉及模块/实体|Solution 应用合同/当前事实评估器；前端验证客户端/固定详情；Audit reason 反读|
|涉及 API / Schema / 权限|不改冻结 URL、顶层字段、角色、数据库或 License；只版本化现有 `type_checks.code` 集合和 Audit reason 前缀|
|验收标准|四类 V2 设计声明精确有序；新观察写 V2；V1/V2 严格原样反读；混合/乱序失败关闭；缺 Trace 时仍不可送审；前后端和 Edge/PG 一致|
|风险|把计划声明误报成执行结果；旧 Audit 无法重放；服务端与严格前端不同步；V2 全 PASS 意外绕过 Trace|

## 实施结果

- 新观察默认使用 `SPEC_VALIDATION_V2_*`，四类检查按 CR-SOL-021 固定为设计声明代码；V1 代码集和 `SPEC_VALIDATION_V1_*` 解码路径完整保留，历史状态字母不会被重新解释或回写。
- `StructuredSpecTypeChecks` 只接受某一完整版本的精确有序集合，不能混用 V1/V2。Audit reason 的版本前缀决定检查代码语义，非法版本、长度、类型或状态继续失败关闭。
- 当前事实评估器仅在结构化正文已通过严格 payload validator 后把 V2 设计声明标为 PASS；这只表示已保存字段的结构和声明完整。实际运行、试迁移、对账、回滚及客户验收仍必须由后续实施/UAT Owner 形成事实。
- 前端严格解析当前 V2 和历史 V1 两套完整集合，并继续独立复算 issue、valid 与 ready；页面明确提示“设计声明完整不代表已实施、已试运行或已获客户验收”。
- Trace 仍由正式 Owner 决定且当前为 `UNAVAILABLE`，因此真实当前版本仍为 `valid=true / ready_for_review=false`，未绕过送审前置。

## 验证证据

- 后端定向：60 项、13 子测试通过，覆盖四类型 V2、V1 Audit 严格反读、派生结论、当前评估器、首次结果重放和 HTTP 投影。
- 后端全量：`3729 passed, 3 skipped, 5817 subtests passed`；最终代码 `py_compile` 与 `git diff --check` 通过。
- 前端定向：2 文件 10 项通过；最终全量 146 文件、1811 项通过；Vue/TypeScript typecheck 和 production build 通过。既有主 chunk 大小提示保留，不是本项新增失败。
- Windows 11 / 可弃 PostgreSQL 18.6：真实 Requirement、Section、Document、Evidence 来源中 V2 五项迁移设计声明全部 PASS，历史系列身份 FAIL，Trace 保持 UNAVAILABLE，报告不具备送审条件；空库至 head 的 Alembic check 无新操作。
- Windows 11 Edge → 构建 Vue → 生产 FastAPI/Uvicorn → PostgreSQL 18.6：首次观察、原 Key 重放、V2 五项展示、非执行/验收警示、跨项目 404/清屏及唯一收据/Audit 全部通过。
- Python 3.13.15 开发 wheel 共 1408 项，两个变更运行模块均入包；SHA-256 `b52067f26c7f6fc142ce0e4a642744230ab06c68a99cb072e14d5e62438e5b1e`。该 wheel 仅为开发验证产物，不是 Pilot 或正式发行包。

## 偏差、兼容、升级与回滚

- 首轮前端 typecheck 暴露回调内数组类型窄化未保持，改为在严格外层校验后绑定本地 `unknown[]` 再解析；定向、全量和生产构建均已重跑。产品运行语义未放宽。
- wheel 首两次装配分别因后端 venv 未带 pip、全局 Python 3.13 未带 setuptools 失败；改用系统 pip 的 `--python` 指向已锁依赖的后端 venv、`--no-deps --no-build-isolation` 本地构建成功，无网络下载或依赖变化。
- 无 Migration、冻结顶层 API、权限、License、依赖或既有业务数据变化。服务端和前端必须同版本部署；旧前端会拒绝 V2，新前端可读取 V1/V2。尚未产生 V2 观察时可整体回退；一旦产生 V2 Audit，不得回退解码器或改写历史，应先关闭新验证入口并保留兼容读取。
- 正式信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 和正式发行状态不变。

Next：`SOL-06-A14-P03` 增加 SOL-06 固定目标证明及精确 ACTIVE `IMPLEMENTS` Trace 覆盖，并接入当前事实评估器；不提前实现 Review 状态迁移或送审。
