# TRC-01-A07-P02：TraceLink 数据库拥有的资源版本

日期：2026-10-02；Phase 2；状态：**Schema PASS，撤销命令未实现**。输入冻结 API-01/02、CR-TRC-003与DEC-20261002-613；Gate 2 原冻结 `64cdf09` 保留。

新增ORM `lock_version` 与增量迁移 `20261002_0053`：ACTIVE为v0，唯一合法终态REVOKED/SUPERSEDED为v1。独立数据库触发器在原历史守卫之后拒绝显式版本改写并执行一次自增；CHECK约束锁定状态/版本组合。迁移在受锁事务内短暂停用原触发器回填历史终态，立即恢复；降级遇任何终态历史拒绝丢弃版本。

验证：Windows 11 自启动一次性 PostgreSQL 18，空库head→0052→head且ORM无新差异；含ACTIVE数据0052→head→0052→head无损；含REVOKED/SUPERSEDED历史0052→head正确回填，新增终态一次自增，直接改版本/重复状态变化拒绝，终态down拒绝且原迁移版本与行保留。首轮验证脚本错误查询public的Alembic版本表，修正为plm后完整重跑PASS。原迁移Head断言从0052更新为0053后，后端全量1885运行/3跳过/无失败；开发wheel SHA-256 `70602728cb93c47ce4e37048c325e79e0876d13d1d19d2adf22ef8ec2083dbf2`。

兼容/升级/回滚：Schema只增列、约束和触发器，无公开API或新依赖；空库/ACTIVE数据可降级，已有终态版本不得降级，须备份与正向修复。未运行生产迁移；内部撤销/关系Owner、正式信任/三平台/UAT/Gate与可用包仍待。
