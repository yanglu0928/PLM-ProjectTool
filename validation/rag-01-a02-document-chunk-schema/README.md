# RAG-01-A02 DocumentChunk Schema 验证

`verify.py` 在 Windows 11 的一次性 PostgreSQL 18 数据库中验证 Migration 0076：空库升降重升、已有 Document/ParseResult 升级、ORM drift、PROJECT Scope、来源/文本 Hash、代次唯一性、状态/历史保留、受控 `simple` FTS 与 GIN 执行计划。验证不创建 Embedding、不调用外部 Provider，也不使用客户资料。
