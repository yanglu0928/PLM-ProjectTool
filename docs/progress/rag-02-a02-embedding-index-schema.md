# RAG-02-A02 EmbeddingIndex / 精确来源快照 Schema

日期：2026-10-04；状态：`RAG_EMBEDDING_INDEX_SCHEMA_PASS`；当前 Phase：Phase 2 Platform Core。下一项：`RAG-03-A01` EmbeddingRecord、受控 HNSW 维度族与 Build Owner 编码前核查。

## 完成范围

1. 新增 Schema0077 与 ORM：`rag_embedding_indexes` 固定 Scope/Project、purpose/version、AIModel/dimension、Chunk profile 和来源快照摘要；`rag_index_source_chunks` 保存本次精确 Chunk 集合。
2. Index 仅能绑定当前 AVAILABLE 的 EMBEDDING Model，dimension 必须完全一致且在 V1 `1..2000`；PROJECT/GLOBAL 关系和 purpose/version 唯一由数据库约束。
3. Index 与成员必须在同一事务创建，成员 Scope/Project/profile/version/state/text fingerprint 与 Chunk 一致；提交时复算有序快照 SHA-256、count 和连续 ordinal。
4. 创建提交后成员封存；UPDATE/DELETE/TRUNCATE 全部拒绝。Index 暂时只允许 PLANNED，Build/Validation/Embedding 尚未安装时状态转换失败关闭。
5. 不新增公共 API、Job、EmbeddingRecord、HNSW、Egress、Provider 调用或依赖。

## 验证证据

|检查|结果|
|---|---|
|Schema/迁移定向|14 项通过（含0076回归）|
|后端全量|2356 项通过，3 项条件跳过|
|PostgreSQL 18.6|`RAG_02_A02_EMBEDDING_INDEX_SCHEMA_PASS`|
|迁移场景|空库升/降/重升；已有DocumentChunk/AIModel升级；有Index历史拒降|
|负例|缺成员、模型类型/状态/维度、跨Project、错误快照、重复purpose/version、迟到/改写成员、状态推进、DELETE/TRUNCATE均拒绝|
|ORM drift|Migration0077 与 metadata 一致；仅输出既有computed reflection警告|
|wheel|828 项；SHA-256 `4169d67bcca6e8271aed693a36f15f00e361440ca8048f3b1ac96fe22d53d9ee`|

验证只使用合成数据和一次性数据库，已清理。Windows Server 2025、Debian 13、Embedding/HNSW/Build/激活/API、性能和Gate3质量未由本项证明。
