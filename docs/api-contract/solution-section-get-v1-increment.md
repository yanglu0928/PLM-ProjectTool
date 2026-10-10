# SOL-04-A08：SolutionSection GET HTTP 增量合同

日期：2026-10-09；细化 Gate 2 冻结 API-04 `SOL_SECTION_GET`，不改变冻结提交或资源种类。

`GET /api/v1/projects/{project_id}/solution-sections/{section_id}` 仅接受 canonical UUID 路径、当前 `plm_session` Cookie 与可信 Host/Origin；不接受查询参数或请求正文。服务端重验真实 Session、License、当前 Project member 和同项目 Section。匿名/失效 Session 返回会话错误；无成员、暂停成员、跨项目或不存在资源按 404 隐藏；License 拒绝 403。未知内部失败不向调用方暴露数据库细节。

成功返回 `data` 与 `trace_id`；`data` 仅含 `solution_section_id`、`solution_outline_id`、`project_id`、`section_key`、`section_state`、`current_approved_version_ref`、`created_by`、`created_at`、`etag`。Header 提供同值强 `ETag`、`Cache-Control: no-store` 与 Trace ID。若批准指针非空，Owner 必须复验指向同 Section/Project、APPROVED 且具有 Review/ReviewRound 双引用；不返回未审批正文、Requirement 映射或 AI 建议。Section 身份读取不代表完整方案交付。

仅通过显式 `create_app(solution_section_read_router=...)` 注入；默认应用 404，Windows 显式平台组合由后续 WBS 接入。无 Schema、Migration、依赖或冻结 `/api/v1` Breaking Change。回滚为停止注入可选 Router，Section 历史保留。
