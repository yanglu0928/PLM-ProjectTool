# REQ-01-A05-A02 Survey/Handover 固定来源证明验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a05-a02-upstream-source-proofs/verify.py
```

覆盖同项目 APPROVED SurveyConclusion、ACTIVE Handover 当前 APPROVED Version、精确 Review/Round/Snapshot
终态与内容指纹、调用方事务共享锁、跨项目/错版本/指纹漂移/受限 Root 拒绝、零写及 Alembic drift。
fixture 仅以管理员复制模式装载已经由各业务 Owner 单独验证过的终态物理形状，不替代业务审批链验收。
