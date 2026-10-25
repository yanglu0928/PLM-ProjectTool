# REQ-01-A10-A04-P02 Requirement HTTP 验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a10-a04-p02-requirement-http/verify.py
```

覆盖七个冻结 HTTP Operation、Requirement 专用 cursor、最小投影、强 ETag、PATCH 零 receipt、
DEFER/REJECT 决定 Evidence、三类状态命令重放、角色/License 拒绝、Audit 与 Alembic drift。
