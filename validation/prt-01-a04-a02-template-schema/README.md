# PRT-01-A04-A02 validation

在 Windows 11 本机 PostgreSQL 18.6 的一次性数据库执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
& '.poc-runtime/poc-01/windows-online/Scripts/python.exe' `
  'validation/prt-01-a04-a02-template-schema/verify.py'
```

验收标志：`PRT_01_A04_A02_TEMPLATE_SCHEMA_PASS`。脚本验证0126有数据升级、0127空历史
降级/重升、Alembic drift、Owner关闭、Scope/合同约束、TRUNCATE拒绝和有历史拒降；使用合成
用户、项目和模板数据，结束时删除临时数据库，不触碰正式库。
