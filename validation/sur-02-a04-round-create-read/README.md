# SUR-02-A04 Round 创建与读取验证

Windows 11 / PostgreSQL 18 验证范围：

- 仅当前 APPROVED SurveyVersion 可创建 PLANNED Round；
- ProjectManager / ImplementationMember 可创建，其他角色拒绝；
- Session、CSRF、License、Audit 与持久幂等同事务；
- 同 Survey 的 `round_no` 在锁内连续分配，并发同 Key 只产生一次；
- Audit 故障整笔回滚并可用同 Key 恢复；
- 所有项目成员可稳定分页读取，详情返回固定来源最小快照；
- 跨项目、撤权和错误标识失败关闭。

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/poc-01/windows-online/Scripts/python.exe' `
  'validation/sur-02-a04-round-create-read/verify.py'
```
