# SUR-02-A02 Survey Round 双表 Schema 验证

在 Windows 11 的 PostgreSQL 18 实例上验证 Migration `0107`：

- 非空库从 `0106` 升级并保留既有数据；
- 空表降级/重升以及 Alembic drift check；
- Round 只允许基于当前已批准问卷版本创建；
- `PLANNED -> OPEN -> CLOSED` 状态约束和强锁版本；
- OPEN Round 的 `PROJECT_RECORD` Evidence 快照可追加且不可修改/删除；
- 重复快照、非项目记录、关闭后追加及保留历史降级均被拒绝。

运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/poc-01/windows-online/Scripts/python.exe' `
  'validation/sur-02-a02-round-schema/verify.py'
```
