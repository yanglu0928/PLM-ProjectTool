# RAG-03-A02 EmbeddingRecord / 受控 HNSW Schema

日期：2026-10-04；状态：`RAG_EMBEDDING_RECORD_SCHEMA_PASS`；当前 Phase：Phase 2 Platform Core。下一项：`RAG-03-A03` Build generation/批次/唯一 Owner 与 INDEX_BUILD/REBUILD 授权快照。

## 完成范围

1. 正式依赖新增 `pgvector==0.5.0`；服务端 extension 仍为 0.8.6，二者分别锁定。
2. Schema0078/ORM 新增不可变 `rag_embedding_records`，固定 Index/Chunk、模型/维度、Chunk正文指纹、vector及SHA-256、Provider request ref和Egress Authorization。
3. 通过复合外键把记录绑定到 Index 模型/维度和精确 source Chunk；Scope/Project 由数据库守卫与项目外键双重约束。
4. 只为768/1024建立 cosine HNSW表达式索引；未知维度不能落记录，Runtime不执行DDL。
5. 插入必须要求 Index 已由后续 Build Owner 推进到 BUILDING，且授权Scope/Project/Model/operation匹配。Schema0077当前仍拒绝Index状态更新，所以A02保持零可写生产路径。
6. UPDATE/DELETE/TRUNCATE均拒绝；空表可降0077，有记录历史拒绝物理降级。

## 验证证据

|检查|结果|
|---|---|
|Schema/迁移定向|20项通过（含0076/0077与ORM回归）|
|后端全量|2362项通过，3项条件跳过|
|PostgreSQL 18.6|`RAG_03_A02_EMBEDDING_RECORD_SCHEMA_PASS`|
|迁移场景|空库升/降/重升；已有Index升级；有EmbeddingRecord历史拒降|
|物理索引|768/1024 `vector_cosine_ops` HNSW目录定义与强制计划均命中|
|负例|PLANNED写入、维度不符、UPDATE/DELETE/TRUNCATE均拒绝|
|ORM drift|`command.check`无新操作；HNSW operator-class文本表达式产生Alembic不可比较提示，但改用命名表达式会产生真实remove/add误报，故保留文本表达式并以目录/执行计划独立验证|
|wheel|隔离导入确认`pgvector==0.5.0`元数据，定向20项通过；SHA-256 `6adfdd88423491bb4d44c4f95992e14602efc11e5455feb26acbc003fa5ab5ba`|

首次全量回归使用的既有PoC虚拟环境缺项目清单中已有的`pydantic-settings==2.15.0`，产生16个导入错误；补齐同版本后从头重跑2362项通过。首次wheel全目录命令未指定测试包顶层，导致相对导入和源码摘要夹具假失败；最终改为隔离wheel导入并运行本次20项合同，未把错误命令计作产品失败。

本项仅使用合成数据和一次性数据库，已清理。Python pgvector MIT材料尚待最终发行Notice复核；Windows Server 2025、Debian 13、Build/真实外发、READY/激活、性能、Gate3质量、UAT和正式发行包未由本项证明。
