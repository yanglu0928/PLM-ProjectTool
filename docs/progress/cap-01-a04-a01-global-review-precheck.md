# CAP-01-A04-A01：GLOBAL Review 运行边界前置核查

日期：2026-10-05。结论：`CAP_01_A04_A01_GLOBAL_REVIEW_PRECHECK_PASS`。下一项：`CAP-01-A04-A02` Review GLOBAL 内核与编排。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Capability最小真实Owner继续实施
当前WBS：CAP-01-A04-A01
输入基线：冻结Architecture/DM-05/API-04、Schema0034/0035、CR-CAP-001、DEC-835
前置任务：CAP-01-A03已完成；Capability DRAFT Version和无状态验证Owner可用
涉及模块：review、capability、auth、audit、license、platform idempotency
涉及实体：Review/ReviewRound/SubjectSnapshot/SubjectLock、CapabilityBaseline/BaselineVersion
涉及API：本项不开放HTTP；既有PROJECT Review API保持不变
涉及权限：GLOBAL写为DeploymentAdmin；Reviewer资格须由Auth当前事实证明
验收标准：识别GLOBAL运行差距，固定不伪造Project、不跨Owner写表的实施路径
风险：把GLOBAL评审错误映射为PROJECT；Review通过但Capability未原子消费；扩大公开API
```

## 核查结果

1. Schema0034/0035、Review ORM 与 `ReviewSnapshotReadPort` 已支持 `GLOBAL/project_id=NULL`，证明冻结物理模型无需新增第二套评审表。
2. `ReviewCreateService`、`ReviewStartService`、`ReviewTransitionCommandService` 及对应持久 DTO/仓储全部固定 `project_id: UUID`、ProjectAuthorization 和 `scope='PROJECT'`。
3. `ReviewSubjectStartRequest` 与 `ReviewSubjectTransition` 又显式拒绝非 PROJECT，因此即使手工写入 GLOBAL Review，受信 Subject Owner 合同也无法合法执行。
4. 当前没有任何模块实现 `ReviewSubjectStartPort` 或 `ReviewSubjectTransitionPort`；Review 默认失败关闭，未出现伪 Owner。
5. 冻结架构规定 Review 只决定状态，Subject Owner 消费 `ReviewCompleted` 后原子更新业务正式指针。Capability 不得直接写 `rvw_*`，Review 也不得直接写 `cap_*`。

## 选择

已登记 `CR-RVW-003`。在 Review 内核补齐已有 GLOBAL 合同，保留 PROJECT 兼容入口；GLOBAL 编排使用部署级权限与幂等域，不构造虚假 Project。A04 后续按内核、Subject Owner、终态正式化三个问题拆分实施。

## 验证与兼容

本项仅文档核查，无 Schema、Migration、API、依赖、网络、Secret 或客户数据变化。已核对冻结架构/DM/API、Review应用/ORM/Schema0034/0035和Capability Schema0092。回滚为停止后续实现并保留本记录；Gate 3继续保持 `BLOCKED`。
