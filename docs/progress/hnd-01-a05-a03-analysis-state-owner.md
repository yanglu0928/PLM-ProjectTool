# HND-01-A05-A03：Handover Analysis 元数据与归档 Owner

日期：2026-10-05。结论：`HND_01_A05_A03_ANALYSIS_STATE_OWNER_PASS`。下一项：`HND-01-A05-A04` 五个普通写 HTTP。

## 编码前检查与变更

冻结 API-04 已定义 Analysis PATCH/ARCHIVE，但 Schema0101 守卫禁止目的与状态变化。按持续授权先登记 `CR-HND-005`，再新增向前 Migration0102；不改写0101或 Gate 2 冻结提交。

0102只开放两种精确形态：ACTIVE Analysis 的 `analysis_purpose` 单字段更新，以及 ACTIVE→ARCHIVED。两者均要求 Root 行锁、锁版本递增、当前操作者和更新时间有效，并在数据库与仓储双层拒绝任何 `IN_REVIEW` Version。既有 Review Owner 对锁版本和正式指针的原子推进保持不变；来源摘要、正式指针、Version/Item 内容与历史删除未开放。

内部 Service 每次验证 License、Session/CSRF 与当前 Project 成员：PATCH 仅 ProjectManager/ImplementationMember，ARCHIVE 仅 ProjectManager。PATCH 规范化 Unicode/空白、强 ETag并拒绝无变化写；ARCHIVE 使用项目级持久幂等收据并精确重放首次 `ARCHIVED` 结果。两者在同事务写不可变 Audit，提交前再次检查 License。

## 兼容、迁移与回滚

无新表列、冻结 URL、依赖、配置、Secret、网络、外发或客户数据变化。公开 Router 仍关闭。0102只替换共享守卫函数；存在 ARCHIVED 或 PATCH/ARCHIVE Audit 历史时拒绝降级。可停止装配状态 Owner阻止新写；既有归档与审计必须保留，只能向前修复，不能恢复 ACTIVE。

## 客观验证

- 定向17项通过（Service、Schema、授权矩阵、Migration合同）。
- Windows 11 / PostgreSQL 18.6：空库0102升降重升、两次drift、PM/实施成员/客户角色、跨项目、强ETag、在审PATCH/ARCHIVE拒绝、归档精确重放、License拒绝、Audit失败全链回滚、归档后数据库写拒绝与历史拒降通过。
- 后端全量2687项通过，3项跳过。
- wheel解包导入：`HND_01_A05_A03_WHEEL_IMPORT_PASS`；SHA-256 `f095e967558071076e09b25dbd44fbced0873710de760b7c79407719a072a472`。

A01表格原只列A04的CREATE/VERSION_CREATE/VALIDATE，遗漏同属普通写的PATCH/ARCHIVE传输层；已更正为A04一次覆盖五个普通写端点，避免A07出现“全11 Operation”却缺两条Router的断链。

已知未完成：A04五写HTTP、A05业务原子送审、A06五读HTTP/cursor、A07 Windows组合与真实HTTP/PG；Server2025、Debian13、Gate 3和发行验收仍按总状态跟踪。
