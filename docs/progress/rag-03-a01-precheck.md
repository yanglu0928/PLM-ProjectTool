# RAG-03-A01 EmbeddingRecord/Build 编码前核查

日期：2026-10-04；状态：`RAG_EMBEDDING_RECORD_BUILD_PRECHECK_PASS`；当前 Phase：Phase 2 Platform Core。下一项：`RAG-03-A02` EmbeddingRecord ORM、Schema0078、768/1024 HNSW 与 PostgreSQL 18 验证。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase/WBS|Phase 2；本项只固定数据、依赖、受控维度与外发幂等边界，不开放 HTTP、不进行真实 Provider 外发。|
|输入基线|ADR-004；冻结 DM-04、SC-02～04、API-03；CR-RAG-002/Schema0077；既有 AI Egress/Job/Worker 安全模式。|
|现状|只有 PLANNED Index/精确 Chunk 快照；无 Python pgvector、EmbeddingRecord、构建 Owner/批次、验证结果或激活路径。|
|依赖|A02 锁定 `pgvector==0.5.0`；与服务端 extension 0.8.6 分开管理，MIT Notice 进入发行复核。|
|维度/HNSW|首版只支持已验证的 768/1024；Migration 预建表达式 HNSW，未知维度拒绝构建/激活，Runtime 不建 DDL。|
|数据状态|EmbeddingRecord 只保存校验成功向量；PLANNED Index 下禁止插入，A02 因而仍无可写生产路径。|
|外发|A03/A04 绑定当轮 INDEX_BUILD/REBUILD 授权；发送前提交 RUNNING 栅栏，未知结果禁止自动重发。|
|质量边界|Schema/HNSW 存在不等于 READY/ACTIVE、召回或引用质量通过；Gate 3 保持开放。|

## 任务分解

1. `RAG-03-A02`：依赖、EmbeddingRecord、复合来源/维度约束、不可变守卫及 768/1024 HNSW。
2. `RAG-03-A03`：Build generation/批次/唯一 Owner、INDEX_BUILD/REBUILD 外发授权快照及状态转换。
3. `RAG-03-A04`：统一 AIService 下的 Embedding Adapter/Worker、发送前栅栏、响应校验和未知结果收敛。
4. `RAG-03-A05`：完整性/HNSW/质量验证，READY 与唯一 ACTIVE 原子发布；之后返回 RAG-02 管理 API。

本项已先登记 `CR-RAG-003` 的差异、风险、迁移/回滚和验证计划。无代码、Schema、依赖、客户数据、Secret 或网络外发变化。
