# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P03-P02：Plan Validate不可变报告结果Schema

日期：2026-10-26。结果：`PLAN_VERSION_VALIDATION_RESULT_SCHEMA_PASS`；非Owner/API/Gate结论。

## 编码前检查

- 当前Phase：Phase 2 Platform Core。
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P03-P02`。
- 输入基线：Gate 2冻结DB Schema V1/commit `64cdf09`、CR-PLAN-006、0188 Plan append-only guards、Audit/Receipt合同。
- 前置任务：A06-P03-P01已记录幂等报告缺口并授权CR-PLAN-006；A06-P02纯报告合同全量回归通过。
- 涉及模块：Plan ORM/Migration、Plan迁移测试、独立隔离PG18验证器。
- 涉及实体：AuditEvent引用、固定PlanVersion复合身份、首次Report payload及固定版本snapshot fingerprint。
- 涉及API：无；未新增HTTP或修改冻结Validate合同。
- 涉及权限：Schema不授予业务权限；未来Owner仍须先做当前Session/CSRF/License/Project PM或IM检查。
- 验收标准：单个专属不可变结果表、Audit/PlanVersion范围FK、报告JSON形状约束、有效与阻断列表一致性；DB INSERT trigger要求匹配Audit身份；拒绝UPDATE/DELETE/TRUNCATE；空库0188→0189→0188→0189、历史存在拒绝降级、Alembic drift清洁。
- 风险：报告结果应只通过后续授权Owner写入；0189不得单独发布开放不完整业务写入口。

## 实施结果

- 新增`PlanVersionValidationResultRow`及Migration `20261026_0189`，保存AuditEvent主键关联、Project/Plan/PlanVersion、snapshot fingerprint、valid、阻断/警告数组、覆盖计数对象和首次`checked_at`。
- 增加固定PlanVersion复合FK及Audit FK；DB INSERT trigger要求匹配同Project、同PlanVersion、plan/PLN-02、USER/SUCCESS/`PLAN_VERSION_VALIDATED` AuditEvent；更新/删除及TRUNCATE均失败关闭。
- Downgrade遇到任一报告历史行即拒绝；空表允许回退并保留0188。新表无客户正文/API Key/License载荷。
- 修正迁移head与ORM表清单回归合同。另修正一个本轮全回归发现的既有Handover随机测试篡改操作（可能未改变原令牌）；只改测试输入生成，不改Handover运行逻辑。

## 验证

- 迁移/ORM定向测试：`9 passed`。
- Windows 11隔离PostgreSQL 18：0188→0189空库升迁、drift；合成历史触发器下UPDATE/DELETE/TRUNCATE拒绝；有历史拒绝降级且历史保留；清理合成行后降迁/重升/drift通过。验证器：`PLAN_02_A06_VALIDATION_RESULTS_SCHEMA_PASS`。
- 完整后端回归：`4141 passed, 3 skipped, 6190 subtests passed`。
- Alembic检查只保留仓库历史已有的vector opclass/计算默认值比较警告，最终`No new upgrade operations detected.`。
- 历史触发器验证记录由仅限本次隔离临时超级用户数据库使用`session_replication_role=replica`注入合成行以覆盖UPDATE/DELETE/TRUNCATE与降级保护；不伪装真实Session/Plan/Audit有效插入。有效业务行/Audit匹配由下一Owner集成验证。

## 兼容与后续

- Migration 0189为CR-PLAN-006追加Schema，原冻结commit不变；含结果行时不能降级删除历史。
- 下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P03-P03`，实现内部事务Owner，验证当前Session/License/Project PM或IM、固定PlanVersion及Approved来源/coverage，且Audit/不可变报告行/通用幂等Receipt原子写入；同Key恢复首次Report，不同payload冲突；无HTTP挂载。
- Server 2025/Debian、正式信任、Pilot、Gate 3及正式Release未在本项验证。
