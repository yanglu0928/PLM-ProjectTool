# SOL-02-A02：目录创建结果快照持久层

日期：2026-10-09；结果：`OUTLINE_CREATE_RESULT_SCHEMA_PASS`，限定 Schema/ORM 和关闭的写边界，不是 SOL-02 Owner 或 Gate 3 PASS。

```text
当前 Phase：Phase 2，依 CR-SEQ-001 前置 Solution 独立 Owner
当前 WBS：SOL-02-A02
输入基线：冻结 DM-05/SC-01/02、API-04、CR-SOL-011/DEC-20261009-1123
前置任务：0136/0137 结构与 A01 前置核查 PASS
涉及模块：solution ORM/Alembic；不改其他业务模块
涉及实体：SolutionOutlineCreateResult，引用 SolutionOutline
涉及 API：无；SOL_OUTLINE_CREATE 运行路由仍未装配
涉及权限：无新权限；目录根和快照仍拒绝任何 DML
验收标准：ORM/迁移同构、空/有数据升降级、drift、FK/约束/历史拒降、全量后端回归
风险：快照被误作正式版本、无 Owner 时提前开放根写入、已有历史丢失
```

Changed：新增迁移 0145、ORM 快照行和一次性 PostgreSQL 验证脚本；更新迁移 Head/ORM 目录断言。Migration：升级/降级/重升和有历史拒降通过。API/配置/依赖：无。Tests：隔离 PG18.6 脚本退出 0，三次 Alembic check 无增量；后端全量 `3356 passed, 3 skipped, 4990 subtests passed`。第一次数据库脚本仅把自动主键约束名误写为 `_pkey`，改为实际 `pk_sol_outline_create_results` 后全流程重跑通过；第一次后端回归的两项失败是新增 Head/表未更新静态目录断言，补上后定向 7 及全量回归通过。

兼容性/升级：旧 API/权限/写保护不变，0144→0145 线性升级；0145 表为空可降级，已有快照拒降。回滚须保留已有历史，不能执行破坏性数据删除。A03 内部 Owner 与有界 Guard 解锁须同一完成单元；A04/A05 再验证 HTTP/Windows 组合。正式 License/目标账户、Server2025、20 并发、POC-03 质量、Gate3/UAT/发行仍待，Debian13 实机按用户指令暂跳过。

TraceLink：SOL-02-A01 → CR-SOL-011 → 0145/本项 → SOL-02-A03。
