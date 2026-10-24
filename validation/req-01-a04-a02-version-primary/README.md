# REQ-01-A04-A02 RequirementVersion 主表验证

在 Windows 11 / PostgreSQL 18 环境执行：

```powershell
$env:PYTHONPATH='apps/backend/src'
.poc-runtime/poc-01/windows-online/Scripts/python.exe validation/req-01-a04-a02-version-primary/verify.py
```

覆盖 Migration0116 空历史升降/重升与 drift、主表字段及约束、当前批准版本同需求同项目复合外键、
单一评审中/批准版本索引、Owner 未开放时的直接写入拒绝、TRUNCATE 拒绝和有历史降级拒绝。

验证脚本仅为证明“有历史不可降级”，以数据库管理员身份临时停用版本 Owner 触发器插入一条
满足全部物理约束的 DRAFT fixture，随即恢复触发器；这不开放产品写路径，也不构成业务验收数据。
