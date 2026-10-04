# PRJ-05-A15-P01：项目名称更新固定前端传输

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端传输合同，非实际浏览器/PG）。输入为冻结 `PROJECT_PATCH`、后端 PRJ-04-A06/A07 与 DEC-20260929-469。
- Changed：`SessionClient.patchProject` 固定项目 PATCH 路径、规范 UUID、强且安全整数 `If-Match`、私有 CSRF、同源 Cookie/no-store 和单次提交。请求体非空且至多 8192 UTF-8 字节；401 清本地会话证明，超时/断线不自动重试，调用层需独立 GET 核对未知结果。此层不解析业务响应或授权身份。
- Files：`apps/frontend/src/modules/auth/api/sessionClient.ts` 及测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 和冻结 `/api/v1`，无需升级。回滚可移除此方法及测试。
- Tests：前端 724/724、typecheck、build PASS；覆盖固定路径/头、非法 ID/版本/体、无 CSRF、401/503、超时单次和互斥。实际浏览器/PG 本项未运行。
- Known Issues/Next：不接受传输层原始 Response 作为业务成功，下一任务 `PRJ-05-A15-P02` 安全业务结果客户端；正式信任、其他平台、性能/质量、Gate3/可用包未验。
