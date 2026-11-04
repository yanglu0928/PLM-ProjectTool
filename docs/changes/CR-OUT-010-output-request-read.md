# CR-OUT-010：OutputRequest 固定版本只读详情

- 日期：2026-11-04
- 状态：已按持续授权登记；OUT-01-A01-P13编码前检查通过
- 来源：CR-EXEC-002 Windows内部Pilot纵向链；P12 Create路由完成后需提供其冻结详情查询
- 基线：API-03 OUTPUT_REQUEST_GET；不修改冻结API/Data Model/Schema

## 决定

为GET /api/v1/projects/{project_id}/output-requests/{output_request_id}新增固定记录只读projection与可注入router。复用Project read authorization和License；SQL按project_id与request id精确过滤，跨项目与不存在统一404。只返回固定版本refs、fingerprint、state和JobRef。

## 边界与回滚

无Schema/API迁移、无状态修改、无Context正文/路径/Secret外露、无当前版本重查、无插件/AI/文件执行。回滚只移除read projection、router与测试，P12 Create保持。

## 验收计划

Hosted后端定向/全量与PG18合成隔离、最小详情projection，再运行父包/A17/A34/A35/A50。正式路由保持未挂载，客户数据不进入验证。
