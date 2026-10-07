# PRT-01-A07-A01：PrototypeVersion Review/Formalize 前置核查

日期：2026-10-08。结论：`PRT_01_A07_A01_REVIEW_PRECHECK_PASS`。下一项：
`PRT-01-A07-A02-P01` Review 生命周期 Migration0132。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：PRT-01-A07-A01
输入基线：冻结PRT_VERSION_SUBMIT_REVIEW、PRT-03、PROTOTYPE_ALL_V1、Schema0131、CR-PRT-001
前置任务：A05 Schema、A06固定证明/Create/Read/Validate均通过
涉及模块：prototype、review、project、trace、audit；不新增第二套Review表
涉及实体：PRT-02/PRT-03、RVW-01/RVW-02、TRC-01
涉及权限：送审者ProjectManager；Reviewer为当前合格项目成员
验收标准：最新DRAFT送审、当前事实重验、终态原子消费、正式指针与旧批准版、Trace及回滚边界
风险：Validate报告替代当前证明；评审期间继续建版；批准未推进正式指针；退回误清旧批准版
```

## 核查结论

1. 复用通用PROJECT Review Kernel与既有Subject Owner协议；固定Subject为`PRT-03`、Policy为
   `PROTOTYPE_ALL_V1`，不复制Review状态机或私表。
2. 只有ACTIVE Prototype的最新DRAFT可送审；送审和APPROVE前必须在调用事务内重新执行Template、当前
   Approved Requirement、Document可用性及Interaction安全验证，不能消费历史ValidationReport。
3. Migration0132只开放DRAFT→IN_REVIEW→APPROVED/RETURNED、旧APPROVED→SUPERSEDED和Root正式指针/
   lock推进。评审期间禁止创建后续Version；APPROVED后才允许基于最新链继续创建DRAFT。
4. APPROVED原子更新`current_approved_version_ref`并把旧APPROVED改为SUPERSEDED；RETURNED/WITHDRAWN映射
   RETURNED且保留旧正式指针。任何终态都保留不可变owned集合和Review引用。
5. Trace只在批准终态建立`PrototypeVersionApproved`可消费关系，固定Review/Round与RequirementVersion来源；
   不以Trace替代Owner事实，也不在DRAFT/IN_REVIEW阶段制造正式链接。

## 实施拆分

- `A07-A02-P01`：Migration0132，状态/指针/创建互斥及终态延迟闭包。
- `A07-A02-P02`：当前事实Validator、Prototype Review Subject Owner/Repository与终态消费。
- `A07-A03`：批准Trace Owner及反向来源闭包。
- `A07-A04`：原子`PRT_VERSION_SUBMIT_REVIEW`业务编排；公开HTTP仍留A09。

本项纯文档，无Schema/API/代码/依赖/外发。Windows Server 2025未验证，Debian13按指令跳过；Gate3保持
BLOCKED，不能把前置核查描述为Review或正式化已完成。
