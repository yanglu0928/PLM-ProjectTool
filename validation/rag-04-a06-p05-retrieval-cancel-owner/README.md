# RAG-04-A06-P05 Retrieval Cancel Owner Validation

Windows 11 / PostgreSQL 18.6 隔离合成验收，不使用客户数据或外部 Provider。

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe `
  validation/rag-04-a06-p05-retrieval-cancel-owner/verify.py
```

验证范围：

- Retrieval 冻结别名 HTTP 对 PENDING Job/Run 直接原子取消，精确重放不新增 Audit。
- 通用 Project Job cancel registry 对同一 `rag/RAG_RETRIEVAL` Owner 分派。
- RUNNING Job 先进入 `CANCEL_REQUESTED`，当前 Worker 再原子关闭 Lease/Attempt/Job/Run。
- Worker 未响应且 Lease 到期时，专属 Reconciler 以 `EXPIRED` 形态原子关闭。
- 两类终态均无 Candidate/Score/Context，且系统/用户 Audit 与幂等证据保留。
