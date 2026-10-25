# CAP-01-A03-P01 Baseline 创建验证

在 Windows 11 / PostgreSQL 18.6 隔离临时库验证真实 DeploymentAdmin Session/CSRF、License、GLOBAL Document 当前事实、幂等收据、Audit、数据库初始形态、并发重放、失败回滚和撤权。

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/cap-01-a03-p01-baseline-create/verify.py
```

全部来源均为合成元数据；不读取标准能力库正文、不外发数据、不创建 BaselineVersion 或 APPROVED 正式事实。
