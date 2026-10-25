# RAG-04-A06-P02 Retrieval Cancellation Schema Validation

Windows 11 / PostgreSQL 18.6 隔离合成验收，不使用客户数据或外部 Provider。

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe `
  validation/rag-04-a06-p02-retrieval-cancellation-schema/verify.py
```

验证范围：

- Schema0089 已有数据升级、ORM drift、无取消历史降级与重升。
- PENDING Job 与 Run 在同一事务直接进入 CANCELLED，零 Lease/Attempt/结果。
- RUNNING Job 先进入 CANCEL_REQUESTED，再由当前 generation 同事务关闭 Lease/Attempt/Job/Run。
- 缺 Run 终态或 CANCELLED 下写结果的半事务被拒绝并完整回滚。
- 已有取消历史拒绝降级；原 Schema0089 成功/失败边界保持。
