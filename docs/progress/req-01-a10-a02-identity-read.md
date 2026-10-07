# REQ-01-A10-A02：Package / Requirement identity 读取 Owner

日期：2026-10-08。结论：`REQ_01_A10_A02_IDENTITY_READ_PASS`。下一项：
`REQ-01-A10-A03` Package 六个冻结 HTTP Operation。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A10-A02
输入基线：冻结API-01/API-04、REQ-01/REQ-02、CR-REQ-001、Migration0111～0121
前置任务：REQ-01-A10-A01 HTTP/组合前置核查PASS
涉及模块：requirement application/infrastructure；project authorization；auth/license
涉及实体：RequirementPackage、Requirement、RequirementPackageMembership
涉及API：无公开HTTP；为REQ_PACKAGE_LIST/GET、REQ_LIST/GET提供Owner
涉及权限：所有当前Project Member可读；Session/License/项目隔离失败关闭
验收标准：四读取、最小投影、成对keyset、包成员稳定顺序、跨项目隐藏、零写入、PG18 drift
风险：只用timestamp分页会丢行；读取误写Audit/receipt；详情暴露非当前项目成员
```

## 实施

- 新增统一 identity read Service/Repository；Package与Requirement分别使用
  `(updated_at DESC, id DESC)`成对位置，只有完整位置才可继页。
- Package列表返回当前状态、创建/更新元数据和强ETag；详情额外返回按UUID
  字节序排列且去重的Requirement ID。Requirement列表/详情投影当前状态、正式版指针和强ETag。
- 新增四个冻结权限策略，均限所有当前Project Member读取；先通过License、
  Session与Project授权，再执行项目限定查询。仓储异常shape统一失败关闭。

## 验证、兼容与回滚

- 定向13项通过；完整后端3033项通过、3项按既有平台条件跳过。
- Windows 11 / PostgreSQL 18.6真实库验证CustomerMember读取、Package/Requirement双页
  keyset、成员顺序、跨项目隐藏、Session/License拒绝、零Audit/receipt/业务写入和drift。
- 开发wheel共1153项，SHA-256
  `6736871ab5d2266bf1fce89a15965f5499601e2d03cc7fa5a448bce83f5a7621`。
- 无Schema/Migration、公开HTTP、依赖、Secret或外发变化。回滚可移除读取Owner与四项
  授权策略；既有数据不受影响。Windows Server 2025与Debian 13未在本WBS重验。
