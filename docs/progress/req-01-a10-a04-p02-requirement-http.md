# REQ-01-A10-A04-P02：Requirement identity 七个冻结 HTTP

日期：2026-10-08。结论：`REQ_01_A10_A04_P02_REQUIREMENT_HTTP_PASS`。下一项：
`REQ-01-A10-A05` RequirementVersion 四个普通 HTTP。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A10-A04-P02
输入基线：冻结API-01/API-04、REQ-01、CR-REQ-001/003、Migration0115
前置任务：A04-P01 PATCH合同对齐，A02 identity读取Owner，A03 Package HTTP均PASS
涉及模块：Requirement API/cursor、identity读写Owner、通用App Router注入点
涉及实体：Requirement、RequirementCommandResult、StateDecision、DecisionEvidenceRef、AuditEvent
涉及API：REQ_LIST/CREATE/GET/PATCH/DEFER/REJECT/ARCHIVE
涉及权限：Project member读取；PM/Implementation写；PM/CustomerManager决定；PM归档
验收标准：专用签cursor、严格DTO、安全错误、ETag/If-Match、决定Evidence、默认关闭
风险：跨资源cursor重放；PATCH伪幂等；错误投影泄漏；决定引用与状态不一致
```

## 结果

- 新增独立 `RequirementCursorCodec`，以独立 32 字节 key 和 `requirements` family 绑定
  Project、Session 摘要、page size及`(updated_at, requirement_id)`位置；拒绝跨上下文重放。
- 新增 opt-in Router，完整实现 LIST/CREATE/GET/PATCH/DEFER/REJECT/ARCHIVE 七个冻结路径；
  通用应用只在显式注入时开放，默认仍返回 404，Windows 正式组合留 A08。
- CREATE/DEFER/REJECT/ARCHIVE使用持久幂等；PATCH只使用强If-Match且不产生receipt。
  DEFER/REJECT严格接收reason、impact和Evidence ID，并返回决定与Evidence引用。
- 输出按资源、Project、操作终态和最小投影验证；未知Owner错误统一安全映射，响应禁止缓存。
- 定向cursor/HTTP 7项通过；完整后端3047项通过、3项跳过。
- Windows 11/PostgreSQL 18.6真实七Operation、cursor、ETag、PATCH零receipt、决定Evidence、
  状态命令重放、角色/License拒绝、Audit及Alembic drift通过。
- 开发wheel共1158项，SHA-256
  `b2f8e19c99ecc3f3477a9314704c233e47c1aaac7a879c6aeda6649945006fc1`。
- 无Schema/Migration、依赖、Secret、客户数据或外发变化；正式cursor key供给与显式组合留A08。
