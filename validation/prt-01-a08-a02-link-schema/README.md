# PRT-01-A08-A02 validation

在 Windows 11 的隔离 PostgreSQL 18 数据库运行：

```powershell
$env:PYTHONPATH='apps/backend/src'
& '.tmp/req-p02-venv/Scripts/python.exe' `
  'validation/prt-01-a08-a02-link-schema/verify.py'
```

脚本只创建并销毁名称以 `prt01a08a02_` 开头的临时数据库。它验证0133→0134有数据升级、空表
降级/重升、Alembic drift、复合端点、Coverage/Purpose、ACTIVE唯一性、不可逆撤销/替换、
replacement闭包、删除/截断拒绝和有历史拒降。夹具使用合成UUID/文本，不含客户数据或Secret。
