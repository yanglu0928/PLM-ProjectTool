# PRJ-05-A13-P01：部门停用固定前端传输

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端传输合同，非实际浏览器/PG）。输入为冻结 `PROJECT_DEPARTMENT_DEACTIVATE`、后端 PRJ-04-A16-P03 和 DEC-20260929-461。
- Changed：`SessionClient.postProjectDepartmentDeactivate` 固定部门停用 POST 路径、规范双 UUID、强且安全整数 `If-Match`、原可打印幂等 Key、私有 CSRF、同源 Cookie/no-store、空 Body 单次提交。401 清本地会话证明，超时/断线不自动重试；调用层必须保留原 Key/If-Match。
- Files：前端 Session transport/测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 和冻结 `/api/v1`，无需升级。回滚可移除此方法及测试。
- Tests：前端 652/652、typecheck、build PASS；实际浏览器/PG 未运行。
- Known Issues/Next：本项不解析 200 首次回执，不提供停用页面。后续 `PRJ-05-A13-P02` 安全业务回执客户端；正式信任、其他平台、性能/质量、Gate3/可用包未验。
