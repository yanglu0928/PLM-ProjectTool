# SOL-03-A04-P03-P03-P04-A01：OutlineVersion INSERT-only 数据库守卫

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P04_A01_OUTLINE_CREATE_GUARD_PASS`；仅数据库原子创建集合，业务 Owner/API 尚未接线。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本任务。输入：Gate2 冻结数据模型/API、CR-SOL-017、DEC-1141、0137/0154/0155 封闭结构与已验内部现时输入证明。
- 单一问题：允许一次事务写入 DRAFT 版本、有序固定关联和不可变首次结果，但事务结束时拒绝缺件/伪空历史，所有 UPDATE/DELETE/TRUNCATE 仍拒。
- 范围：Solution Alembic SQL Guard；无公开 API/角色/依赖变化，未接用户授权、License、收据、Audit。直接数据库写仍不是正式业务入口。
- 验收：空库与有身份库升降重升、drift、缺失结果与伪空拒绝、完整原子提交、历史不可变、有历史拒降及后端全量。

## 实施与验证

线性 `0155→0156` 重定义旧全拒行级 Guard，仅开放 INSERT。版本 INSERT 锁定同项目 ACTIVE Outline，并约束首版/前驱链、DRAFT 初态、至少一节、最多 500 Reference、对象数组声明与无来源时缺失声明；三类关联均受声明计数上界和原复合 FK/唯一顺序约束。首响 INSERT 必须逐字段匹配版本。延迟约束触发器在事务结束核验三类关联的数量/连续顺序和首响存在；任何缺件回滚整个事务。历史 DML 与 TRUNCATE 仍拒。

Win11 一次性 PostgreSQL 18.6：空库和已有项目/目录/节身份库升降重升、Alembic drift、单独版本缺件回滚、伪空拒绝、同事务版本+节+首响提交、UPDATE/DELETE/TRUNCATE 拒绝、有历史拒降退出 0。后端全量 3446 通过/3 跳过/5256 子例，保留已有告警。此验证只覆盖本任务 SQL 集合，不等于 Owner 对真实来源、项目角色、License、并发收据或 Audit 的验收。

兼容/回滚：无旧行迁移；`0156` 前发现已有版本/首响行会拒升并要求审计。未写入历史时可降回 `0155` 恢复全拒，有历史时拒降，需前向修复；不得删除历史。下一项 `P04-A02` 接同事务 Owner/授权/License/收据/Audit，之后双 Scope PG、HTTP、Windows、UI。Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-002/017 → DEC-1141 → 0137/0154/0155 → 0156 → OutlineVersion Owner。
