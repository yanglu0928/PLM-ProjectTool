# CR-HND-005：Handover Analysis 元数据与归档 Owner

日期：2026-10-05。状态：依 V1.1 持续授权已实施并验证。关联 `HND-01-A05-A03`、冻结 API-04、DM-05、Schema0101/0102 与 DEC-870～872；不改写 Gate 2 原冻结提交 `64cdf09`。

## 触发与差异

冻结 API 已定义 `HND_ANALYSIS_PATCH` 与 `HND_ANALYSIS_ARCHIVE`，但当前 Schema0101 的共享 Owner 守卫明确禁止 `analysis_purpose` 和 `analysis_state` 变化，因此应用层无法在不绕过数据库边界的情况下实现两个正式 Operation。直接只写应用仓储会被数据库拒绝，也无法防止在审期间元数据漂移。

## 选择与实施计划

- 新增向前 Migration 0102，不改写0101；共享守卫只新增两种精确形态：ACTIVE 的 `analysis_purpose` 单字段更新，以及 ACTIVE→ARCHIVED 单向终态。
- PATCH/ARCHIVE 均使用强 ETag、行锁和固定 Analysis→Version 锁序，并拒绝存在 `IN_REVIEW` Version；PATCH 仅 ProjectManager/ImplementationMember，ARCHIVE 仅 ProjectManager。
- PATCH 不使用幂等键但拒绝无变化写；ARCHIVE 使用项目级持久幂等收据，精确重放只返回首次 ARCHIVED 结果。两者写不可变 Audit，重新验证 License、Session/CSRF 和当前 Project 成员事实。
- 保留 Review Owner 对 Root 锁版本与正式指针的原子推进；不开放来源摘要、正式指针、Version/Item 内容或历史删除。

## 风险、迁移、回滚与验证计划

主要风险是元数据在评审中漂移、归档后继续升版/送审、守卫过宽允许组合写、旧 ETag 覆盖新事实以及重放产生第二条 Audit。0102 将在数据库守卫与应用仓储双层拒绝在审写，并由既有 create/version/review Owner 的 ACTIVE 条件封闭归档后写入。

已验证空库 `0101 -> 0102 -> 0101 -> 0102`、Alembic drift、守卫正反例、角色/跨项目、强 ETag、在审栅栏、重放/Audit/回滚与归档后写拒绝；存在 ARCHIVED 或 PATCH/ARCHIVE Audit 历史时拒绝降级。后端2687项通过/3项跳过，wheel解包导入通过，SHA-256 `f095e967558071076e09b25dbd44fbced0873710de760b7c79407719a072a472`。回滚只能停止新入口并向前修复，不能删除历史或把已归档 Analysis 恢复为 ACTIVE。

无新表列、依赖、配置、Secret、网络、外发或客户数据变化。公开 HTTP 仍留在后续 A04/A06，A03 只实现内部 Owner 与数据库边界。
