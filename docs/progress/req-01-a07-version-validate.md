# REQ-01-A07：RequirementVersion 校验报告 Owner

日期：2026-10-07。结论：`REQ_01_A07_VERSION_VALIDATE_PASS`。下一项：`REQ-01-A08`
Review 送审与终态正式化。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：REQ-01-A07
输入基线：冻结REQ_VERSION_VALIDATE、RequirementVersion Aggregate、CR-REQ-001、DEC-988～990
前置任务：A05五类来源proof、A06不可变Version创建/读取均通过
涉及模块：Requirement只读快照/验证Owner、来源/Evidence/Capability proof、Audit回放
涉及实体：不修改RequirementVersion；AuditEvent作为不可变验证结果引用
涉及API：内部Owner；HTTP仍未挂载
涉及权限：当前ProjectManager/ImplementationMember、Session/CSRF/License、幂等、Audit
验收标准：分类/验收/来源/能力/冲突有限报告、原Key历史回放、新Key重验、零状态转换
风险：把结构完整冒充业务正确；把PENDING静默转正；用当前事实改写首次报告；把PASS冒充Review
```

## 实现与决策

- 新增共享锁快照仓储、当前事实校验器和幂等报告Owner。报告复算内容指纹及七类声明计数，验证顶层与
  Source/Assessment Evidence嵌套ordinal；重证A05来源、Capability及GLOBAL/PROJECT双侧Evidence。
- 分类规则固定为：STANDARD至少一个人工CONFIRMED DIRECT；NONSTANDARD/DIFFERENCE至少一个人工
  CONFIRMED PARTIAL/NONE且必须有明确排除；PENDING始终返回未通过。AI置信度不参与分类映射。
- 至少一个五要素AcceptanceCriterion；重复标准、同一文本同时作为assumption/exclusion均报告冲突。
  结构/业务问题使用有限稳定issue code，不能依赖自由文本推断通过。
- 每个新Key写一个SUCCESS Audit和receipt，业务`valid`可为false；原Key从不可变Audit恢复首次观察，
  上游事实恢复或漂移均不改写历史报告，新Key才重新观察。Version状态与正式指针均保持不变。

## 验证

- Windows 11 / PostgreSQL 18.6：有效STANDARD报告、PROJECT Evidence撤销、Capability Review Snapshot
  漂移、恢复后新Key重验、PENDING失败、原Key历史重放、幂等冲突、CustomerManager/License/跨项目拒绝、
  Version零状态变化及Alembic drift通过。
- 定向14项、后端全量3013项通过且3项既有环境跳过；开发wheel共1145项，SHA-256
  `63cc68f3751e9160a87caa0443cce747efda001b9b12b7758b98ba9565c9a8c8`，不是正式发行包。

无Schema、Migration、公开API、依赖、Secret、客户数据或外发变化。可停止Validation Owner关闭新报告，
既有Audit/receipt保留。校验PASS不是人工Review或APPROVED；A08～A12、Gate 3、UAT和发行仍待。
