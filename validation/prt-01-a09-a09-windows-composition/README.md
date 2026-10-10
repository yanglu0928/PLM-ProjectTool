# PRT-01-A09-A09 Windows 生产组合验收

在 Windows 11 的隔离 PostgreSQL 18 数据库上验证 Prototype 默认关闭、显式只读/写组合、独立游标密钥、统一 `PRT-03` Review 注册，以及真实 Session/CSRF/License/项目授权下的代表性读写闭环。

运行：

```powershell
$env:PYTHONPATH='apps/backend/src'
& .poc-runtime/poc-01/windows-online/Scripts/python.exe validation/prt-01-a09-a09-windows-composition/verify.py
```

脚本只创建并删除带随机后缀的临时数据库，不修改既有项目数据库。正向 License 为测试注入，不代表正式 License 信任材料验收。
