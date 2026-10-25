# REQ-01-A08-A02-P01 Requirement Review 生命周期 Schema 验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a08-a02-p01-review-schema/verify.py
```

覆盖0120空库升降重升、Review开始/RETURNED/APPROVED与Root ETag不可变结果闭包、无结果直写拒绝、
截断拒绝、历史拒降和Alembic drift。
