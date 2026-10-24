# REQ-01-A08-A01：RequirementVersion Review 正式化前置核查

日期：2026-10-07。结论：`REQ_01_A08_A01_REVIEW_PRECHECK_PASS`。下一项：
`REQ-01-A08-A02-P01` Review 生命周期 Migration 0120。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：REQ-01-A08-A01
输入基线：冻结REQ_VERSION_SUBMIT_REVIEW、DM-05/API-04、Schema0119、CR-REQ-001
前置任务：A05来源proof、A06 Version Owner、A07当前事实校验均通过
涉及模块：requirement、review、project、audit及A05事实Owner
涉及实体：REQ-01/REQ-03、RVW-01/RVW-02；不增加第二套Review表
涉及API：本项不开放HTTP，不改变冻结Operation
涉及权限：送审者ProjectManager；Reviewer为当前合格项目成员
验收标准：固定Subject锁、状态迁移、当前事实重验、终态指针、回滚与升级边界
风险：把Validate历史报告当当前证明；Review终态未被Subject原子消费；PENDING被送审；批准后不能升版
```

## 核查结果

1. 通用PROJECT Review已提供创建、开轮、决定、撤回、Subject锁、终态回调、Audit和持久幂等内核；
   `REQ-03 + REQUIREMENT_ALL_V1`可复用现有表与合同，不新增评审状态机。
2. Requirement尚未注册Review Subject Owner，未知Subject在现有组合中失败关闭；当前没有伪送审入口。
3. Migration0119只允许DRAFT INSERT，任何Version UPDATE和Root正式指针变化均被数据库守卫拒绝；必须
   通过0120窄门开放DRAFT→IN_REVIEW→APPROVED/RETURNED、旧APPROVED→SUPERSEDED及Root指针更新。
4. A07 Audit是历史观察，不能替代送审/批准当下事实。Subject Owner必须在调用方事务内共享锁重建快照，
   调用同一CurrentValidator，任何issue（含PENDING、来源/能力/Evidence漂移）都拒绝送审或APPROVE。
5. 只允许ACTIVE Requirement的最新DRAFT送审；评审期间A06创建条件已禁止新Version。APPROVED更新正式
   指针并SUPERSEDE旧正式版；RETURNED/WITHDRAWN映射Version RETURNED且保留旧指针。
6. 0119创建逻辑不要求正式指针为空，因此首版批准后仍可显式base当前最高Version创建修订，无需放宽
   创建Owner；Root ETag会在送审和终态消费各递增一次并保持并发栅栏。

## 实施拆分与验证

- `REQ-01-A08-A02-P01`：Migration0120，数据库级开放并延迟闭合Review开始、终态和正式指针。
- `REQ-01-A08-A02-P02`：Requirement Review Subject Owner/Repository，复用PROJECT Review内核并重证A07
  当前事实；完成APPROVED/RETURNED/WITHDRAWN原子消费。
- 冻结HTTP、Windows生产组合和前端仍分别留A10/A11，不在本任务提前装配。

本项为静态核查，无程序、Schema、Migration、依赖、网络、Secret或数据外发变化。已对账Review合同、
Survey同类Owner、Requirement Migration0116～0119、A06创建与A07校验；Gate 3继续阻塞。
