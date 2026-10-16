# SOL-01-A04-P08-P06-P02：GLOBAL Reference Create 冻结操作实现细化

日期：2026-10-09。依据 Gate 2 冻结 API-04 与 CR-SOL-006/007/009/010；仅实现原已冻结 `SOL_REFERENCE_CREATE` 的 GLOBAL 展开，不修改 PROJECT 路径和已有字段。默认应用不装路由；Windows 显式组合、隔离 PG/文件和实际人工业务确认须分别验收后才可用于正式资料。

`POST /api/v1/global/reference-solutions` 要求当前 `plm_session`、可信 Origin/Host、`X-CSRF-Token`、`Idempotency-Key`、有效 License 与 DeploymentAdmin。请求正文恰含六字段：`name`、`document_version_ids`（有序 1～100 规范 UUID）、`evidence_ids`（有序 0～500 规范 UUID）、`source_project_class`、`deidentification_class`、`applicability`。不接受 query、body 中的 scope/project/actor/确认 ID、重复或未知 JSON 键，128 KiB 上限；原文、绝对路径、客户端 SHA 均不可作为证明。

服务端 Owner 在创建写事务内逐个核验 GLOBAL 固定文档文件摘要与当前 Evidence 资格，计算整个有序来源集合指纹，并按该指纹寻找最新有效、未撤回的人工确认；分类/适用性须一致。缺确认、已过期/撤回、来源或权限变化均失败关闭，不以客户端提交的 ID、预览结果、AI 建议或脚本勾选代替人工确认。当前 Admin、CSRF、License、幂等、Reference 初版/来源引用、确认绑定、Audit/收据由现有原子 Owner 负责。HTTP 只投影其安全结果，不返回确认 ID 或客户正文。

成功 `201` 使用 API-01 信封 `data` + 当前请求 `trace_id`，`data` 为 `reference_solution_id`、`reference_version_id`、`scope:"GLOBAL"`、`project_id:null`、`name`、`eligibility_state:"REFERENCE_ONLY"`、`version_state:"DRAFT"`、`created_by`、UTC `created_at`、`etag:"\"v0\""`；响应头含同一 ETag、`Location:/api/v1/global/reference-solutions/{id}`、`Cache-Control:no-store`。首次 201 只表示引用创建，不等于正式方案审核通过或当前来源永远有效。错误遵循现有 API-01：请求畸形 400、Session 401、CSRF/Origin/License 403、权限或来源缺失 404、非法字段 422、幂等冲突 409、来源/系统不可用 503；不透传异常栈或来源正文。

本任务仅将路由作为可注入依赖接入 `create_app`；未在 Windows 生产组合挂载，默认请求仍 404。P06-P03 必须用隔离 PG/文件验证成功绑定与缺/撤回/过期确认等负例；P06-P04 再审核显式写模式和目标账户信任源。无 Schema/依赖或数据迁移，回滚关闭新增路由并保留已有确认/Reference/Audit/收据历史。
