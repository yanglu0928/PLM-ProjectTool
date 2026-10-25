# PRJ-05-A12-P02：部门更新安全业务客户端

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端合同，非实际浏览器/PG）。输入为 P01、部门安全只读投影、冻结 API 与 DEC-20260929-458。
- Changed：只允许 ACTIVE 原部门且 `code`/`name` 至少一项；输入按 NFKC/trim、长度和控制字符约束。一次 PATCH 的 200 回执必须与原部门 ID/创建时间/状态、目标与未改字段、强响应 ETag 和预期版本增长一致；无实际变化保持原版本。明确错误码/HTTP 状态逐一匹配，其他响应或断线视为未知，不自动重试。
- Files：`projectDepartmentPatchClient.ts`及测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 和冻结 `/api/v1`，无需升级。回滚可移除客户端/测试，P01传输保留。
- Tests：前端 644/644、typecheck、build PASS；实际浏览器/PG 未运行。
- Known Issues/Next：PATCH 回执不替代独立历史重读；若断线后不能确定服务端是否提交，必须先重读再决定。下一任务 `PRJ-05-A12-P03` 显式确认页面。正式信任、其他平台、性能/质量、Gate3/可用包未验。
