# PRJ-05-A15-P02：项目名称更新安全业务结果客户端

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（前端业务客户端合同，非页面或实际浏览器/PG）。输入为 P01、冻结 `PROJECT_PATCH`、后端 PRJ-04-A06/A07、项目只读投影和 DEC-20260929-470。
- Changed：名称仅经 NFKC/trim、1～255 字符及控制字符拒绝后作为单字段提交；要求原项目规范 ID、ACTIVE、强版本。200 回执须绑定原项目 ID/编号/创建时间、目标名称、ACTIVE、`v+1` 与响应头 ETag；即使同名 PATCH，后端仍递增版本。结果只返回安全 ProjectView，不把回执当独立当前 GET。状态与错误码匹配的拒绝明确返回；伪成功、断线、503 或错码状态均标不确定，禁止直接自动重试。
- Files：`apps/frontend/src/modules/project/api/projectPatchClient.ts` 及测试、决策/进度/版本/STATUS。
- Migration/API：无；兼容 DB head `20260927_0049` 和冻结 `/api/v1`，无需升级。回滚可撤客户端与测试，P01 保留。
- Tests：前端 751/751、typecheck、build PASS；覆盖正常与同名 v+1、非法输入、身份/字段/版本伪成功、ETag/JSON、已知拒绝、未知及断线。实际浏览器/PG 本项未运行。
- Known Issues/Next：页面仍未提供项目名称修改入口；下一任务 `PRJ-05-A15-P03` 显式确认界面，成功/未知均需独立重读以恢复当前状态。正式信任、其他平台、性能/质量、Gate3/可用包未验。
