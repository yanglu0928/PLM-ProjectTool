# SOL-02-A02：目录创建首次结果快照 Schema 0145 增量

日期：2026-10-09；依据冻结 DM-05/SC-01/02、API-04 `SOL_OUTLINE_CREATE`、CR-SOL-011。原 Gate 2 冻结提交 `64cdf09` 保留。

迁移 `20261009_0145` 新增 `plm.sol_outline_create_results`，以 `solution_outline_id` 为主键，`(solution_outline_id, project_id)` 复合外键指向 `sol_outlines`；保存首次规范名称和有限的 `created_at`。名称与根同为去首尾空白的 1..500 字符。ORM 与迁移同构。该表为后续持久 Receipt 的不可变 201 首次响应快照，不是目录版本、审批、Trace 或业务承诺。

A02 仍使用 0136 的全拒 DML Guard：目录根与结果表的 INSERT/UPDATE/DELETE 均拒绝；两个表的 TRUNCATE 也拒绝。A03 必须与受权 Owner 同一交付单元才可把创建 INSERT 有界解锁，不能单独部署无 Owner 的写入窗口。当前任何应用路由、权限、License、Secret 或客户数据均未改变。

升级从 0144 线性执行，现有 Project/User 数据保留；表为空时可降至 0144 并重升，已有结果快照时拒绝降级，不得删历史强行回滚。独立 Win11 PostgreSQL 18.6/pgvector 临时实例已验证空表/有基础数据升级、三次 Alembic drift、无历史降级重升、根/结果写与 TRUNCATE 拒绝、隔离测试下复合 FK/名称/重复主键、有结果历史拒降，退出 0；测试后实例停止、临时目录清理。既有 0136/0137 数据、生产账号权限和 A03 后的真实并发重放不在本项验证范围。

TraceLink：Gate 2 → CR-SOL-001/002 → CR-SOL-011/DEC-20261009-1123 → 0145 → SOL-02-A03。
