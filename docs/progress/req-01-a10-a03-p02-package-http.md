# REQ-01-A10-A03-P02：RequirementPackage 六个冻结 HTTP

日期：2026-10-08。结论：`REQ_01_A10_A03_P02_PACKAGE_HTTP_PASS`。下一项：
`REQ-01-A10-A04` Requirement identity 七个冻结 HTTP。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A10-A03-P02
输入基线：冻结API-01/API-04、REQ-01、CR-REQ-001/002、Migration0111～0121
前置任务：A10-A02读取Owner与A03-P01 PATCH合同对齐PASS
涉及模块：requirement api/application/infrastructure；通用FastAPI显式Router注入
涉及实体：RequirementPackage、RequirementPackageMembership、IdempotencyReceipt、AuditEvent
涉及API：REQ_PACKAGE_LIST/CREATE/GET/PATCH/ADD/REMOVE；路径与冻结API-04一致
涉及权限：当前Project Member读；PM/IM写；Session/License/CSRF/Project/If-Match/Idempotency
验收标准：六端点、独立签名cursor、严格DTO、强ETag、幂等重放、默认404、真实PG后验
风险：cursor跨Session/项目重放；PATCH再引入幂等key；内部字段/异常泄露；Router误默认开放
```

## 实施与验证

- 新增`RequirementPackageCursorCodec`，以独立32字节密钥签名，绑定family、Project、
  Session摘要、page size及完整`(updated_at, package_id)`位置；篡改或跨上下文失败关闭。
- 新增opt-in Package Router和通用`create_app` 显式注入点。未注入时六路径均404；
  Windows组合根仍未接线，留A08。
- 读取仅接受白名单query；写请求严格检查Origin/CSRF/JSON字段。Create和ADD/REMOVE
  要求幂等key；PATCH只要求强If-Match。响应使用最小投影、`no-store`、ETag及Create Location。
- 新增合同/cursor定向7项通过；完整后端3040项通过、3项既有平台条件跳过。
- Windows 11/PostgreSQL 18.6真实HTTP验证六Operation、双页cursor、CustomerMember读取、
  PATCH零receipt、ADD重放、REMOVE、角色/License拒绝、Audit、行数后验和drift。
- 开发wheel共1156项，SHA-256
  `204dd820ffa135baa79cb90603944ca68567a1ea7b19a41a1352cc33a9076a25`。

## 兼容与回滚

无Schema/Migration、依赖、Secret或外发变化。移除`requirement_package_router`注入即关闭所有
新入口；已成功的Package、membership、receipt、command result和Audit历史保留，不物理删除。
正式cursor密钥供给与Windows组合属A08；Server 2025、Debian 13、性能、UAT与Gate 3未因本项关闭。
