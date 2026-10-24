# RAG-01-A01 生产 RAG 基础编码前核查

日期：2026-10-04；状态：`RAG_FOUNDATION_PRECHECK_PASS`；当前 Phase：Phase 2 Platform Core。下一项：`RAG-01-A02` DocumentChunk/全文检索 Schema 与隔离 PostgreSQL 18 迁移验证。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase|Phase 2；CR-SEQ-001 允许先完成不依赖正式业务 Owner 的 AI/RAG 平台基础，Gate 3 保持开放。|
|当前 WBS|`RAG-01-A01`，只核查冻结 RAG 模型、物理约束、API/权限、PoC 证据和现有实现差距。|
|输入基线|ADR-004；冻结 DM-04 的 RAG-01～04；SC-01～04 的 Q-RAG-01/02；API-03 RAG Index/Retrieval；POC-02/03 证据。|
|前置任务|PG18/pgvector、DocumentVersion/ParseResult、AI Provider/Embedding Model、Job/Audit基础可用；AI-05已完成。分类48%、引用74%的质量失败继续阻塞Gate 3，但不阻塞生产平台骨架。|
|涉及模块|新增模块化单体内部 `rag`；只通过 Document/AI/Job/Audit Application Port 协作，不从业务模块直写向量SQL。|
|涉及实体|RAG-01 DocumentChunk、RAG-02 EmbeddingIndex、RAG-03 EmbeddingRecord、RAG-04 RetrievalRun/ContextBundle；分任务实施。|
|涉及 API|本项无；后续保持冻结 global/project index 与 project retrieval-run 路径，Chunk/Embedding无公共CRUD。|
|涉及权限|GLOBAL仅DeploymentAdmin；PROJECT Index由PM写、PM/IM读；Retrieval由PM/IM/CM创建；每层强制Scope/ProjectId。|
|验收标准|形成现状差距、分解顺序、状态/Scope/模型维度/来源/外发边界；不把PoC脚本复制成生产模块；不虚报质量或Gate通过。|
|风险|跨项目泄露、旧向量复用、外发授权越界、动态DDL、PoC质量结果被误当生产质量、ParseResult/Chunk来源漂移。|

## 现状与差距

1. 生产后端当前没有 `rag` 模块、RAG ORM、Migration、RetrievalService 或冻结 RAG HTTP；数据库迁移头为 `20261003_0075`。Audit target 已预留 RAG-01～04，基础迁移已安装 pgvector 0.8.6。
2. Document 已提供不可变 DocumentVersion、成功 ParseRecord/ParseResultRef、受权结果读取和 Typed ContentLocator；RAG 必须消费这些公开 Port，不能读取 Parser 临时文件或把 PoC ChunkId 当生产事实。
3. AIModel 已支持 `EMBEDDING` 与强制 dimension；Provider/Secret/Egress和Worker基础存在，但生产 Embedding/Reranker调用、Index Build Job与授权快照尚未实现。
4. POC-03 证明 PG18.6 的 Project隔离、FTS、HNSW、Hybrid、换模全量重建、外部Rerank和异常合同可行；独立留出集只证明 Top-5 98% PASS，分类48%和引用74%仍FAIL。PoC代码/本地Artifacts不能直接成为生产服务或质量放行依据。
5. SC-03 的 `embedding_index_id/generation` 按冻结聚合关系解释为“Chunk generation 与通过 EmbeddingRecord 关联的 Index”，不在 Chunk 行复制可变 Index归属。Index/Chunk 多对一关联由 RAG-03 `(index_ref, chunk_ref)` 固定，防止同一Chunk正文被多处不一致保存。

## 实施分解

1. `RAG-01-A02`：只实现 RAG-01 DocumentChunk ORM/Migration、来源与Scope完整性、确定性generation、受控中文Token后的`simple` FTS/GIN；空库和有数据升降级验证。
2. `RAG-02`：EmbeddingIndex identity/state/source snapshot/模型维度与原子激活，不做Embedding网络调用。
3. `RAG-03`：EmbeddingRecord、固定受支持维度HNSW索引族、外发授权快照与Build Job/Worker；换模只能新generation全量重建。
4. `RAG-04`：受权 Hybrid候选、精确回退、Reranker策略、RetrievalRun/Result/Context持久化与冻结HTTP。
5. 后续再接 AI Content Plan；业务模块只能调用统一 RetrievalService。Gate 3 使用全新独立留出集复验，不能用旧50条或PoC已见集重新宣称独立PASS。

本项仅静态核查和WBS拆分，无程序、Schema、API、依赖、外发或客户数据变化。
