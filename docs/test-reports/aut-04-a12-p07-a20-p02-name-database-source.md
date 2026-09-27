# P07-A20-P02 实际数据库结果

2026-09-27，Windows 11 / Python 3.13.15 / PostgreSQL 18临时库。

修正后完整执行exit0：真实缺行RESOURCE_NOT_FOUND、规范名称当前源错配AUTH_PATCH_UNAVAILABLE、最大bigint版本CONFLICT_VERSION、唯一名称CONFLICT_DUPLICATE、非唯一检查约束23514原IntegrityError传播、更新结果时间倒退AUTH_PATCH_UNAVAILABLE。每场景退出未提交UOW后九表全行一致，pg_constraint确认TEST_ONLY约束已撤销。

首轮exit1原因：验收脚本错误推断updated_by有外键，实际未拒绝；审阅0006确认字段无FK，上层负责授权，不改生产。记录后改用临时库未提交UOW新增检查约束，保留全部原约束，不mock成功SQL，再完整重跑。

原名称修改并发/重放/审计与末核回滚、原dualScope空集/260行文件发布验证通过。仅合成用户/License/临时Vault；非生产安全锚或发行证明。完整unit最近1524项本项未重跑，覆盖率/性能/wheel未运行。完整Auth分支84.717%仍为最近实际结果，不推算提升。追溯DEC-20260927-368及同名progress/validation脚本；无生产、Migration、API、依赖变化，无升级要求。
