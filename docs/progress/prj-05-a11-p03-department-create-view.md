# PRJ-05-A11-P03：部门创建确认页面

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端合同，非实际浏览器/PG）。输入为P01/P02、部门历史页及DEC-20260929-455。
- Changed：部门历史仅对当前项目负责人有写证明的会话显示创建入口；独立页面核对编号/名称、显式确认后固定原Project/Actor/输入/幂等Key提交。未知结果保留原记录并要求再次确认同Key恢复，幂等冲突锁页，确定拒绝清原尝试；首次回执明确非当前状态证明，返回历史须重读。切项目/卸载丢弃迟到回执并隐藏写表单。
- Files：`ProjectDepartmentCreateView.vue`及测试、路由、部门历史入口/测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容DB head `20260927_0049`及冻结`/api/v1`，无需升级。回滚撤页面/路由/入口，P01/P02保留。
- Tests：前端613/613、typecheck PASS；首次合并构建在Windows进程异常退出，单独完整`npm run build`重跑PASS。真实浏览器/PG未运行。
- Known Issues/Next：原Key仅保留本页内存，离页后未知结果必须先核对历史/审计；正式信任、其他平台、性能/质量、Gate3/可用包未验。下一任务PRJ-05-A11-P04 Windows11浏览器/隔离PG验收。
