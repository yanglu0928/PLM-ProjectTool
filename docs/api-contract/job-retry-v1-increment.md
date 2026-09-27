# 任务受控重试运行Contract增量

P05-B（2026-09-27）：真实PROJECT/GLOBAL Document上传Commit来源经Windows当前Owner读取后，retry精确409 JOB_NOT_RETRYABLE、20表全行无写；不假支持Parser重试。实际第三Attempt技术fixture非临时分类false/409，完成时间与Job/Lease不一致静态503 SYSTEM_UNAVAILABLE；恢复原事实true。creator实施/客户角色false且retry404，noncreator客户GET/retry404；归档PM维护例外实际新generation→Worker成功。1247无失败/2跳过/旧混排发布回归；P05内部完成，正式信任合成，非性能/三平台/完整包/Gate。下文P05-A/P04为历史。

2026-09-27 / P05-A更新：Windows显式platform-write现挂上述双retry；默认/login不挂，platform只读GET使未知POST405。写模式Audit FAILED详情/列表只有当前PM Export或受权DEPLOYMENT Admin、原第三临时失败来源及版本一致才retryable=true；非FAILED/未注入Source/非PM/已知JOB_NOT_RETRYABLE为false，坏源/版本不一致静态失败，不伪装false。归档沿冻结Audit Export维护例外。提示不是写许可，命令仍在写UOW重新核授权/CSRF/License。实际双ScopeFactory→新Job→Worker成功/重放及旧混排通过，1247无失败/2跳过；正式信任合成。P05-B真实Doc409/坏源metadata/完整角色矩阵待；以下P04为历史，不覆盖本更新。

2026-09-27 / JOB-03-A02-P04 / CR-JOB-006；原API-01/API-03冻结64cdf09保留。

- 可选POST `/api/v1/projects/{project_id}/jobs/{job_id}:retry` 与 `/api/v1/admin/jobs/{job_id}:retry`。默认未注入router404；Windows本项未挂，已有动态Job GET时未知POST可能405，不表示有重试命令。
- 严格可信Host/Origin、唯一plm_session/X-CSRF-Token/Idempotency-Key和强If-Match。空JSON对象`{}`，Content-Type application/json可charset=utf-8、最多1024bytes；未知字段/重复键/NaN/非UTF8/非空query400。客户端不能提供Owner/Scope/export_id/payload/路径。缺IfMatch428，弱/通配/多值400，陈旧409。UUID零404/畸形按通用422。
- HTTP和Jobs再验证当前Session-CSRF/License，现安全Job详情原源/Project/Admin隔离后显式Owner分派；read/hint不授权写，Owner写UOW再次完整授权/原源/强版本。当前Audit受其Owner PM export/DEPLOYMENT Admin规则约束，不借泛Job Creator规则扩大权限。未知/隐藏404；已受权注册而无用户retry实现（Document）409 JOB_NOT_RETRYABLE，目前Doc拒绝为unit证据，实际混合Owner运行待P05。
- Audit只原第三Attempt真实AUDIT_UNAVAILABLE终态FAILED可新generation；其余已成功/取消/不可重试配置/签名/越权等不复活。新Key新一代、同Key原响应，SourceJob/query/expected_version改变同Key409 CONFLICT_IDEMPOTENCY。新任务固定原spec窗口重新采集，不复用旧捕获或承诺同字节。
- 202 Envelope：data={job_id（新）,source_job_id,scope,project_id,state:PENDING,etag:"v0",status_url,accepted_at}及本请求trace_id。ETag及Location对应首次新Job/no-store/nosniff；无内部Export/Audit/Event/Lease/正文。首次created_at是不可变generation受理快照，即使新Worker已成功，重放仍PENDING/v0；当前GET另取真实状态和ETag。
- 当前权限重放仍必须满足。Session401、Origin/CSRF/License403、无权/错Scope/未知404、版本/幂等/不可重试409、输入422、未知/DB/坏源503静态，无SQL/Secret/路径/traceback。
- 证据：5Contract+5Dispatch Unit及真实双ScopePG-ASGI第三Worker失败→HTTP新Job→现Worker文件成功→当前GET vs 首次响应重放、拒绝十五表无写。1239后端无失败/2既有权限跳过、wheel681969；正向License合成，非正式材料/其他Owner完整权限/Windows运行/性能/三平台/完整包/Gate。
- 无Migration/依赖/角色/Breaking路径，head0045；回滚撤可选Router/Adapter保历史。公开metadata retryable仍False，下一P05运行/安全投影接线。
