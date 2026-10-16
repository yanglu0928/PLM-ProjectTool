# PRT-01-A04-A03 validation

在 Windows 11 本机 PostgreSQL 18.6 一次性数据库执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
& '.poc-runtime/poc-01/windows-online/Scripts/python.exe' `
  'validation/prt-01-a04-a03-template-create/verify.py'
```

验收标志：`PRT_01_A04_A03_TEMPLATE_CREATE_PASS`。脚本使用合成管理员、项目成员、项目及
GLOBAL/PROJECT DocumentVersion，验证权限、License、Artifact proof、OUTPUT_ARTIFACT失败关闭、合同
规范化、重放/冲突、Audit回滚、提交闭包、撤权重放拒绝和历史拒降；结束时删除临时数据库。
