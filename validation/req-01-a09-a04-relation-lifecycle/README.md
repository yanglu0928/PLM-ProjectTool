# REQ-01-A09-A04 RequirementRelation 生命周期验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a09-a04-relation-lifecycle/verify.py
```

覆盖撤销/替代权限与幂等、替代DAG排除旧边、复用既有ACTIVE replacement、不可逆终态、Audit、receipt
及Alembic drift。
