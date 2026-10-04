# RAG-04-A03-P02 Retrieval Claim Validation

Windows 11 / PostgreSQL 18.6 合成验收，复用前置合成 ACTIVE Index 和 Retrieval 创建链，不作为真实业务质量或 Gate 3 证据。

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/rag-04-a03-p02-retrieval-claim/verify.py
```

验证范围：

- 通用、Parser、AI Task、RAG Index Build Worker 均不能认领 `rag/RAG_RETRIEVAL`。
- Retrieval 专属 Worker 只认领 PROJECT、单次 attempt/fencing、唯一 Run 引用 payload。
- 当前 claim 精确绑定 Job、Run、Project、Actor、Trace 与租约。
- 租约过期后通用和专属 claim 均不自动接管，Job/Run 保持原状，等待后续原子 Reconciler。
- 全程使用合成数据，无 Provider I/O、无客户数据外发。
