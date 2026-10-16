# REQ-01-A12-A03-A02 Requirement Workflow Scope PostgreSQL 验证

在 Windows 11 / PostgreSQL 18.6 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/prj05a05-p04-venv/Scripts/python.exe validation/req-01-a12-a03-a02-workflow-scope-pg/verify.py
```

覆盖Project范围栅栏、完整Requirement Root扫描、两个ACTIVE最新Approved Version、DEFER/ARCHIVED
决定闭合、规范顺序、空范围/未决Version/直接归档/决定版本漂移失败关闭、共享锁及Alembic drift。
