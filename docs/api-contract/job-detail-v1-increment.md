# Job详情运行Contract增量

JOB-02-A03（2026-09-27）首次版本前置已补：0044 append-only Audit取消版本快照，新JobId首次请求在原UOW保存实际lock_version；Worker确认推进后重放仍原state+原version。旧收据无快照保None，未来HTTP必须失败关闭，不能猜强ETag。冻结GET JobView不改，项目取消HTTP尚未挂载，Admin取消不自动新增；无本轮Breaking/权限变化，生产升级需0044备份维护门禁。

JOB-02-A02（2026-09-27）内部Audit Owner支持JobId同UOW原源解析，强制expected_version；原当前授权/受理/pair与export入口指纹去重保持。无公开HTTP。API-03取消仅状态结果，GET才完整JobView；但API-01更新强ETag/首次重放需补取消首次lock_version快照，不能当前version拼旧state。冻结只有JOB_PROJECT_CANCEL，内部DEPLOYMENT不等新增JOB_ADMIN_CANCEL，若需HTTP另CR；其他Owner/完整Scope保留。

JOB-02-A01（2026-09-27）内部前置更新：CR-JOB-003已补原Audit取消expected_version与锁内实际Job版本比较；显式版本绑定原持久指纹，同Key原命令重放返回首次结果且仍重验当前授权，过期新请求VERSION_CONFLICT整事务无写。None仅保留旧内部调用/指纹，未来公开If-Match映射必须显式提供版本；尚无公开取消HTTP/JobId受权Owner解析/完整响应，不能据本项宣称JOB_CANCEL或完整Jobs PASS。无新Migration/冻结API Breaking/角色变动；GET强vN保持。

JOB-01-A03（2026-09-27）装配更新：Windows --platform与--platform-write显式模式已接该详情Router、原当前授权和首个Audit Owner；默认与login-only仍404。实际PG/ASGI双工厂验证通过、正式信任源不可用时仍拒绝启动。前文“Windows尚未接线”为P02历史状态保留，完整Jobs Owner/正式账户/监听进程/浏览器/发行仍未完成。

2026-09-27 / JOB-01-A02-P02 / CR-JOB-001、002；原Gate2冻结64cdf09保留。实现原JOB_PROJECT_GET/JOB_ADMIN_GET，非新增Breaking路径、非完整Jobs模块交付。

GET `/api/v1/projects/{project_id}/jobs/{job_id}`：S/L/当前成员及Owner资源再授权，PM/IM可见受权任务元数据，其余角色仅原actor；路径ProjectId与资源必须一致。GET `/api/v1/admin/jobs/{job_id}`：当前DeploymentAdmin，仅DEPLOYMENT/GLOBAL，不包含项目Job。未知Owner/type或无权限与不存在同404。Admin不提供项目通配权。

响应Envelope `data` 与本请求 `trace_id`；data字段：job_id、job_type、owner_module、scope、project_id、state、progress、checkpoint、attempt_count、retryable、error_code、result_ref、created_at、completed_at、etag。时间UTC RFC3339；etag与HTTP ETag同为强 `"v<实际lock_version>"`，源自0043，不是Lease/fencing/hash。当前没有已验证细粒度进度/检查点/安全终态原因时相应字段null，不填百分比或透传Attempt异常。retryable是Owner用户重试策略，不是后台自动重试次数；Audit当前False，公开用户retry仍待。result_ref为 `{type: AUDIT_EXPORT, id: export UUID}` 或null，不返回物理File/路径/正文，不授下载权；内容下载须重新执行原Audit权限。

响应 `Cache-Control: no-store`、`X-Content-Type-Options: nosniff`；当前If-None-Match仍执行全授权并返回当前200或拒绝，不以304省略撤权检查。If-Match取消/重试尚未实现，不能据GET宣称已具备写并发控制。

无Query白名单（所有非空query拒绝400）。Cookie只接受单个严格plm_session，可信Host/可选Origin，零UUID404、畸形UUID按通用422；缺/失效Session401，License403，跨项目/无权/不存在404，来源/DB/其他错误SYSTEM_UNAVAILABLE503且不暴露SQL/路径/traceback。默认create_app仍404，仅显式job_detail_router可选挂载；Windows生产组合尚未接线。当前首个Audit Owner策略，Document等Owner接线后按完整Job合同验收，不取消其他Owner需求。

证据：tests/contract/test_job_detail_api.py与validation/job-01-a02-p02-http/verify.py，1150后端无失败/2既有权限跳过，实际PG8成功/13拒绝矩阵、只读业务快照及原发布通过。Windows11、合成License，非正式发行/20并发/浏览器/其他平台/完整UAT证明。无本轮Migration/依赖变化；需已升级0043。
