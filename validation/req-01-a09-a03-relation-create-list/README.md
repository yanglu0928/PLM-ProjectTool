# REQ-01-A09-A03 RequirementRelation create/list 验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a09-a03-relation-create-list/verify.py
```

覆盖真实Session/CSRF/License/项目角色、端点证明、对称归一化与自然幂等、稳定分页、分类型DAG、跨项目
隔离，以及两笔并发互补边在Project行锁下只能成功一笔。
