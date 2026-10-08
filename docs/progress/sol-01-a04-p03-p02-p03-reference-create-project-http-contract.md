# SOL-01-A04-P03-P02-P03：PROJECT Reference 创建 HTTP 合同

日期：2026-10-09；结果：`PROJECT_REFERENCE_CREATE_HTTP_CONTRACT_PASS`，非运行装配或完整 Reference 功能 PASS。

```text
当前 Phase：Phase 2
当前 WBS：SOL-01-A04-P03-P02-P03
输入基线：冻结 API-01/API-04、CR-SOL-007、0144、P03-P02-P02 PROJECT PG 证据
前置：内部 Owner 及 PROJECT 真实 PG/文件组合通过
涉及模块/实体：Solution HTTP 创建边界；无实体/Schema 变化
API/权限：PROJECT POST，PM/IM；GLOBAL 路由尚未装配
验收：严格正文、Session/CSRF/Origin/幂等、201/ETag/Location/Envelope、默认关闭
风险：GET/List、真实 ASGI/PG/文件及正式信任源、GLOBAL 人工确认、UI 待
```

新增可选 PROJECT Router，路径直接决定 Scope/ProjectId，不接受 body 自报归属；服务端在同事务重查角色、来源、License、Audit 和幂等。合同测试覆盖默认 404、201 安全投影、正确 Trace/ETag/Location，以及 Cookie、Origin、CSRF、幂等头、查询串、未知字段、错误 UUID、错误形状、重复 JSON Key、无权/冲突/来源不可用、错误归属返回值。`4 passed, 8 subtests passed`；后端全量 `3305 passed, 3 skipped, 4839 subtests passed`。未进行本路由真实 ASGI/PG/文件组合，故不把该端点称为运行可用。

TraceLink：API-01/API-04 → CR-SOL-007/DEC-20261009-1112 → ReferenceCreateService/PROJECT Router → 合同测试 → 后续真实 ASGI/PG。
