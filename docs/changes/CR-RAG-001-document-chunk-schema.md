# CR-RAG-001：生产 DocumentChunk 与受控全文检索增量

日期：2026-10-04；状态：`IMPLEMENTED_AND_WINDOWS11_PG18_VERIFIED`；WBS：`RAG-01-A02`。关联 Gate 2 冻结 ADR-004、DM-04、SC-03 与 API-03；原冻结提交 `64cdf09` 不改，数据库增量从 `20261003_0075` 前进至 `20261004_0076`。

## 差异与原因

冻结基线定义了 RAG-01 DocumentChunk、PROJECT/GLOBAL Scope、来源 DocumentVersion/ParseResult、内容指纹和全文检索能力，但生产仓库在 Gate 2 后尚无 RAG 表或 ORM。为进入 EmbeddingIndex/Build，实现首个只承载来源事实和全文投影的 `plm.rag_document_chunks`；不把 PoC 表、向量、模型或索引归属复制进 Chunk。

DocumentChunk 固定 DocumentVersion、成功 ParseRecord/ParseResult、切分 profile/version/ordinal、受控 locator、文档分类、正文 SHA-256、元数据快照和状态。数据库守卫要求 Scope/Project、来源关系、结果 hash、document category 与正文指纹完全一致；正文生成 `simple` tsvector 并建立 GIN。Chunk 来源不可改写，ACTIVE/RESTRICTED/REVOKED 使用封闭转换，DELETE/TRUNCATE 和有数据 downgrade 拒绝。

## 风险、兼容、迁移与回滚

- 风险：错误 Scope 或来源绑定会跨项目泄露；守卫在插入和状态恢复时重验 Document/Parse 来源及可用性，未知或漂移失败关闭。
- 中文检索：本增量只提供确定性的 `simple` token FTS 候选，不宣称中文语义质量；后续 Hybrid/Embedding/Reranker 不能据此跳过 Gate 3 质量复验。
- 兼容：只新增内部表、ORM 和 Migration，不增加公共 Chunk CRUD，不改变冻结 `/api/v1`、依赖或外发行为。
- 升级：停写、备份后执行 0076；已有 Document/Parse 数据无需回填，新 Chunk 由后续受权构建流程产生。
- 回滚：空表可 downgrade 至 0075；一旦存在 Chunk 历史，物理 downgrade 拒绝，采用停止新构建、限制/撤销 Chunk、向前修复或受控备份恢复。
- 过程偏差：实现草稿在本 CR 文件写入前已于本地工作树形成，但在提交、推送和生产集成前补齐了 CR、风险与验证记录；未有远端、生产库或外发变更。后续 RAG Schema 增量继续先登记再编码。

## 验证结果

Windows 11 上使用一次性 PostgreSQL 18.6 数据库完成：空库 0076 升/降/重升、已有 Document/成功 ParseResult 升级、ORM drift、Scope/来源/hash/generation 负例、`simple` FTS 与 GIN 执行计划、状态/历史保留和有数据拒降；标记 `RAG_01_A02_DOCUMENT_CHUNK_SCHEMA_PASS`，数据库已清理。

定向 10 项、后端全量 2352 项通过，3 项既有条件跳过。开发 wheel 含 827 项，SHA-256 `fed28e9a2409d58ec4d469886e8ec62759e1a905dedde8ed0617f8fdc7f239e0`，包含 RAG ORM 与 Migration0076。未创建 Embedding、未调用 Provider、未使用客户数据或 Secret。Windows Server 2025 和 Debian 13 本项尚未验证，不据 Win11 结果推定通过。
