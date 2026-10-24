# PRJ-05-A11-P02：部门创建首次结果安全客户端

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端业务合同，非实际浏览器/PG）。输入为冻结Department201响应、P01传输、只读安全投影与DEC-20260929-454。
- Changed：NFKC规范化部门编码/名称并固定二字段Body；仅201且trace、Department安全投影、原编码/名称、ACTIVE/`"v0"`、ETag与精确Location一致时返回不可变首次回执，显式声明不是当前状态证明。已知拒绝安全映射；网络/坏响应/伪成功分类为不确定，不自动重发。
- Files：`apps/frontend/src/modules/project/api/projectDepartmentCreateClient.ts`及测试、决策、进度、版本说明、STATUS。
- Migration/API：无；兼容DB head `20260927_0049`和冻结`/api/v1`，无升级步骤。回滚撤新增业务客户端，P01私有传输保留。
- Tests：前端604/604、typecheck、build PASS；实际浏览器/PG未运行。
- Known Issues/Next：首次回执可能是同Key重放，不能作为当前状态证明；页面必须保留原输入/Key处理未知结果。正式信任、其他平台、性能/质量、Gate3/可用包未验。下一任务PRJ-05-A11-P03创建页面。
