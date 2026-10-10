# SOL-03-A04-P03-P03-P01：封闭的 OutlineVersion 首次创建结果结构

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P01_OUTLINE_RESULT_SCHEMA_PASS`；仅封闭 Schema，OutlineVersion CREATE 仍不可写。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A04-P03-P03-P01。
- 输入基线/前置：Gate2 DM-05/API-04、CR-SOL-002/017、`0137/0154` 封闭版本/引用结构和已验 Section/Requirement/Reference 现时证明。
- 单一问题：持久幂等重放须返回首次 201 DRAFT，而非从可能转入 Review 的版本行重建；需先有不可变首响结构，保持现有版本写 Guard 关闭。
- 模块/实体/API/权限：Solution ORM/Alembic，新增 `sol_outline_version_create_results`；无公开 API、角色或依赖变化。DDL 允许首响字段存储，但行级 INSERT/UPDATE/DELETE 与 TRUNCATE 全拒。
- 验收：空库与已有 Outline/Version 身份库升降重升、ORM drift、复合 FK/摘要/计数负例、封闭 DML、有历史拒降、后端全量。风险：此表结构不等于已经建立 Owner/Audit/Receipt；不能作为 CREATE PASS。

## 实施与验证

线性 `0154→0155` 新增首响表：以固定 OutlineVersionId 为 PK，复合 FK 绑定版本/Outline/Project，记录首次 DRAFT 的版本号、指纹、缺失/冲突声明、三类引用计数、前驱、创建人/时间；字段约束防止非法摘要/计数/声明，独立触发器在 Owner 未安装前全拒 DML/截断。既有 `0137/0154` Guard 不变。Win11 隔离 PostgreSQL 18.6 空库及合成既有身份库的 up/down/re-up、四轮 drift、直接写拒绝、FK/check 与历史拒降均退出 0。静态 ORM 清单第一次全量遗漏新表导致 1 失败，已补测试清单并重跑；最终后端全量 3437 通过/3 跳过/5243 子例，保留既有 2 条告警。

兼容/回滚：既有库仅新增空表，无历史回填；表空时可降回 0154，有结果行拒降，不删除历史。下一项 `SOL-03-A04-P03-P03-P02` 定义并测试 Owner 创建命令/有序集合/声明/首响合同，再单独实施 INSERT-only Guard 和真实 PG 原子写。Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-002/017 → 0137/0154 → 0155 → OutlineVersion Owner/Guard。
