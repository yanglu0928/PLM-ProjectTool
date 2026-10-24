# REQ-01-A09-A02 RequirementRelation Schema 验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a09-a02-relation-schema/verify.py
```

覆盖0121空库升降重升、同项目组合FK、ACTIVE唯一边、对称端点顺序、不可变字段、REVOKED/SUPERSEDED
单向终态、删除/截断拒绝、历史拒降和Alembic drift。
