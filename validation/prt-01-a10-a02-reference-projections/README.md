# PRT-01-A10-A02 稳定引用与制品定位验证

在 Windows 11 / PostgreSQL 18.6 随机隔离数据库中依次验证：Requirement Version读取返回真实
AcceptanceCriterion稳定业务引用；PROJECT PrototypeTemplate与PrototypeVersion读取只在Document Owner
当前证明成功后返回`document_id + document_version_id`定位组合；跨项目、权限撤销、License、只读零写及
Alembic drift保持既有边界。每个子验证结束即销毁数据库。

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/prt-01-a10-a02-reference-projections/verify.py
```
