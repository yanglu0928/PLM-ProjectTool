# PRJ-05-A13-P03：部门停用显式确认页面

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端合同，非实际浏览器/PG）。输入为 P01/P02、部门历史安全投影、冻结 API、CR-PRJ-005 与 DEC-20260929-463。
- Changed：仅当前项目负责人可在 ACTIVE 历史行发起停用，勾选核对目标、版本及影响后提交。成功首次回执不冒充当前状态，清旧列表并要求独立历史重读；未知结果保留原 Project/Actor/Department/ETag/Key 于本页，成功重读且原行仍 ACTIVE、原版本未变才可再次明确确认并复用原 Key。历史变化或未读到原行不恢复；幂等冲突锁本页，切项目/卸载丢弃迟到回执。刷新后仍显示冲突锁定说明。
- Files：`ProjectDepartmentListView.vue`及测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 与冻结 `/api/v1`，无需升级。回滚撤停用页面入口，P01/P02 客户端保留。
- Tests：前端 683/683、typecheck、build PASS；覆盖非负责人/非 ACTIVE、明确确认、原 Key 不确定恢复、历史变化、幂等冲突及跨项目迟到结果。实际浏览器/PG 未运行。
- Known Issues/Next：未知结果离页后内存原 Key 不再可恢复，必须核对历史与审计；分页未读到原行不允许恢复。下一任务 `PRJ-05-A13-P04` Windows 11 隔离合成浏览器/PG 验收；正式信任、其他平台、性能/质量、Gate 3/可用包未验。
