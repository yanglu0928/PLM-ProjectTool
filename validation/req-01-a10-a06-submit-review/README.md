# REQ-01-A10-A06 RequirementVersion 原子送审验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a10-a06-submit-review/verify.py
```

覆盖固定 `REQ-03 + REQUIREMENT_ALL_V1`、当前来源重验、Review create/start/Requirement绑定/
receipt/Audit同事务、HTTP持久幂等回放与冲突、ProjectManager权限、License拒绝及Alembic drift。
