# SOL-02-A03：SolutionOutline 创建 Owner Schema 0146 增量

日期：2026-10-09；依据冻结 DM-05/SC-01/02/API-04、CR-SOL-011、DEC-20261009-1123/1124。原 Gate 2 冻结提交 `64cdf09` 保留。

迁移 `20261009_0146` 将既有 Solution 身份 Guard 按表/操作收窄：`sol_outlines` 只接纳 ACTIVE、无 Approved 指针、锁版本 0 的 INSERT；`sol_outline_create_results` 只接纳与当前根项目、规范名称及 `created_at` 完全一致的 INSERT。两表 UPDATE/DELETE、Section 任意 DML、TRUNCATE 全部继续拒绝。根 INSERT 另设 `DEFERRABLE INITIALLY DEFERRED` 约束触发器，提交前必须存在对应首次结果；直接提交孤立根失败。该约束不是 Session/Project 授权证明，业务授权由内部 Owner 同事务执行，正式 DB 服务账户权限由 Release 独立验收。

升级从 0145 线性执行，不转移数据，不改已有 ORM 列/API。无目录历史时可降回 0145 并恢复全拒 Guard；存在根或快照历史时拒降，不能删除业务历史强行回滚。Win11 一次性 PG18.6/pgvector 含已有 Project、Auth、Reference 数据的迁移重升、Alembic drift、真实目录创建/重放/失败关闭与非空拒降通过；A02 旧关闭态脚本在当前 Head 下复跑通过。Server2025、正式信任源/目标 DB 角色、20 并发、UAT/发行独立未验。

TraceLink：CR-SOL-011 → 0145 → DEC-20261009-1124 → 0146/SOL-02-A03。
