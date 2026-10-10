# REQ-01-A12-A04-A02：Requirement Workflow Windows生产组合注册

日期：2026-10-08。结论：`REQ_01_A12_A04_A02_WINDOWS_COMPOSITION_PASS`。下一项：
`REQ-01-A12-A05` Windows 11 / PostgreSQL 真实聚合Workflow闭环。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A12-A04-A02
输入基线：CR-REQ-004、DEC-1016～1018、A03 Owner/Repository、A04-A01通用写链
前置任务：REQ-01-A12-A04-A01 PASS
涉及模块：entrypoints.windows_workflow_checklist
涉及实体：无新增实体或Schema
涉及API/权限：既有Preview/Record/Transition路由；授权、License、Origin和Session边界不变
验收标准：两个Requirement item显式注册同一聚合Owner，证明依赖完整且缺失依赖失败关闭
风险：不同入口组装出不同Owner；Evidence/Decision依赖实例不一致；影响既有Handover/Survey注册
```

## 实现结果

- Windows Workflow注册表新增`REQUIREMENT_FORMAL_VERSIONS`与`REQUIREMENT_ACCEPTANCE`，两项固定
  绑定同一个`RequirementWorkflowQualificationOwner`，不做运行时发现或隐式回退。
- Owner组合完整注入范围锁Repository、Version当前事实Validator、Survey/Handover/Decision/Evidence/
  Capability来源证明及Review读取；Validator与Owner共享Decision及Evidence证明实例。
- Preview、Checklist Record与Stage Transition三个生产入口继续复用同一注册表工厂；既有Handover、
  Survey四项注册和路由路径不变。

## 验证、兼容与回滚

- 组合及聚合写链定向35项通过；后端全量3084项通过、3项按既定条件跳过，source/tests
  `compileall`通过。
- 开发wheel共1167项，SHA-256
  `eec3d8b33f4402ea02e8c72e3927d21a8f02758d083f2ab26842a4559b277f24`。
- 无Schema/Migration、公开路径、依赖、Secret、客户数据或外发变化；移除两项显式Registration及相关
  imports可回滚，既有四项Owner不受影响。
- 本项验证生产对象图可构造，不替代Windows 11/PostgreSQL真实业务数据、HTTP和阶段推进验证；这些留
  A05。前端/Edge、Gate 3、UAT和发行仍未完成。
