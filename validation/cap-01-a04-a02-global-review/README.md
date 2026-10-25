# CAP-01-A04-A02 GLOBAL Review 内核验证

在一次性 PostgreSQL 18 数据库升级至当前 head，使用 Review 自有 GLOBAL repository 和同事务 persistence service 验证：GLOBAL 创建与开轮、两名 reviewer 完整决策、APPROVED、独立 WITHDRAWN、不可变事件、主题锁释放、DEPLOYMENT Audit 及零 PROJECT 污染。

本夹具的 `BoundSyntheticOwner` 只证明 A02 Review 内核会强制调用并绑定 Subject Port；它不是 Capability 生产 Owner，也不作为 Capability 正式化证据。A03 必须接真实 Capability Version/来源/权限锁，A04 才能验证正式指针。

```powershell
$env:PYTHONPATH='apps/backend/src'
& '.poc-runtime/poc-01/windows-online/Scripts/python.exe' `
  'validation/cap-01-a04-a02-global-review/verify.py'
```
