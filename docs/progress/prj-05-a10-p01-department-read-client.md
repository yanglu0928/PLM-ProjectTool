# PRJ-05-A10-P01：部门历史只读客户端

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端合同，非实际浏览器/PG 验收）。输入为冻结 Department 列表、PRJ-04-A13-P04 与 DEC-20260929-450。
- Changed：独立 `ProjectDepartmentReadClient` 按固定50条读取部门历史；安全投影保留 ACTIVE/INACTIVE、创建时间和强 ETag，不复用成员选择时只保留 ACTIVE 的候选客户端。UUID/游标/响应合同、重复 ID、错误映射与单次超时失败关闭。
- Files：`apps/frontend/src/modules/project/api/projectDepartmentReadClient.ts` 及对应测试；决策、进度、版本说明和 STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 与冻结 `/api/v1`，无升级步骤。权限仍由服务器实时裁决。
- Tests：前端 557/557、typecheck、build PASS；浏览器/实际 PostgreSQL 未运行。回滚可撤新增独立客户端，不影响成员选择及后端。
- Known Issues/Next：跨页历史可能变化，不宣称快照一致；页面和真实浏览器/PG、正式信任、Server 2025/Debian、性能/质量、Gate 3/可用包仍待。下一项 PRJ-05-A10-P02 部门历史页面。
