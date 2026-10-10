# REQ-01-A06-A03 RequirementVersion 授权读取验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a06-a03-version-read/verify.py
```

覆盖项目成员list/get、version_no keyset、完整有序固定快照、跨项目隐藏、License/Session拒绝、零写和drift。
