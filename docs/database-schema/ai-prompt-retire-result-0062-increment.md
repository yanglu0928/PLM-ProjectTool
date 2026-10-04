# DB Schema 0062：Prompt 退役不可变首次结果

版本：0.1.0.dev0；日期：2026-10-02；来源：CR-AI-009、DEC-689；原 Gate2 冻结提交 `64cdf09` 保留。增量 Alembic `20261002_0062`，上游0061。

`plm.ai_prompt_retire_results` 保存退役首次 200 的 result UUID、Template、操作者、Audit、Trace、退役前 `DRAFT/ACTIVE` 与可空的旧活动版本、固定 `RETIRED`、期望和最终锁版本、UTC 接受时间/事务 ID；不复制 Prompt 正文或 Secret。模板 FK 必须存在；旧活动版本非空时经复合 FK 归属同一模板。形态约束限定 DRAFT→RETIRED 时旧版本为空、ACTIVE→RETIRED 时旧版本为正且存在，锁版本恰好加一；Audit 唯一。UPDATE/DELETE/TRUNCATE 触发器保护历史。

Migration up 建表/约束/历史保护；down 仅允许空表，锁表后检查非空立即拒绝。历史已写入时不可物理回退，需受控备份恢复或向前修复。此增量不启用退役命令或生产 API。

Win11 隔离 PostgreSQL 18：空库 head→0061→head、有 Prompt 版本历史库升0062、Alembic drift=0，DRAFT/ACTIVE 合法快照、跨模板旧版本 FK、畸形状态/空值/版本、重复 Audit、历史更新/删除/截断拒绝、非空表 down 拒绝均通过；随机库已清理。Server2025/Debian、正式生产迁移与 Gate3 未验。
