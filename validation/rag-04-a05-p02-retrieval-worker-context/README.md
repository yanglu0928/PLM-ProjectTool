# RAG-04-A05-P02 Retrieval Worker and Context Validation

Windows 11 / PostgreSQL 18.6 合成验收；索引、文档、查询和系统身份均为隔离夹具，
不构成正式业务质量、生产信任源或 Gate 3 证据。

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe `
  validation/rag-04-a05-p02-retrieval-worker-context/verify.py
```

验证范围：

- 一次性 Worker 完成 claim→当前事实→解密→FTS→merge→原子结果/终态/Audit。
- 零候选以固定错误码失败且不创建 Candidate/Context。
- 过期 generation 由专属 Reconciler 原子关闭，不重领。
- AI `RAG_CONTEXT` Owner 只按完整 bundle 身份和当前权限读取最小文本；撤权后失败关闭。
