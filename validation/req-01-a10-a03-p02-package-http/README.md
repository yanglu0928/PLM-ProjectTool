# REQ-01-A10-A03-P02 RequirementPackage HTTP 验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a10-a03-p02-package-http/verify.py
```

覆盖六个冻结Package Operation、独立cursor、CustomerMember读取、强ETag、PATCH无receipt、
ADD/REMOVE重放、角色/License拒绝、Audit、数据库后验与Alembic drift。
