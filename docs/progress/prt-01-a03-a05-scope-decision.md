# PRT-01-A03-A05：NOT_REQUIRED 原子范围决定 Owner

日期：2026-10-08。结论：`PRT_01_A03_A05_SCOPE_DECISION_PASS`。`PRT-01-A03`完成；下一项：
`PRT-01-A04` GLOBAL/PROJECT PrototypeTemplate 与不可变 TemplateVersion 基础。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：PRT-01-A03-A05
输入基线：CR-PRT-001、Schema0125、A03-A01、冻结PRT_MARK_NOT_REQUIRED控制
前置任务：PRT-01-A03-A04 PASS
涉及模块：prototype scope decision application/repository、requirement/review current facts、authorization/audit
涉及实体：PRT-02 Root、不可变ScopeDecision、固定RequirementVersion refs、不可变first result
涉及API：内部Owner；命令含I/M；Router仍关闭
涉及权限：ProjectManager/CustomerManager
验收标准：强ETag、当前Approved需求、决定内容指纹、可选精确Approved Review、重放与提交闭包
风险：把PM称客户确认；固定旧/草稿需求；无范围空决定；Root/决定/引用/结果半提交
```

## 实施结果

- 新增`PRT_MARK_NOT_REQUIRED`严格命令、Service和Repository。范围为1～200个唯一RequirementVersion，
  规范排序进入决定指纹；事务锁由写授权先锁Project，再锁Prototype及全部Requirement/Version。
- 每个引用必须同项目、`version_state=APPROVED`且仍被Requirement的正式指针精确指向；Prototype必须
  ACTIVE且没有Approved PrototypeVersion。Root、决定、有序固定引用、不可变首结果、Audit和receipt同事务。
- PM或CustomerManager的当前受权命令记录为`confirmed_by`；不产生`customer_confirmed`字段。Review可空；
  若提供，必须是同项目Approved `PRT_SCOPE_DECISION` Review/Round，Snapshot内容指纹与本次决定完全一致。
- Migration0126为决定补充32字节内容指纹并新增不可变结果/延迟闭包；直接写半套决定失败关闭，产生历史后
  拒绝物理降级。该指纹和内部Review证明合同是CR-PRT-001下的兼容实现细化，不新增公开API或必填字段。

## 验证

- Windows 11/PostgreSQL 18.6：空历史升降/重升、drift、PM/CustomerManager/实施成员边界、Session/CSRF/
  License、非当前Approved拒绝、精确Review/无Review、Audit回滚、重放/冲突、直接半套提交拒绝、归档后
  首结果保留、撤权重放拒绝及历史拒降：PASS。
- 定向29项PASS；完整后端3113项PASS、3项既有条件跳过；compileall PASS。
- 开发wheel构建PASS，1184 entries，SHA-256
  `b88fd092635e6cd8b0efa99f2bdf88fe93a7a50bbd04d1e216a2cfec756c9a6c`。

本项未开放HTTP、Template、PrototypeVersion/正式Review/Workflow或客户事实；实库上游Requirement/Review
为隔离合成验证数据。Windows Server 2025未执行本轮，Debian 13按用户指令跳过，Gate 3/UAT/发行仍未通过。
