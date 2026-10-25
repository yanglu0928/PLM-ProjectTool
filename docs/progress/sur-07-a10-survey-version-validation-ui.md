# SUR-07-A10：调研版本当前校验报告面板

日期：2026-10-25；结果：`SUR_07_A10_FRONTEND_PASS`。

## 编码前检查

| 项目 | 内容 |
|---|---|
| Phase/WBS | Phase 2 / `SUR-07-A10`，完成调研 DRAFT 当前版本校验入口与报告面板。 |
| 输入基线 | 冻结 API-04 Survey `:validate` 空正文幂等命令；已有后端 Validation Owner、HTTP Router 和 Windows Survey 组合。 |
| 前置任务 | `SUR-07-A09` 前置核查通过。 |
| 涉及模块 | Session 私有命令桥、Survey 校验客户端、Survey 详情视图。 |
| 实体/API/权限 | SurveyVersion；`POST /api/v1/projects/{project}/surveys/{survey}/versions/{version}:validate`；仅当前项目 Project Manager / Implementation Member 显示入口，服务端仍负责最终授权。 |
| 验收标准 | same-origin Cookie/CSRF、无请求正文、幂等操作号、严格校验报告字段及版本标识/计数；报告清楚表明不改状态、不代表送审/客户批准；网络不确定时保留原 Key 并阻止换号重试。 |
| 风险 | 报告是当次当前来源快照，来源后续变化时须重验；客户端角色仅用于呈现，不替代服务端检查。 |

## 变更

- 新增 Survey Validate Session bridge 与严格响应解析，检查固定版本身份、声明计数、问题条件计数、错误码顺序、缓存头和审计事件。
- 新增详情页当前校验报告面板；当前仅 DRAFT 与有权角色可见。未知结果以 sessionStorage 保存原始幂等 Key，需同号重试；会话切换清理当前报告并提示核对。
- 无 Schema/Migration/API 合同/License/依赖变化。无数据库升级或回滚动作。

## 验证

- SessionClient + Survey detail 定向测试：177 项通过（含 bodyless CSRF transport 和 report 显示）。
- 前端全量测试：2040 项通过，192 个测试文件。
- Typecheck：通过。Production build：通过（399 modules）；Vite 既有主包 >500 kB 警告仍存在，本任务未改动分包策略。
- Server 2025、Debian 13、正式信任、Pilot、Gate 3、客户送审/批准均未因此通过。

下一项：`SUR-07-A11` 原子送审客户端与当前有效客户 Reviewer 选择；沿用项目经理权限、完整成员分页、最大候选数、显式确认及未知结果保留原候选集合/操作号。
