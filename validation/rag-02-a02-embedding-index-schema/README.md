# RAG-02-A02 EmbeddingIndex Schema 验证

`verify.py` 在 Windows 11 的一次性 PostgreSQL 18 数据库中验证 Migration 0077：空库升降重升、已有 DocumentChunk/AIModel 升级、ORM drift、模型 kind/state/dimension、PROJECT Scope、逐 Chunk 精确快照、创建事务封存、版本唯一、状态关闭、历史保留与有数据拒降。验证不创建向量、不调用 Provider，也不使用客户资料。
