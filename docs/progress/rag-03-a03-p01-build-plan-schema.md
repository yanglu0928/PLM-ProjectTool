# RAG-03-A03-P01 Embedding Build 计划 Schema

日期：2026-10-04；状态：`RAG_EMBEDDING_BUILD_PLAN_SCHEMA_PASS`；当前 Phase：Phase 2 Platform Core。下一项：`RAG-03-A03-P02` 受权 Build 创建/claim、唯一 Owner 与 PLANNED→BUILDING 原子推进。

## 完成范围

1. Schema0079/ORM 新增 Build 根和 Batch；每个 Index/Job 最多一个 Build，首版每个 Index 只有 generation=1，失败重建必须创建新 Index。
2. Job 必须为 `owner_module=rag`、`job_type=RAG_INDEX_BUILD`、PENDING、`max_attempts=1`，并以精确Build/Index/generation三字段payload refs绑定。
3. Batch在同一事务内连续覆盖1..source_chunk_count，每批最多1000条；提交时按固定IndexSourceChunk复算source fingerprint。
4. 每个Batch独占一次授权；授权必须为INDEX_BUILD/INDEX_REBUILD且Scope/Project/Model、类别、限额、source/payload fingerprint精确一致，`max_retry_attempts=1`。
5. 授权集合fingerprint与Build fingerprint在提交时复算；Build/Batch创建后暂时完全封存，P02 Owner安装前不允许状态转换。
6. 不开放HTTP、不创建实际生产Job、不进行Provider调用；没有消息队列、Runtime DDL或跨项目复用。

## 验证证据

|检查|结果|
|---|---|
|Schema/迁移定向|24项通过（含0076～0078、ORM与迁移链回归）|
|后端全量|2366项通过，3项条件跳过|
|PostgreSQL 18.6|`RAG_03_A03_P01_BUILD_PLAN_SCHEMA_PASS`|
|迁移场景|空库升/降/重升；已有Index升级；有Build/Batch历史拒降|
|正向|2个Batch连续覆盖2个Chunk；2次独立授权、Job Owner、授权集/Build指纹提交通过|
|负例|Build/Batch状态推进与TRUNCATE拒绝；Guard/定向合同覆盖缺批次、来源、授权限额/类别/指纹和Job绑定|
|ORM drift|`command.check`无新操作；继承Schema0078已记录的HNSW operator-class比较提示|
|wheel|隔离导入和定向24项通过；SHA-256 `94d7bddb4b89811f3e630d91c1e8d1360281d32d8dfc3420423ffe716d91c535`|

首轮Migration实库编译发现`authorization`在该SQL位置被PostgreSQL解析为关键字，迁移事务回滚且验证库清理；改用`authz`别名后在全新库完整重跑通过，未产生生产迁移或残留数据。

本项只使用合成数据和一次性数据库。它不证明实际创建服务、Worker claim、发送栅栏、Embedding响应、READY/ACTIVE、性能、三平台、Gate3质量、UAT或正式发行包。
