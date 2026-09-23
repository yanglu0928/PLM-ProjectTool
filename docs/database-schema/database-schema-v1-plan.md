# Database Schema V1 执行计划

## 状态

`IN_PROGRESS / SC-01_PASS / SC-02_NEXT / NOT_GATE_2_FROZEN / NO_MIGRATION_YET`

本计划把 `DATA-MODEL-CANDIDATE-V1` 转换为 PostgreSQL 18 + pgvector 的物理 Schema 候选。SC-01～SC-05 只产出物理设计、约束、索引、Migration 方案与验证脚手架；在 Gate 2 前不实现正式业务功能。

## 前置条件

- Phase 0 Gate 1：`APPROVED`。
- Architecture：`ARCH-CANDIDATE-V1 / AF-01～AF-05 PASS`。
- Data Model：`DATA-MODEL-CANDIDATE-V1 / DM-01～DM-06 PASS`。
- PostgreSQL 18 + pgvector 的 Windows 11 可用性已通过 POC-02；Windows Server 2025 具备已验证范围，Debian 13 仍未实机验证。
- 正式业务编码继续由 Gate 2 阻塞。

## SC-01～SC-05

|WBS|目标|交付物|完成判定|
|---|---|---|---|
|SC-01|逻辑到物理映射|数据库/Schema/命名策略；65 个 Root 与 Owned Entity 表映射；引用和内容存储策略|PASS；见 `sc-01-logical-physical-map-v1-candidate.md`|
|SC-02|字段、类型与约束|PK/FK、Scope/ProjectId、Version、唯一、CHECK、不可变和多态引用约束|核心不变量均有数据库或 Application 双层保护|
|SC-03|索引与关键查询|pgvector/FTS、Job/Outbox、Audit/Trace、授权过滤、WBS 图和容量索引|关键查询具有索引与查询计划验证方案|
|SC-04|Migration 与恢复验证|Alembic 基线、up/down、空库、有数据升级、文件恢复、Retention/Cleanup 验证|升级/回退和恢复测试完整，失败关闭|
|SC-05|汇总 DB Schema Candidate|表/列/约束/索引/Migration/风险单一候选|形成 `DB-SCHEMA-CANDIDATE-V1`，进入 API Contract V1|

## 设计边界

- 单一 PostgreSQL 18 数据库；客户运行应用对象位于 `plm` Schema。
- Developer Workbench 使用独立数据库/部署，不创建在客户 `plm` Schema 中。
- 表名使用模块短前缀，明确 Owner；同一数据库 Schema 不等于共享写所有权。
- 文件正文、Plugin 工作区和生成制品继续位于受控本地文件系统；数据库只保存元数据、状态、Hash 和 Locator。
- 业务迁移只能通过 Alembic；禁止手工修改生产数据库。
- SC-01 不选择最终 PostgreSQL 类型、外键动作、CHECK、索引、分区或 pgvector 参数，分别在 SC-02/03 固化。

## 共同验证

- 每个 Root 恰好映射一个 primary table，数量保持 65。
- 每张表有唯一 Owner prefix，表名为 ASCII lower_snake_case 且不依赖中文/平台大小写。
- PROJECT/GLOBAL_OR_PROJECT 表明确 project_id 映射位置；Scope 不由 JSON 内隐字段代替。
- 逻辑身份与不可变 Version 使用不同 primary table；不得把 current pointer 当历史引用。
- 固定类型关系优先直接 FK；多态引用只用于 Review/Trace/Audit/Event 等确需跨模块的场景。
- Owned collection 只有在需要查询、唯一、顺序、独立状态或引用时拆表；大正文不塞入关系行。
- 所有物理清理和级联仍受 Data Model 的 Retention/Hold/保护引用约束。

## 下一输出

SC-02：为 SC-01 的表映射确定 PostgreSQL 18 字段类型、PK/FK、Scope/ProjectId、版本、唯一、CHECK、不可变与并发约束。
