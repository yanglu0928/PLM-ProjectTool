# PRT-01-A03-A05 NOT_REQUIRED scope decision Owner 验证

Windows 11 / PostgreSQL 18.6：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/prt-01-a03-a05-scope-decision/verify.py
```

验证Migration0126空历史升降/重升与drift、PM/CustomerManager权限、当前Approved RequirementVersion固定
集合、可选Approved Review内容指纹、无Review决定、强ETag、持久重放、Audit回滚、Root/决定/引用/结果提交
闭包、归档后历史重放和历史拒降。Requirement/Review上游事实均为隔离临时库合成验证数据，不冒充客户确认。
