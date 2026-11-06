# CR-EXEC-041：OUT-01-A01-P42 PlanVersion 到 OutputRequest/Job 事务集成

日期：2026-11-07  
状态：编码前检查通过；实现及 Hosted PG18 验收待完成。

## 当前阶段与 WBS

Phase 2 Platform Core / Windows 11 Pilot 纵向业务链。WBS：OUT-01-A01-P42。

## 输入基线与前置

- 冻结 API Contract V1、DB Schema V1、Output Request 与 Jobs/Outbox Owner。
- CR-EXEC-040 / OUT-01-A01-P41 已 PASS_SCOPE_LIMITED：Plan Owner 精确版本查询、项目隔离、输出投影与字段策略已接线；Hosted PG18真实project-scoped lookup通过，但 snapshot reconstruction使用合成fixture。
- 现有 OUT-01-A01-P02 Hosted PG18 transactional Output owner 验收器已覆盖同事务Snapshot/Request/Job/Outbox/Audit/Idempotency持久化及失败回滚。

## 编码前检查

- 问题：现有 PG18 transactional Output owner verifier 只用通用synthetic resolver，尚未验证 CR-EXEC-040 的固定 PlanVersion source-kind/context policy能否实际进入同一事务持久化链。
- 目标：在已存在的合成 PostgreSQL 18 disposable 数据库中，以一个 owner-authorized fixed PlanVersion projection 驱动真实 TrustedOutputContextResolver 与 OutputRequestService，验证 source context、OutputRequest、ContextSnapshot、Job/Outbox、Audit、Idempotency 同事务持久化及同 Key replay。
- 涉及模块：验证Harness、Output application/Owner、Jobs Owner；不修改产品运行代码、ORM、Migration、API、权限模型或打包信任配置。
- 数据：固定测试身份/项目/PlanVersion UUID与WBS字段，仅合成；无客户数据、外部服务或插件执行。
- 权限边界：测试fixture声明的 Plan Owner projection仅用于隔离集成；P41真实Owner授权/查询证据保持独立，不将fixture称为生产授权。新 policy只接受APPROVED；DRAFT拒绝且零写入。
- 插件边界：测试Operation registry仅返回隔离的 enabled/trusted fixture以覆盖Resolver→Output Owner契约；不得触发 PluginService、子进程或文档生成。正式签名Publisher缺失时产品组合继续fail-closed。
- 验收：Hosted父包PG18 smoke内P42单独摘要PASS_SCOPE_LIMITED；请求source ref与context字段精确，字段白名单无多余字段；请求与Job/Outbox引用一致；replay不增加写入；DRAFT/Project mismatch负例无写入；插件执行数为0；原P02/P41/full backend tests均保持通过。
- 回滚：只撤销 P42 verifier 与 P02 Hosted smoke接线，既有Owner产品代码及冻结数据不变。
- 执行位置：GitHub Hosted Windows Server 2025，owned RUNNER_TEMP 的 D盘一次性 PG18；不在本机/C盘运行。

## 风险与关闭条件

- 若测试fixture必须削弱产品授权、Operation trust校验或冻结请求字段，立即停止；不得把测试开关接入正式组合。
- Harness异常必须在D盘owned目录清理数据库；summary仅输出有限布尔/计数结果，无凭据、正文或日志。
- Secret扫描干净、Hosted PG18 probe与全量workflow证据完成后，将结果记入 STATUS/CHANGELOG；整体workflow即使被独立A08阻塞，也只报告P42自身证据，不宣称Gate/Pilot/Release。
