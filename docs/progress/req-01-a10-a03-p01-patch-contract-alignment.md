# REQ-01-A10-A03-P01：Package PATCH 冻结合同对齐

日期：2026-10-08。结论：`REQ_01_A10_A03_P01_PATCH_CONTRACT_PASS`。下一项：
`REQ-01-A10-A03-P02` Package 六个冻结 HTTP Operation。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A10-A03-P01
输入基线：冻结API-01/API-04、REQ-01、CR-REQ-001/002、Migration0113
前置任务：REQ-01-A10-A02 identity读取Owner PASS；CR-REQ-002已在实施前登记
涉及模块：requirement package mutation application与既有PostgreSQL验收脚本
涉及实体：RequirementPackage、PackageCommandResult、AuditEvent、IdempotencyReceipt
涉及API：不挂载HTTP；对齐REQ_PACKAGE_PATCH的S,L,C,M,A控制
涉及权限：ProjectManager/ImplementationMember；License/Session/CSRF/Project/If-Match
验收标准：PATCH不要求/不写幂等key/receipt；Audit与更新同事务；ADD/REMOVE幂等不变
风险：公开合同被内部DTO反向扩大；修复误伤ADD/REMOVE重放；Audit失败留下根更新
```

## 结果

- `PatchRequirementPackage` 移除幂等key，PATCH走独立非幂等短事务；仍生成不可变
  command result作为根状态投影证明，并同事务写Audit。
- ADD/REMOVE继续使用actor/project/operation/key范围的持久收据与首成功结果重放。
- Windows 11/PostgreSQL 18.6验证PATCH receipt计数不变、旧ETag冲突、Audit失败回滚、
  ADD/REMOVE重放及Alembic drift；定向6、后端3033/3通过。
- 开发wheel共1153项，SHA-256
  `c52ddd2bd629d5a9d116bb50e8986390d342d675cb86598e0b00c2dc8471e324`。
- 无Schema/Migration、公开HTTP、依赖、Secret或外发变化；历史receipt/command result不删除。
