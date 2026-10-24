# RAG-04-A05-P01 Retrieval Terminal Schema Validation

Windows 11 / PostgreSQL 18.6 合成验收；正向索引和文档均为隔离夹具，
不构成真实业务质量或 Gate 3 证据。

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe `
  validation/rag-04-a05-p01-retrieval-terminal-schema/verify.py
```

验证范围：

- Schema0088 已有库到 Schema0089 的升级、空历史降级/重升与 ORM drift。
- Candidate/FTS+FINAL Score、Run/Job/Attempt/Lease、最小 Context 成功同事务。
- 零候选普通失败与过期 generation 失败同事务，无候选/Context 残留。
- Candidate 单独提交、成功缺 Context、终态历史降级均失败关闭。
