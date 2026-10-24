# PRJ-05-A15-P03：项目名称更新显式确认页面

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端页面合同，非实际浏览器/PG）。输入为 P01/P02、项目详情 GET、冻结 `PROJECT_PATCH` 与 DEC-20260929-471。
- Changed：项目详情仅向当前可写 ProjectManager 的 ACTIVE 项目显示改名入口，原编号和版本明示，新名称编辑后需要重新勾选确认；归档与改名编辑互斥。提交使用原 Project/版本/Actor 快照，成功回执只说明本次响应并清旧详情，独立 GET 后才展示当前状态；已知拒绝或未知结果同样清旧详情、禁止直接重发，提示重读与核对审计。跨项目/卸载丢弃迟到结果。
- Files：`apps/frontend/src/modules/project/views/ProjectDetailView.vue` 及测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 与冻结 `/api/v1`，无需升级。回滚可撤页面改名入口与状态，P01/P02 保留。
- Tests：前端 756/756、typecheck、build PASS；覆盖非负责人/已归档入口、显式确认/编辑撤确认、同名更新、回执与当前 GET 分离、拒绝/未知清旧、独立刷新和跨项目迟到结果。首轮测试通过但测试样本类型过宽导致 typecheck 失败，修正测试声明后完整重跑。实际浏览器/PG 本项未运行。
- Known Issues/Next：浏览器离页后未知写结果无原请求恢复（PATCH 无持久幂等 Key），须核对当前详情与审计。下一任务 `PRJ-05-A15-P04` Windows 11 隔离浏览器/PG 验收；正式信任、其他平台、性能/质量、Gate3/可用包未验。
