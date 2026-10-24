# SOL-06-A13-P05：结构化专项内部受权验证 Service

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_VALIDATION_SERVICE_PG_PASS`；只完成内部 Service、正式策略映射、持久收据/Audit 与重放，不表示 HTTP、Windows 组合或送审已实现。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A13-P05`|
|输入基线|A13-P02 首次观察报告合同、A13-P03 共享锁固定来源、A13-P04 当前事实评估器；SectionVersion VALIDATE 的已验收原子模式|
|前置任务|报告序列化、受锁来源、当前 Owner、通用 Session/CSRF、License、项目授权、幂等收据和 Audit 均已存在|
|涉及模块/实体|Solution；SOL-06 固定版本；通用 IdempotencyReceipt 与 AuditEvent|
|涉及 API / 权限|新增冻结操作对应的 `SOL_STRUCTURED_SPEC_VALIDATE` 策略；仅 ProjectManager、ImplementationMember，ACTIVE 项目写策略；尚无 Router|
|验收标准|首次观察同事务完成授权、共享锁读取、现时评估、Audit 与收据；重放重新鉴权并恢复首次报告；错误/回滚不留持久结果|
|风险|同 Key 重新采样产生不同报告；Audit SUCCESS 被误解为业务通过；失效 License/Session 或跨项目仍读取来源；收据与 Audit 绑定不一致；来源撤回恢复后错误忽略摘要漂移|

## 实施结果

- 新增 `StructuredSpecValidationService`：先校验 License、Session/CSRF 与项目写角色，再按用户/项目/操作/Key 预留收据，并在同一事务调用 A13-P03 Repository 和 A13-P04 评估器。首次观察追加 `SOL_STRUCTURED_SPEC_VALIDATED` Audit、完成 `V1_SOL_STRUCTURED_SPEC_VALIDATE` 收据、反读 Audit 绑定、再次校验 License 后才提交。
- Audit 的 `SUCCESS` 只表示验证命令完成；八维事实、类型检查、`valid`、`ready_for_review` 与问题码仍由报告准确表达。Service 不修改专项版本、系列、Review 或批准状态。
- 同 Key 重放仍重新检查 License、Session/CSRF、现时项目角色和固定版本归属，但不重新采样来源；由收据绑定的 Audit 原因码恢复首次 observation、TraceId 与时间。收据类型/状态、Audit 主体/项目/系列/版本/状态任一不一致均失败关闭。
- 新增 `SqlAlchemyStructuredSpecValidationAuditSource`，只读取严格绑定的 PROJECT/USER/SUCCESS/SOL-06 Audit；新增项目策略与策略单元基线。无新增表或 Migration。

## 验证证据

- P02～P05 与项目策略联合定向：69 项、800 子例通过；P05 覆盖首次原子观察、原结果重放、两类写角色拒绝、归档/缺失、Session/License、幂等冲突、Audit 反读失败和提交前 License 二次失效。
- Windows 11 / 可弃 PostgreSQL 18.6：真实 Auth、Project、License、Requirement、Section/Document、Evidence、SOL-06 v1/v2、通用收据和 Audit；项目经理与实施成员均可验证，跨项目/错误 CSRF/失效 License 拒绝，当前与历史首次观察准确，同 Key 返回原报告，新 Key 在 Evidence 撤回后重采为 `UNAVAILABLE`，Audit 故障整事务回滚。四条成功命令对应四条收据和四条 Audit；脚本退出 0，临时库/实例按既有夹具清理。
- Evidence 从 INELIGIBLE 恢复后 lock version 已变化；首轮验收误期望新观察重新 `valid=true`，实际 integrity 正确为 `FAIL`。修正测试断言后完整重跑，保留不可变创建摘要语义，未放宽产品逻辑。
- 后端全量：`3720 passed, 3 skipped, 5796 subtests passed in 76.48s`。
- py_compile、`git diff --check` 通过。
- Python 3.13.15 开发 wheel：1407 个条目，Service 与 AuditSource 各入包 1 份；SHA-256 `cb936384c9fcbbf99480fdaee6f21a8fd0b59d1f2e2d01a10437590c70fd6fa0`。
- 无 Migration、外部 AI/网络、客户数据或 Secret 外发。

## 兼容、升级、回滚与遗留

本项只增加未装配的内部 Service/AuditSource、冻结角色对应的项目策略、测试与验证脚本；无 Schema、冻结 API 字段/路径、License 权益、依赖或旧数据变化。未开放 Router 时无外部运行行为；可撤 Service、AuditSource 与策略，但已经写入的 Audit/收据不得删除。开发 wheel 不是 Pilot 或正式发行包。

HTTP、Windows 平台装配、页面/Edge 尚未实现。Trace、非空 Artifact 及各类型非结构业务检查缺少正式 Owner，报告继续明确不可送审。正式信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 与正式发行状态不变。

Next：`SOL-06-A13-P06` 实现默认关闭的冻结 VALIDATE HTTP 合同：严格空正文、Session/CSRF/Idempotency-Key、路径身份、200 报告投影和统一错误；不做 Windows 装配。
