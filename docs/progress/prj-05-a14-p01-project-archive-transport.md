# PRJ-05-A14-P01：项目归档固定前端传输

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端传输合同）。输入为冻结 PROJECT_ARCHIVE、后端 PRJ-04-A08-P03、现有项目只读模型和 DEC-20260929-465。
- Changed：`SessionClient.postProjectArchive` 固定私有 `POST /api/v1/projects/{project_id}:archive`，规范 Project UUID、强且安全整数 `If-Match`、原可打印幂等 Key、私有 CSRF、同源 Cookie/no-store、空 Body 单次提交。401 清本地证明；超时/断线不自动重试，调用层须保留原 Key/版本。
- Files：`sessionClient.ts`及测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 和冻结 `/api/v1`，无需升级。回滚撤前端方法及其测试。
- Tests：前端 687/687、typecheck、build PASS；覆盖固定请求、坏路径/版本/Key、缺写证明、503/401 和超时互斥。实际浏览器/PG 未运行。
- Known Issues/Next：本项不解析 200 回执，也不提供单向归档按钮；下一任务 `PRJ-05-A14-P02` 安全首次回执客户端。正式信任、其他平台、性能/质量、Gate3/可用包未验。
