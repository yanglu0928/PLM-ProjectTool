# PRJ-05-A12-P03：部门历史行内更新确认

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端页面合同，非实际浏览器/PG）。输入为 P01/P02、部门历史页和 DEC-20260929-459。
- Changed：只对当前项目负责人可写会话显示 ACTIVE 部门修改入口；从授权部门历史读取原条目与强 ETag，不接受任意路由中的部门快照。编号/名称变化撤销勾选确认，确认后固定原 Project/Actor/Department/ETag/输入单次提交。成功仅展示本次回执，清除旧列表并要求独立重读；未知和明确拒绝均清旧并锁写，只有成功刷新可再操作。跨项目/卸载丢弃迟到结果。
- Files：`ProjectDepartmentListView.vue` 及测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 和冻结 `/api/v1`，无需升级。回滚撤行内修改，P01/P02保留。
- Tests：首轮 647/648 因测试夹具将同一已消费 Response 用于两次页面加载，改为每次新建后完整 648/648、typecheck、build PASS；实际浏览器/PG 未运行。
- Known Issues/Next：成功回执不代替当前状态；未知结果需独立历史/审计核对。下一任务 `PRJ-05-A12-P04` Windows 11 浏览器/隔离 PG 验收；正式信任、其他平台、性能/质量、Gate3/包未验。
