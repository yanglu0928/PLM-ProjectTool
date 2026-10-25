# WFL-02-A02-A05 Windows HTTP/PostgreSQL 验证

在仓库根目录执行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime\poc-01\windows-online\Scripts\python.exe' `
  'validation/wfl-02-a02-a05-windows-http-pg/verify.py'
```

验证脚本复用 Handover 当前事实夹具，在独立临时数据库中创建完整事实、记录两个
Checklist PASS，并通过 Windows 显式写组合的真实 HTTP 边界执行
`HANDOVER -> SURVEY`。脚本断言默认关闭、Origin/Session/CSRF/If-Match、拒绝客户端
提供 Gate、最小响应与强 ETag、精确幂等回放，以及 PostgreSQL 中唯一 Transition、
两个 Gate、Audit 和完成回执；临时数据库与文件在退出时清理。
