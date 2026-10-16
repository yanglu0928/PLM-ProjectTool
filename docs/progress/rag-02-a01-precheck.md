# RAG-02-A01 EmbeddingIndex 编码前核查

日期：2026-10-04；状态：`RAG_EMBEDDING_INDEX_PRECHECK_PASS`；当前 Phase：Phase 2 Platform Core。下一项：`RAG-02-A02` Index 身份/精确 Chunk 快照 ORM、Migration0077 与 PostgreSQL 18 验证。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase/WBS|Phase 2；本项只关闭 RAG-02 物理边界与实施顺序，不实现外部 Embedding、Build Worker 或 HTTP。|
|输入基线|ADR-004；冻结 DM-04 EmbeddingIndex；SC-01～03；API-03 Index 管理；CR-RAG-001/Schema0076。|
|前置事实|DocumentChunk 来源/Scope/FTS 已实证；AIModel 已固定 Provider/model key/revision/kind/dimension/state；AI Egress Schema 已预留 INDEX_BUILD/REBUILD。|
|主要缺口|无 `rag_embedding_indexes`、精确来源快照、EmbeddingRecord、验证结果、Build Job/Worker 或 Index API。|
|权限/API|GLOBAL 仅 DeploymentAdmin；PROJECT Create/Build/Activate/Retire 为 ProjectManager，PM/IM 可读。A02 不挂载路由。|
|外发|A02 不外发；后续 Build/重建若使用外部 Embedding，必须绑定当轮 INDEX_BUILD/REBUILD 授权，历史授权不可复用扩权。|
|质量边界|PLANNED/Schema 成功不等于 READY/ACTIVE，更不等于分类/引用质量通过。Gate 3 保持开放。|

## 决定与分解

1. Index 身份固定 `(scope, project_id, index_purpose, index_version)`，同 scope/project/purpose 最多一个 ACTIVE；GLOBAL 与 PROJECT 从存储到查询都不混合。
2. 每个 Index 绑定唯一 AIModel、Provider 语义身份和 dimension。A02 通过 AIModel FK + 数据库守卫验证 `EMBEDDING/AVAILABLE/dimension`；模型状态后续变化不改历史，但构建、激活和检索必须重新验证。
3. 采用逐 Chunk 精确快照，而非仅记录 DocumentVersion。成员必须与 Index Scope/Project 和 Chunk profile/version 一致；Index/成员不可删除或改写。
4. A02 创建的 Index 只能从 `PLANNED` 开始，数据库暂时拒绝状态更新。RAG-03 增加 EmbeddingRecord/Validation/Build Owner 后，再以新 Migration 替换守卫并开放 `PLANNED→BUILDING→READY/FAILED→ACTIVE→RETIRED`。
5. dimension 大于 2,000 在 V1 直接不兼容；1～2,000 仍不代表存在 HNSW。RAG-03 只为受控维度由 Migration 建索引族，未知维度不得在 Runtime 动态 DDL 或激活。
6. A02 不创建 Job/Egress/ActivationResult，不实现冻结 HTTP；后续顺序为 RAG-03 数据/构建闭环，再回到 RAG-02 激活与管理 API，避免可见但不可完成的入口。

本项已在 `CR-RAG-002` 先登记差异、风险、迁移/回滚和验证计划；无代码、Schema、依赖、客户数据或网络外发变化。
