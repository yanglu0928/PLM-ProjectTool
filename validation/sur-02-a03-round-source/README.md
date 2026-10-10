# SUR-02-A03 Round PROJECT_RECORD 来源与追加验证

在 Windows 11 / PostgreSQL 18 上验证：

- Evidence Owner 仅接受 ProjectManager / ImplementationMember；
- 来源必须是当前 ELIGIBLE、同项目且固定 `PROJECT_RECORD`；
- Evidence proof 与 Survey Round append 共用调用方事务；
- 固定 Question 必须属于 Round 的固定 SurveyVersion；
- Round 锁下分配连续 ordinal，回滚不留记录；
- proof 与 append 持有 Evidence / Round 锁直至调用方提交；
- CLOSED Round 拒绝继续追加。

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/poc-01/windows-online/Scripts/python.exe' `
  'validation/sur-02-a03-round-source/verify.py'
```
