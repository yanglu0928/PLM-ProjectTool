# REQ-01-A12-A05 Windows 11 / PostgreSQL Workflow 验证

在仓库根目录、已启动本项目隔离 PostgreSQL 18.6（`127.0.0.1:55434`）后执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
& '.poc-runtime/prj05a05-p04-venv/Scripts/python.exe' `
  'validation/req-01-a12-a05-workflow-pg/verify.py'
```

脚本创建临时数据库，使用正式 Requirement/Review/Workflow 服务与 Windows 组合，验证真实来源、能力、
ReviewRound、聚合预览、写时漂移复验、两项清单记录、`REQUIREMENT -> PROTOTYPE`、Audit/receipt/replay及
Alembic drift，最后强制清理临时数据库。验证数据均为合成数据。
