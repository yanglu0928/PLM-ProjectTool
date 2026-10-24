# REQ-01-A10-A02 Requirement identity 读取验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a10-a02-identity-read/verify.py
```

覆盖 Package/Requirement 四个读取 Owner、`(updated_at,id)` 稳定 keyset、包成员顺序、
CustomerMember 权限、跨项目隐藏、License/Session 拒绝、零写入和 Alembic drift。
