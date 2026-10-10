# PRT-01-A03-A04 Prototype identity mutation Owner 验证

Windows 11 / PostgreSQL 18.6：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/prt-01-a03-a04-prototype-mutation/verify.py
```

验证Migration0125空历史升降/重升与drift、PATCH强ETag且无receipt、ARCHIVE单向终态与持久重放、
ProjectManager/ImplementationMember角色边界、Session/CSRF/License、Audit回滚、Root/不可变结果提交闭包、
归档不删除Package membership及历史拒降。全部数据是隔离临时库合成元数据；不开放HTTP或业务Version写入。
