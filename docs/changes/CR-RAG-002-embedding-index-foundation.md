# CR-RAG-002：EmbeddingIndex 身份与精确来源快照

日期：2026-10-04；状态：`APPROVED_FOR_IMPLEMENTATION_BY_CONTINUOUS_AUTHORIZATION`；WBS：`RAG-02-A01～A02`。关联 Gate 2 冻结 ADR-004、DM-04、SC-01～03 与 API-03；原冻结提交 `64cdf09` 不改。

## 差异与方案

冻结基线要求 Index 固定 Scope/Project、purpose、Embedding Model/Dimension、Chunk Profile、source snapshot 和单调 version，并在构建校验后原子激活。生产仓库目前只有 DocumentChunk Schema0076，没有 Index 物理表。

实施增量将新增 `rag_embedding_indexes` 和精确 Chunk 成员快照。SC-01 的 `rag_index_source_versions` 是候选集合名，但仅记录 DocumentVersion 不能证明某次构建实际使用了哪些 Chunk；因此物理实现采用逐 Chunk 不可变成员表，同时每个成员仍可经 Chunk 反查固定 DocumentVersion/ParseResult。该细化不改变冻结 Aggregate、API 或 Scope 语义。

A02 只开放 `PLANNED` Index 的持久化基础：模型必须是当前 `AVAILABLE` 的 `EMBEDDING`，dimension 与 AIModel 完全一致且不超过 V1 pgvector 2,000 维；Index 与所有 Chunk Scope/Project、profile/version 必须一致。BUILDING/READY/ACTIVE/FAILED/RETIRED 状态字段会先存在，但数据库写守卫在 EmbeddingRecord、验证结果与构建 Owner 落地前拒绝转换，避免半实现路径被误用。

## 风险、兼容、迁移与回滚

- 风险：只固定 DocumentVersion 而不固定 Chunk 可在并发生成时改变构建输入；逐 Chunk 快照消除该漂移。
- 风险：AIModel 后续 SUSPENDED/RETIRED 不改写 Index 历史；创建、构建、激活和检索分别重验模型当前状态，失效时失败关闭。
- 维度：模型元数据可达 65,536，但 V1 pgvector HNSW 上限为 2,000；大于 2,000 的模型不能创建 Index。具体可激活 HNSW 维度必须由后续 Migration 明确支持，Runtime Role 不执行 DDL。
- 兼容：新增内部表，无公共 API、外发、Provider 调用或依赖变化；不引入本地模型或独立向量库。
- 迁移/回滚：停写、备份后升级；已有 Chunk 不自动建 Index。空表允许降级；一旦存在 Index/快照历史，物理降级拒绝，采用停止构建、向前修复或受控恢复。

## 验证计划

空库和有 DocumentChunk 历史的 PostgreSQL 18.6 升/降/重升；ORM drift；GLOBAL/PROJECT、模型 kind/state/dimension、purpose/version、Chunk Scope/profile、重复/跨 Index 成员、来源不可变和有数据拒降负例；确认未产生 Embedding、Job、Egress、Provider I/O。Windows Server 2025、Debian 13、HNSW/Build/激活与质量另行验证。
