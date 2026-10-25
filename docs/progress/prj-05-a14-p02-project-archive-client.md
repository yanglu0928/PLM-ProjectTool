# PRJ-05-A14-P02：项目归档首次回执安全客户端

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端合同，非实际浏览器/PG）。输入为 P01、Project 安全只读投影、冻结 PROJECT_ARCHIVE、后端 PRJ-04-A08 与 DEC-20260929-466。
- Changed：只接收 ACTIVE 原项目、强且安全的版本与原幂等 Key；200 必须绑定原 Project ID/编号/名称/创建时间、`ARCHIVED`、`v+1` 与响应强 ETag。回执显式标记非当前状态证明；同 Key 重放不冒充新历史读取。已知 HTTP/错误码一致映射，伪成功、坏信封、断线/超时为未知，不自动生成新请求。
- Files：`projectArchiveClient.ts`及测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 和冻结 `/api/v1`，无需升级。回滚撤业务客户端和测试，P01 传输保留。
- Tests：前端 715/715、typecheck、build PASS；覆盖原项目/版本/Key 校验、首次与重放、已知拒绝、伪成功和断线。实际浏览器/PG 未运行。
- Known Issues/Next：首次回执不代替独立项目详情重读；归档单向且禁止新写/Job，未知结果须核对历史与审计。下一任务 `PRJ-05-A14-P03` 显式确认页面；正式信任、其他平台、性能/质量、Gate3/可用包未验。
