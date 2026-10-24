# P07-A20-P02 名称修改实际数据库来源

2026-09-27编码前检查：Phase 2，WBS AUT-04-A12-P07-A20-P02；输入冻结64cdf09/0049、A20-P01及既有名称修改实际验证。仅Auth User名称Repository验收，不改生产实体、API、权限、Migration或依赖。

验收计划：在验证脚本自建临时PostgreSQL库中执行真实缺行、当前名称错配、最大bigint版本、重复规范名称、非重复IntegrityError及更新结果时间倒退拒绝；每次退出UOW后九表全行快照一致。先真实SQL读取/更新，不模拟成功SQL，不停用约束或触发器。实际外键错误应保持原IntegrityError，不冒充固定错误码。运行原名称修改并发/审计/末核回归。

风险与回滚：仅测试临时库合成用户，故障更新全部置于未提交UOW，临时资源由原fixture清理；不得操作生产库。若约束客观禁止某故障，则记录保护证据及未执行分支，不绕过约束。无发行升级。完整coverage、性能、wheel不在本项；原Gate/正式信任源/性能FAIL仍保留。

验证计划修正：首轮exit1，前四场景及原名称回归通过，但错误假设updated_by存在外键。0006与实际SQL证明该字段仅UUID来源字段，Repository不承诺账号授权（上层Access负责）；不改生产约束。改为在同一未提交临时UOW新增TEST_ONLY名称检查约束，以真实23514验证非唯一IntegrityError传播，事务退出撤销DDL与数据。禁止移除/停用既有约束。该新增约束不进入Migration或生产。

结果：修正后完整重跑exit0，六场景全部实际PG通过，九表全行回滚；每次pg_constraint确认临时约束不存在。原名称并发/重放/审计/末核与dualScope空集/260行发布回归通过。仅Windows 11合成用户/License/临时Vault与数据库，不代表正式信任源或发行通过。unit最近1524项本项未重跑；coverage/性能/wheel未运行。下一A21完整安全覆盖复验（新增本链，新runtime保留旧raw）。
