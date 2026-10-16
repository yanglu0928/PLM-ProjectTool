# CAP-01-A02 Schema0091 验证

在 Windows 11 / PostgreSQL 18.6 隔离临时库执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/cap-01-a02-capability-schema/verify.py
```

验证空库与已有平台数据升级、空 Capability 历史降级/重升、Alembic drift、两 Root/五表 GLOBAL 形状、固定 DocumentVersion 集合摘要、每项 Document/Evidence 完整绑定、Owner 未安装时状态关闭，以及已有 Capability 历史拒绝物理降级。全部夹具为合成元数据，不读取标准能力库正文，不外发数据，不创建 APPROVED 版本。
