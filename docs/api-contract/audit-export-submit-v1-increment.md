# Audit导出提交运行Contract增量

2026-09-27，AUD-03-A07-P01；原Gate2/API-02 AUDIT_EXPORT/64cdf09保留。可选POST `/api/v1/projects/{project_id}/audit-exports` 和 `/api/v1/admin/audit-exports`，角色原PM/Admin，S/L/C/I/A，短事务只接受并登记，不执行长任务/文件I/O。

Origin/Host严格受控，Cookie plm_session及X-CSRF-Token各唯一32字节hex，Idempotency-Key使用原公共语法/上限；当前Session预验证后Application同事务重新检查Auth/角色/Project/License。项目路径绑定PROJECT，admin固定DEPLOYMENT，不接受客户端scope/project_id/请求actor/格式/存储位置。actor_id/trace_id字段仅Audit搜索过滤，不是执行主体或请求Trace。

body：UTF8 application/json（可charset=utf-8）、流式8192字节上限，唯一key对象，拒绝非标准常数/递归过深/未知字段。必填purpose、start_at、end_at；可选action、outcome、actor_id、target_object_type、target_object_id、trace_id，可选null等同不筛选。start/end为aware RFC3339含时区，最多6位小数、UTC归一、start<end且最多31天；UUID过滤必须规范小写非零；purpose按原EXPORT_PURPOSES且DEPLOYMENT不可PROJECT_GOVERNANCE。无SQL/JSONPath/raw payload输入。

202 Envelope data为export_id/job_id/state=PENDING/status_url，Location=status_url，no-store。state表示**固定首次受理快照**，不是本次重放时的实时Job状态；重放已成功/失败仍返回原202与同一refs，不新增/重启任务。实时状态和强vN由已授权status_url GET查询，终态不得复活。Project status_url按原路径项目/jobs/id，admin按admin/jobs/id。Trace_id为本请求Trace，原接受Trace保存不改。导出结果/下载另需重新授权，不能据此获取正文。

HTTP映射：畸形JSON/类型/未知字段/非空query/大小上限400 REQUEST_MALFORMED；scope/purpose/date/filter不符422 AUDIT_EXPORT_SCOPE_INVALID（原API-02安全码正式注册）；Key非法422，内容冲突409 CONFLICT_IDEMPOTENCY；缺/无效Session401，当前CSRF/Origin拒绝403，License403，无权限/跨项目404，DB/原源/未知异常503 SYSTEM_UNAVAILABLE。预验证后Auth撤销产生Service拒绝时404，不泄露目标是否存在；错误不含SQL/路径/原异常/Key/客户正文。

默认create_app与目前Windows工厂仍未挂载POST；可选audit_export_submit_router需配合原Jobs详情用于status_url，下一Windows写装配单独验证。不改Schema/依赖/冻结路径，仍需前序0043。证据：5新Contract+1155后端无失败/2既有权限跳过；实际PG/Session-CSRF/Submit/原Worker/JobGET双Scope202、原受理重放/冲突/权限/十业务表回滚、成功v2/终态重放不复活，原发布通过；明确合成License，非正式供给/20并发/P95/浏览器/安装包/Gate通过。
