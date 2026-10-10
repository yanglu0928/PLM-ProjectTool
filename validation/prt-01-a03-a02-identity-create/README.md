# PRT-01-A03-A02 identity create Owner 验证

Windows 11 / PostgreSQL 18.6：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/prt-01-a03-a02-identity-create/verify.py
```

验证 Migration0123 空历史升降/重升与 drift、真实 Session/CSRF、Project角色、License、Package和
Prototype创建、持久幂等重放/冲突、Audit故障回滚、Root与不可变首结果提交闭包、历史拒降。全部为隔离
临时库中的合成元数据，不开放HTTP或创建正式PrototypeVersion。
