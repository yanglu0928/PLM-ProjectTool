# REQ-01-A07 RequirementVersion 校验验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a07-version-validate/verify.py
```

覆盖有效标准功能报告、PENDING 失败报告、来源/Evidence/Capability 漂移、原 Key 历史重放、角色与
License 拒绝、幂等冲突、版本零状态变化和 Alembic drift。
