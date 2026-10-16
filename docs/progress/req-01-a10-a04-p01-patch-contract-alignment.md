# REQ-01-A10-A04-P01：Requirement PATCH 冻结合同对齐

日期：2026-10-08。结论：`REQ_01_A10_A04_P01_PATCH_CONTRACT_PASS`。下一项：
`REQ-01-A10-A04-P02` Requirement identity 七个冻结 HTTP Operation。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A10-A04-P01
输入基线：冻结API-01/API-04、REQ-01、CR-REQ-001/003、Migration0115
前置任务：REQ-01-A10-A03 Package六HTTP PASS；CR-REQ-003已在实施前登记
涉及模块：requirement identity mutation application与既有PostgreSQL验收脚本
涉及实体：Requirement、RequirementCommandResult、StateDecision、AuditEvent、IdempotencyReceipt
涉及API：不挂载新HTTP；对齐REQ_PATCH的S,L,C,M,A控制
涉及权限：ProjectManager/ImplementationMember；License/Session/CSRF/Project/If-Match
验收标准：PATCH不要求/不写幂等key/receipt；Audit与更新同事务；三类状态命令幂等不变
风险：公开合同被内部DTO反向扩大；修复误伤决定证据或状态命令重放；Audit失败留下根更新
```

## 结果

- `PatchRequirementIdentity` 移除幂等 key，PATCH 走独立非幂等短事务；仍生成不可变
  command result 作为根状态投影证明，并同事务写 Audit。
- DEFER/REJECT/ARCHIVE 继续使用 actor/project/operation/key 范围的持久收据与首成功结果重放。
- Windows 11/PostgreSQL 18.6 验证 PATCH receipt 计数不变、旧 ETag 冲突、并发单胜、
  Audit 失败回滚、状态命令重放、决定 Evidence 证明及 Alembic drift；定向 5、后端 3040/3 通过。
- 开发 wheel 共 1156 项，SHA-256
  `4c1c4cd49cf9d8650508a8c45fb1403ac03f3cd4b15cb5164e37c9da03e470d5`。
- 无 Schema/Migration、公开 HTTP、依赖、Secret 或外发变化；历史 receipt/command result 不删除。
