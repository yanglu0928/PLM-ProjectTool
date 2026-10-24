# PRJ-05-A11-P01：部门创建私有传输

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端传输合同）。输入为冻结 Department POST、PRJ-04-A14-P03 与 DEC-20260929-453。
- Changed：SessionClient 增加固定 `POST /api/v1/projects/{project_id}/departments`，规范 Project UUID、私有 CSRF、调用方原幂等 Key、同源 Cookie、8192 字节上限与单次超时；401 清写证明，未知结果不自动重发。只提供传输，不解析业务响应或创建页面。
- Files：`apps/frontend/src/modules/auth/api/sessionClient.ts`、对应测试、决策、进度、版本说明、STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 与冻结 `/api/v1`，无需升级。回滚撤本方法和测试。
- Tests：前端575/575、typecheck、build PASS；实际浏览器/PG未运行。
- Known Issues/Next：HTTP 201 仍须绑定原项目、输入与强 ETag/Location；页面必须保留未知结果原 Key。正式信任、其他平台、性能/质量、Gate3/可用包未验。下一任务 PRJ-05-A11-P02 部门创建安全业务响应客户端。
