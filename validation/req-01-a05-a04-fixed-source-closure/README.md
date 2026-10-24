# REQ-01-A05-A04 五类固定来源闭环验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a05-a04-fixed-source-closure/verify.py
```

覆盖APPROVED SurveyConclusion、当前APPROVED Handover、不可变DEFER/REJECT人工决定、PROJECT/ELIGIBLE
Evidence和当前GLOBAL Capability在同一调用方事务中的proof；另覆盖人工决定首结果/Evidence集合错配、
跨项目、当前Evidence撤销与不可变决定历史的区别、零写及Alembic drift。
