# PRJ-05-A13-P02：部门停用安全业务回执客户端

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端合同，非实际浏览器/PG）。输入为 P01、部门安全只读投影、冻结 API、CR-PRJ-005 与 DEC-20260929-462。
- Changed：只接受 ACTIVE 原部门、强安全版本、可打印原幂等 Key；200 必须绑定原部门 ID/编号/名称/创建时间、`INACTIVE`、`v+1` 与响应强 ETag。回执显式标记非当前状态证明；同 Key 重放只代表不可变首次结果。已知 HTTP/错误码一致映射，包括在用部门 409；未知或断线保留原 Key/If-Match，不自动生成新请求。
- Files：`projectDepartmentDeactivateClient.ts`及测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 与冻结 `/api/v1`，无需升级。回滚撤客户端/测试，P01传输保留。
- Tests：前端 679/679、typecheck、build PASS；实际浏览器/PG 未运行。
- Known Issues/Next：首次回执不代替独立部门历史重读；未知结果先核对历史与审计。下一任务 `PRJ-05-A13-P03` 停用显式确认页面；正式信任、其他平台、性能/质量、Gate3/可用包未验。
