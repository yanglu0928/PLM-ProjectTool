# REQ-01-A10-A07 RequirementRelation HTTP 验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a10-a07-relation-http/verify.py
```

覆盖四个冻结HTTP、Relation专用cursor、固定Version端点、规范对称边、DAG拒绝、终态强
`If-Match: "v0"`、持久幂等、角色/License拒绝、Audit、receipt及Alembic drift。
