# REQ-01-A04-A04 RequirementVersion 支持引用与完整性验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a04-a04-version-support/verify.py
```

覆盖 Migration0118 既有Requirement身份安全升级、未审计Version拒升、空支持历史降级/重升、drift、
Source/Assessment Evidence及Version AI Task规范化引用、声明计数、连续ordinal、STANDARD+PROJECT双证明、
PROJECT Evidence映射、Accepted-to-Draft AI provenance、Owner关闭、TRUNCATE和有支持历史拒降。

上游Evidence/Capability/AI fixture以管理员复制模式创建；RequirementVersion及owned/support Owner trigger
仅在提交闭包测试期间临时停用并恢复。所有完整性constraint trigger保持启用，负例由真实事务提交拒绝。
