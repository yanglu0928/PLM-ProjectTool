# REQ-01-A03-P03-P02 Requirement mutation 验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a03-p03-p02-requirement-mutation/verify.py
```

覆盖 Migration0115 空历史升降/重升与 drift，真实 Session/CSRF、角色、License、PATCH、
DEFER/REJECT 当前同项目 ELIGIBLE Evidence、ARCHIVE、持久首结果、并发ETag、Audit回滚、
数据库提交闭包、伪造快照、撤权重放拒绝和有历史降级拒绝。
