# REQ-01-A03-P02 Package mutation 验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a03-p02-package-mutation/verify.py
```

覆盖 Migration0113 空历史升级、降级、重升与 drift，真实 Session/CSRF、项目角色、License、
Package 元数据修改、Requirement membership 增删、持久幂等首结果、版本并发、Audit 回滚、
伪造快照拒绝、移除 membership 不删除 Requirement，以及有历史降级拒绝。
