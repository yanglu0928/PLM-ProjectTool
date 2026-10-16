# REQ-01-A10-A05 RequirementVersion HTTP 验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a10-a05-version-http/verify.py
```

覆盖四个冻结普通 HTTP Operation、Version 专用 cursor、完整固定快照、root 强 ETag、
CREATE/VALIDATE 持久幂等、当前来源重验报告、角色/License 拒绝、Audit 与 Alembic drift。
