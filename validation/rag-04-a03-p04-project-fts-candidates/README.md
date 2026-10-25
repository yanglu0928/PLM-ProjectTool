# RAG-04-A03-P04 PROJECT FTS Candidate Validation

Windows 11 / PostgreSQL 18.6 合成验收，复用前置合成 ACTIVE Index、受权 Query 准备与专属 claim，不作为真实业务质量或 Gate 3 证据。

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/rag-04-a03-p04-project-fts-candidates/verify.py
```

验证范围：

- `websearch_to_tsquery('simple', :query_text)` 参数绑定与 stored `simple` tsvector 一致。
- 固定 PROJECT/Index/Model/IndexSourceChunk/ACTIVE Chunk/AVAILABLE Embedding/DocumentVersion/Document 谓词。
- metadata 只映射 `document_category`、`source_type`、`document_version_ref`；任意、business/effective filter 继续关闭。
- `ts_rank_cd` 量化整数分数、source ordinal/ChunkId 稳定排序、`min(top_k*4,400)` 有界池。
- 计划不含正文/向量，A05 前 Candidate/Score 表保持空。
