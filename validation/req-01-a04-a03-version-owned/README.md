# REQ-01-A04-A03 RequirementVersion owned 集合验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a04-a03-version-owned/verify.py
```

覆盖 Migration0117 空历史升降/重升与 drift、六类有序 owned 表、同 Version/Requirement/Project
组合归属、固定 CapabilityVersion/Item 引用、来源/验收/能力判断形状、跨项目/重复序号负例、Owner
关闭、TRUNCATE 拒绝和有历史降级拒绝。

脚本以数据库管理员身份通过 `session_replication_role=replica` 构造上游固定 fixture，并仅在负例和历史
保护验证期间临时停用六表 Owner trigger；所有触发器随即恢复。这不是产品写路径或业务事实。
