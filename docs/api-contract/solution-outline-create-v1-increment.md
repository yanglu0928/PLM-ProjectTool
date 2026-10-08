# SOL-02-A04：SolutionOutline CREATE HTTP 增量合同

日期：2026-10-09；细化 Gate 2 冻结 API-04 `SOL_OUTLINE_CREATE`，不修改原冻结提交或增加资源种类。

`POST /api/v1/projects/{project_id}/solution-outlines` 仅接受路径中的 canonical ProjectId、当前 `plm_session` Cookie、可信 Host/Origin、`X-CSRF-Token`、`Idempotency-Key`；正文恰为 `{"name": string}`，不接受 actor、project/scope、批准指针或版本。重复/未知 JSON 键、查询串、非 JSON 与超限正文拒绝；名称由 Owner 按 NFKC、去首尾空白、1..500 字符并排除控制字符。PROJECT_MANAGER/IMPLEMENTATION_MEMBER 的有效项目写授权在同一事务重验；客户角色、失效身份与跨项目隐藏为 404，归档项目拒写。

首次及同 Key 同载荷重放均返回 201，`data` 仅含 `solution_outline_id`、`project_id`、规范 `name`、`outline_state=ACTIVE`、`current_approved_version_ref=null`、`created_at` 和 `etag="v0"`；Headers 有同值 ETag、固定详情 Location、`Cache-Control:no-store` 与 Trace ID。重复 Key 异载荷 409；不返回 Session、CSRF、内部错误或客户正文。创建逻辑身份不等于 DRAFT/Approved OutlineVersion，也不使任何 Solution Checklist 通过。

此路由只通过显式 `create_app(solution_outline_create_router=...)` 注入；默认应用/现有 Windows 生产组合仍 404。Location 所指详情 GET 尚未装配，A05 只做 Windows 显式 CREATE 组合，详情读另立 WBS，不把 201 视为 GET 已通过。迁移仍是 A03 的 0146，本项无新 Schema、依赖或数据迁移。回滚为停止注入此可选路由，历史目录和 Audit/Receipt 保留。
