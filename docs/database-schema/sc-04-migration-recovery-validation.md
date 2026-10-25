# SC-04：Migration 与恢复验证报告

## 状态

`SC-04_PASS / VALIDATION_ONLY / WINDOWS_11_VALIDATED / SC-05_NEXT / NOT_GATE_2_FROZEN / NOT_PRODUCTION_SCHEMA`

本报告验证 SC-01～SC-03 的 PostgreSQL 18/Alembic 机制。工作区位于 `validation/sc-04-database-schema`，是 Gate 2 前的验证性 Schema Contract，不是正式生产 Migration，也不授权业务模块编码。

## 环境

|项目|结果|
|---|---|
|平台|Windows 11 x86-64|
|Python|3.13.15|
|PostgreSQL|18.6，本地隔离端口运行|
|pgvector|0.8.6|
|SQLAlchemy / Alembic / psycopg|2.0.54 / 1.20.0 / 3.3.5|
|外部网络调用|0|
|客户资料|未使用|

Windows Server 2025 已有 POC-02 PostgreSQL/pgvector/Alembic/备份恢复证据，但本轮 SC-04 工作区未在 Server 重跑；Debian 13 按用户决定继续跳过，不能形成 SC-04 实机结论。

## 交付物

|交付物|作用|
|---|---|
|`schema_manifest.py`|65 个 Root ID、primary table、PK、Profile 与 20 个 Query ID 的机器可读清单|
|`schema_contract.py`|SQLAlchemy 结构契约；关键域使用代表字段/约束，其余 Root 使用 Profile 最小结构|
|Migration 0001|创建 `plm` Schema、pgvector 与 65 个 Root primary table/代表 child table|
|Migration 0002|创建代表性 B-tree/partial unique/GIN/HNSW 和 append-only trigger|
|`validate_sc04.py`|空库/有数据、负向约束、计划、并发、Retention、备份恢复和敏感列检查|
|Windows 运行脚本|复用离线 Python 3.13 与 PostgreSQL 18.6，不下载依赖|
|`evidence/windows-11/result.json`|结构化验证证据|

## 验证结果

|验证项|结果|证据摘要|
|---|---|---|
|Manifest 单元测试|PASS|4/4；Root/Query/标识符/敏感列|
|Root 覆盖|PASS|65/65 唯一 Root ID、表名和 primary table|
|SQLAlchemy metadata|PASS|70 张表；65 Root + 5 个代表 child/owned table|
|标识符|PASS|217 个受检名称，全部 ASCII lower_snake_case 且 ≤63 bytes|
|空库 upgrade|PASS|Alembic `base → 0002`；65 Root；pgvector 0.8.6|
|空库 downgrade|PASS|`0002 → base` 后 Root 表 0|
|有数据 upgrade/down|PASS|测试 Document 在 `0001 ↔ 0002` 保留；base 清理完成|
|代表索引|PASS|81 个 PK/unique/代表 secondary index；0002 down 后 secondary index 移除|
|数据库负向约束|PASS|10/10 拒绝|
|关键计划|PASS|Job claim、Audit timeline、FTS GIN、HNSW 物理探针命中预期索引|
|Job 并发|PASS|20 Worker 使用 `SKIP LOCKED`，20 个唯一 Job，无重复领取|
|Retention/File Recovery|PASS|1 个到期 STAGED 候选；1 个 Active Hold 对象被阻断|
|备份恢复|PASS|custom dump 非空（本轮 807,325 bytes）；恢复后 65 Root、测试 Document 完整|
|敏感字段扫描|PASS|禁止明文列名 0；Secret-like 源码值 0|

## 10 个数据库拒绝场景

|场景|SQLSTATE / 结果|
|---|---|
|PROJECT 缺 ProjectId|23514 CHECK violation|
|DocumentVersion 跨项目引用|23503 FK violation|
|同 Review 第二个 IN_REVIEW Round|23505 unique violation|
|向量维度与 Index dimension 不一致|23514 CHECK violation|
|修改 append-only AuditEvent|55000 object_not_in_prerequisite_state|
|WBS dependency 跨项目|23503 FK violation|
|重复规范化用户名|23505 unique violation|
|重复 Job idempotency key|23505 unique violation|
|同 Job 第二个 Active Lease|23505 unique violation|
|同 Index/Chunk 第二个 AVAILABLE Embedding|23505 unique violation|

## 查询计划结论

- Q-JOB-01 命中 `ix_job_jobs__claim`。
- Q-AUD-01 命中 `ix_aud_events__project_time`。
- Q-RAG-01 FTS 命中 `ix_rag_chunks__search_gin`。
- 1,001 条向量的 HNSW 物理探针命中 `ix_rag_embed__v32_hnsw`，Top-5 与 exact 对照 Recall 100%。
- 带单一 Project/EmbeddingIndex 强过滤的授权向量查询由 planner 选择 `uq_rag_embeddings__index_chunk_available` 后精确排序。这是 SC-03 已定义的 `EXACT_FILTERED_FALLBACK`，在小候选集上优于强制 HNSW；未通过关闭 planner 能力伪造生产计划。
- 本轮只验证计划可用性，不声明正式 P95。POC-02 的 100k/HNSW 性能证据保持独立，正式维度、多租户偏斜和写放大仍须后续性能环境复验。

## Migration 与恢复边界

1. `plm.alembic_version` 位于应用 Schema；Alembic online 环境先幂等创建 Schema，down to base 保留空 Schema/version table。
2. 0001 验证 Root/Profile、Scope/ProjectId、复合 FK、CHECK 和 pgvector；0002 验证索引/trigger 可独立回退。
3. Append-only trigger 对 Audit/Trace 代表表验证成功；生产版本仍须按最终表清单逐表生成，不使用任意动态 SQL trigger。
4. `pg_dump -Fc`/`pg_restore` 在临时数据库验证，测试数据库和临时 dump 在运行结束后删除；只提交脱敏 JSON 结果。
5. Migration 当前复用固定 `schema_contract.metadata`，仅适合候选验证。正式开发 Migration 必须冻结 revision 内容、进行人工 review，并与最终 ORM/manifest 漂移测试绑定。

## 已知限制与后续关闭

|限制|影响|关闭位置|
|---|---|---|
|非关键 Root 只有 Profile 最小列|不能当作完整生产列清单|SC-05 汇总 + Gate 2 后正式模块 Migration|
|只创建 5 个代表 child/owned table|Owned table 全量 DDL 尚未冻结|SC-05 index/table manifest|
|SC-04 只在 Windows 11 重跑|Server/Debian 无本轮结果|Server 继承 POC-02 可行性；Debian 为 Release 约束|
|HNSW 本轮仅 1,001 条/32 维|不能替代正式维度和 100k 性能|后续性能验证，继承 POC-02 基线|
|无 API/Repository 权限链|未验证“无 RLS”下应用过滤|API Contract/Permission 集成测试|
|文件恢复只验证元数据候选/Hold|未操作客户文件正文|文件模块集成与恢复测试|

以上限制不阻塞 Schema 机制候选，但禁止把 SC-04 结果描述成“完整生产数据库已实现”。

## SC-04 验收

- 65 个 Root primary table 与 Profile manifest 可执行，Root 覆盖无遗漏/重复：PASS。
- SQLAlchemy 结构契约与两级 Alembic Migration 已建立且明确 `VALIDATION_ONLY`：PASS。
- 空库 upgrade/downgrade 与有数据 upgrade/downgrade 均通过：PASS。
- 10 个直接 SQL 负向约束全部失败关闭：PASS。
- SC-03 的 Job、Audit、GIN 和 HNSW 代表索引具备实际执行计划证据：PASS。
- 小候选授权向量查询正确走 exact filtered fallback，HNSW 物理路径和 Recall 单独通过：PASS。
- 20 Worker `SKIP LOCKED` 唯一领取验证通过：PASS。
- Retention 到期发现、Active Hold 阻断与 STAGED File 候选验证通过：PASS。
- `pg_dump`/`pg_restore` 后 65 Root 和有数据记录完整：PASS。
- 标识符、敏感字段与 Secret-like 内容扫描通过：PASS。
- Windows 11 验证范围、Server 既有证据和 Debian 未验证边界已明确：PASS。
- 未开发 API/业务功能，正式编码仍由 Gate 2 阻塞：PASS。

## 下一步

SC-05：汇总 SC-01～SC-04，形成单一 `DB-SCHEMA-CANDIDATE-V1`，统一表/列/Profile/约束/索引/Migration 边界、验证证据、未关闭风险和 API Contract 输入。
