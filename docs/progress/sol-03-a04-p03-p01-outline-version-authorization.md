# SOL-03-A04-P03-P01：OutlineVersion 创建授权策略

日期：2026-10-09。结果：`SOL_03_A04_P03_P01_AUTHORIZATION_POLICY_PASS`；仅内部授权策略，OutlineVersion Owner/HTTP/写 Guard 仍关闭。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A04-P03-P01。
- 输入基线/前置：Gate2 API-04/DM-05、CR-SOL-016、`SOL-03-A04` Owner 前置检查和已验证的 Reference 现时来源组合。
- 单一问题：Project 授权矩阵缺冻结 `SOL_OUTLINE_VERSION_CREATE` 操作，Owner 无法按本项目 ProjectManager/ImplementationMember 授权。
- 模块/实体/API/权限：仅 Project Application 的操作策略及矩阵测试；无实体、Schema、Migration、公开 API 或新角色。
- 验收：允许本项目有效 ProjectManager/ImplementationMember，拒 CustomerManager/CustomerMember、非成员、跨项目和归档项目；全量回归。风险是策略已存在但 Owner 未接线，不能误称实际写权限开放。

## 实施与验证

增加 `SOL_OUTLINE_VERSION_CREATE` 写策略，角色与冻结合同一致；现有 `ProjectAuthorizationService` 统一检查项目归属、有效成员与归档状态。矩阵定向 8 项/732 子例通过；后端全量 3429 通过/3 跳过/5234 子例，保留既有 2 条告警。未修改既有授权策略的行为，也未接入 OutlineVersion Owner。无迁移/升级；回滚为撤销这条尚未接线的操作策略，现有数据不受影响。

下一项 `SOL-03-A04-P03-P02` 验证稳定 Section 身份与当前批准 RequirementVersion 的内部证明，再构建 Owner 的原子创建/幂等/Audit 与受限 Guard。Gate3 仍 BLOCKED。

TraceLink：Gate2 API-04/DM-05 → CR-SOL-016 → Reference 使用证明 → 本授权策略 → OutlineVersion Owner。
