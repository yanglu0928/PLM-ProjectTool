# REQ-01-A03-P01 身份创建 Owner 验证

Windows 11 / PostgreSQL 18.6：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a03-p01-identity-create/verify.py
```

验证 Migration0112 空历史升降/重升与 drift、真实 Session/CSRF、Project 角色、License、Package 与
Requirement 首次创建、持久幂等/并发重放、重复 code、Audit 故障全回滚、不可变首结果快照和历史拒降。
所有数据均为隔离临时库中的合成元数据。
