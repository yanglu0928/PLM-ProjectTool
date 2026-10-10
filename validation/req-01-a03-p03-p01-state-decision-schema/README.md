# REQ-01-A03-P03-P01 Requirement state decision Schema 验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a03-p03-p01-state-decision-schema/verify.py
```

覆盖 Migration0114 空历史升级、降级、重升与 drift，决策/证据组合归属约束、P01 Owner关闭、
TRUNCATE拒绝，以及管理性历史fixture下的降级拒绝。fixture仅用于验证降级护栏，不代表生产写入口。
