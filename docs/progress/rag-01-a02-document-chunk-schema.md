# RAG-01-A02 DocumentChunk / FTS Schema

日期：2026-10-04；状态：`RAG_DOCUMENT_CHUNK_SCHEMA_PASS`；当前 Phase：Phase 2 Platform Core。下一项：`RAG-02-A01` EmbeddingIndex 编码前核查与状态/模型维度边界设计。

## 完成范围

1. 新增模块化单体内部 `rag` ORM，`DocumentChunkRow` 只保存来源绑定、切分代次、定位、正文/指纹、元数据快照和受控状态，不保存向量或可变 Index 归属。
2. 新增 Alembic `20261004_0076`，前序为 `20261003_0075`；注册 ORM metadata，更新迁移头和表清单契约。
3. 数据库强制 PROJECT/GLOBAL Scope、DocumentVersion/ParseRecord/ParseResult 同源、成功结果与 hash、document category、正文 SHA-256、切分代次唯一、来源不可变和历史保留。
4. `search_vector` 使用生成列 `to_tsvector('simple', search_body)` 与 GIN；它是确定性全文候选，不替代后续中文 Embedding/Hybrid 质量验收。
5. 未新增公共 API、Embedding、Provider 调用、外发或依赖；业务模块仍不得直读 Chunk 表。

## 验证证据

|检查|结果|
|---|---|
|Schema 单元与迁移契约|10 项通过|
|后端全量|2352 项通过，3 项条件跳过|
|PostgreSQL 18.6|`RAG_01_A02_DOCUMENT_CHUNK_SCHEMA_PASS`|
|迁移场景|空库升/降/重升；已有 Document/Parse 数据升级；有 Chunk 拒降|
|负例|跨 Project、错误结果/hash、重复 generation/ordinal、来源改写、非法状态、DELETE/TRUNCATE 均拒绝|
|全文检索|`simple` FTS 命中合成中文标记，执行计划使用 GIN|
|ORM drift|Migration0076 与 metadata 一致|
|wheel|827 项；SHA-256 `fed28e9a2409d58ec4d469886e8ec62759e1a905dedde8ed0617f8fdc7f239e0`|

验证只使用合成数据和一次性数据库，结束后清理；无真实 Provider I/O、客户数据或 Secret。首次历史库夹具试图在清除 Document effective version 前限制版本，被既有 Document 守卫正确拒绝；调整验证操作顺序后以全新数据库重跑通过，生产守卫未放宽。

## 兼容与待项

- 正式冻结提交 `64cdf09` 保留，增量由 `CR-RAG-001` 和 `DEC-20261004-788` 追溯。
- 空表允许降回 0075；有历史时拒绝物理降级。
- Windows Server 2025、Debian 13、RAG Build/检索运行、分类/引用质量和 Gate 3 均未由本项证明。
