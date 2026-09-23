# Core Entity / Data Model Freeze 执行计划

## 状态

`IN_PROGRESS / DM-01_PASS / DM-02_PASS / DM-03_PASS / DM-04_PASS / DM-05_PASS / DM-06_NEXT / NOT_GATE_2_FROZEN`

## 前置条件

- Phase 0 Gate 1：`APPROVED`。
- Architecture Freeze Candidate：`ARCH-CANDIDATE-V1 / AF-01～AF-05 PASS`。
- 正式业务编码继续由 Gate 2 阻塞。

## 输入

1. 《PLM项目实施辅助工具软件开发实施方案 V2.1》第六部分。
2. `docs/architecture/architecture-freeze-candidate-v1.md`。
3. AF-01～AF-03 详细候选与 ADR-001～ADR-009。
4. Phase 0 例外、Review/Trace/版本化和 ProjectId 强制约束。

## DM-01～DM-06

|WBS|目标|交付物|完成判定|
|---|---|---|---|
|DM-01|建立核心实体与聚合目录|实体、Owner、Scope、Aggregate Root、正式/建议态分类|PASS；见 `core-entity-aggregate-catalog-v1-candidate.md`|
|DM-02|冻结平台与安全模型|Project/User/Session/Role、Workflow、Review、Audit、Secret、License|PASS；见 `platform-security-model-v1-candidate.md`|
|DM-03|冻结 Document/Evidence/Trace/版本模型|文件、版本、解析、证据定位、TraceLink|PASS；见 `document-evidence-trace-model-v1-candidate.md`|
|DM-04|冻结 AI/RAG/Job/Plugin/Output 模型|Prompt/Invocation、Index/Chunk、Job/Lease、Plugin、OutputArtifact|PASS；见 `ai-rag-job-plugin-output-model-v1-candidate.md`|
|DM-05|冻结实施业务域模型|Capability、Handover、Survey、Requirement、Prototype、Solution、Plan|PASS；见 `implementation-domain-model-v1-candidate.md`|
|DM-06|生成 Data Model Candidate|关系、基数、生命周期、不变量、删除/保留策略和风险清单|无未登记模型分歧，进入 Database Schema V1|

## Data Model 与 Schema 边界

Data Model Freeze 定义业务实体、聚合、身份、关系、基数、生命周期、不变量、Scope 和版本语义；本阶段不固定 PostgreSQL 表名、列类型、索引、约束名称或 Alembic Migration。物理实现进入 Database Schema V1。

## 共同约束

- PROJECT 实体必须有可验证的 ProjectId 归属；GLOBAL 实体显式声明 Scope。
- 正式对象、文件和 Review 历史不可覆盖；修改创建新版本或追加记录。
- AI 建议与正式业务事实使用不同状态/对象语义，不允许单字段静默晋升。
- 所有正式 Requirement、Prototype、Solution、Plan 与关键附件必须可通过 TraceLink 反查来源。
- 跨聚合只引用稳定 ID/Version，不持有其他模块 ORM 对象。
- 删除、归档、保留与审计语义必须显式；普通用户不能删除 Audit。
- Data Model 候选不得被当作已存在数据库或已验证 Migration。

## 下一输出

DM-06 汇总 Data Model Candidate，统一关系、基数、生命周期、删除/保留策略和风险清单；完成后进入 Database Schema V1 候选设计。
