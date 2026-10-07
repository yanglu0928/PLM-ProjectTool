# PRT-01-A02 Schema0122 验证

在 Windows 11 / PostgreSQL 18.6 隔离临时库执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/prt-01-a02-identity-scope-schema/verify.py
```

验证已有平台/Requirement数据升级、空Prototype历史降级/重升、Alembic drift、Package/Prototype身份、
同项目membership、固定RequirementVersion的NOT_REQUIRED受影响范围、Review引用成对约束、Owner关闭、
截断拒绝及存在历史时拒绝物理降级。全部夹具是合成元数据，不读取/外发项目资料，不创建正式Prototype、
客户确认或Approved业务事实。
