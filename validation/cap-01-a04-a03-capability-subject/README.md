# CAP-01-A04-A03 Capability Review Subject 验证

在一次性 PostgreSQL 18 数据库中创建真实 Capability Baseline/DRAFT Version，并用 Auth、Document、Evidence 与 Capability Repository 的生产 Port 验证：失效 Evidence 整事务拒绝且不残留 Review；恢复后绑定 GLOBAL Review/首轮并把 Version 持久化为 IN_REVIEW；Active Review 阻止替换 Draft；非终态 reviewer 决策通过；禁用 reviewer 被拒；A04 正式化 Owner 未安装前终态整事务回滚。

本项不挂 HTTP，也不创建 APPROVED 或正式指针。外层 Session/CSRF/License/幂等命令和终态正式化留给 A04-A04。

```powershell
$env:PYTHONPATH='apps/backend/src'
& '.poc-runtime/poc-01/windows-online/Scripts/python.exe' `
  'validation/cap-01-a04-a03-capability-subject/verify.py'
```
