# PKG-PILOT-01-A02：当前候选随包数据库迁移前置检查

日期：2026-10-24；状态：`PRECHECK_PASS / VALIDATION_IN_PROGRESS`。

|检查项|结果|
|---|---|
|当前 Phase / WBS|Phase 2 / `PKG-PILOT-01-A02`：固定 A01 候选的包内 PostgreSQL 18/pgvector `0184→0185` 迁移预检|
|输入基线|Gate 2/CR-PKG-008/CR-PKG-009；A01 非发行 ZIP SHA `da90e98b41e8684a12af83c9d03a0162292cab9288e28c220dc38dfd72a4bb6a` 与独立清洁暂存；当前迁移 `20261024_0185`|
|前置任务|A01 候选完整性/解包/导入通过；旧 P47-A04 临时库演练工具仅支持 `0051→0052`，不可据此声称最新迁移已验|
|涉及模块|仅非发行包迁移烟测工具；使用包内 Python、PG18/pgvector 与现有 Alembic，不改产品数据库代码|
|涉及实体|合成 `plt_system_configurations` 旧行；检查新增 `sol_outline_review_state_results` 与闭合 Trigger|
|涉及 API / 权限|无；不使用正式服务账户或真实客户数据|
|验收标准|一次性隔离 PG 集群中有数据 `0184→0185→0184→0185`、空库直升、旧行保留、新表/触发器存在、pgvector 可用、停止并清理临时集群|
|风险|迁移规模大、失败后临时库残留；仅使用新随机回环端口和直接 Temp 子目录，绝不指向既有数据库；正式安装/升级另验|

本片只验证当前候选随包迁移，不关闭正式 Pilot、客户数据升级或三平台发行。
