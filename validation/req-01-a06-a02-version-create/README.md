# REQ-01-A06-A02 RequirementVersion 原子创建验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a06-a02-version-create/verify.py
```

覆盖Migration0119空库升降重升、drift、真实Session/角色/License、PROJECT Evidence来源proof、initial与
显式base、Root ETag、幂等、并发、Audit回滚、跨项目Evidence、无结果Root/Version直写拒绝和历史拒降。
