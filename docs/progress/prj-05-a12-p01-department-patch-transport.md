# PRJ-05-A12-P01：部门更新固定前端传输

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端传输合同，非实际浏览器/PG）。输入为冻结 `PROJECT_DEPARTMENT_PATCH`、后端 PRJ-04-A15-P02 与 DEC-20260929-457。
- Changed：`SessionClient.patchProjectDepartment` 固定部门 PATCH 路径、规范双 UUID、强且安全整数 `If-Match`、私有 CSRF、同源 Cookie/no-store、单次提交。请求体限制非空且至多 8192 UTF-8 字节；401 清本地会话证明，超时/断线不自动重试，调用层需先 GET 核对未知结果。
- Files：前端 Session transport/测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 和冻结 `/api/v1`，无需升级。回滚可移除此方法及测试。
- Tests：前端 617/617、typecheck、build PASS；无真实浏览器/PG 验证。
- Known Issues/Next：本项不解析成功业务载荷，也不提供更新页面；后续 `PRJ-05-A12-P02` 安全业务响应客户端。正式信任、其他平台、性能/质量、Gate3/可用包未验。
