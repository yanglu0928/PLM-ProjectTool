# 项目Job协作取消Contract增量

2026-09-27 / JOB-02-A04，原冻结API-01/03与64cdf09保留，无Breaking路径/角色变更。可选 `POST /api/v1/projects/{project_id}/jobs/{job_id}:cancel`，不新增JOB_ADMIN_CANCEL。默认create_app未注入Router仍404；只挂本取消Router时Admin404，已有Job GET同挂时未知Admin POST因原动态GET路径匹配而405，均无取消写入口。Windows写组合本项尚未接线。

请求：可信Host/Origin，唯一严格Cookie plm_session、X-CSRF-Token、Idempotency-Key；强If-Match映射expected_version，缺失428 CONFLICT_VERSION_REQUIRED，弱/多值/通配/畸形400，实际旧版本409 CONFLICT_VERSION。Content-Type application/json（可charset=utf-8），最多8192 bytes UTF8严格JSON，唯一reason字段（trim1～1024字符、禁止控制字符）；重复/未知/非标准常量拒绝400，原因值非法422。禁止客户端传Owner/Scope/export_id/路径。UUID零值404，其他非规范UUID按通用422；非空query400。

处理：HTTP先当前Session-CSRF；Jobs Application再次当前License/Session，Jobs owned只读hint按显式(owner,type)分派，PROJECT/path一致。hint不是权限/租约证明，事务关闭后由Owner在原实际写事务完整再授权、Root/acceptance/Job/pair/版本绑定。当前仅Audit Owner；未知Owner404不回退。原Creator-or-PM策略，IM可读他人Job元数据但无取消权，Admin无项目通配权；原Owner证据与0044首次版本必须存在。

响应200：Envelope `data={job_id,state,changed,etag,status_url}` 与本请求trace_id；state为首次CANCEL_REQUESTED/CANCELLED/SUCCEEDED/FAILED，changed为原首次是否发生转换；etag与HTTP ETag均首次真实 `"vN"`，不拼当前version；Cache-Control no-store/nosniff。当前GET由status_url取得，Worker确认使当前v3而原请求v2时重放仍原state/v2；同Key改理由/版本409 CONFLICT_IDEMPOTENCY，无新写。trace_id仍当前请求，并非旧Audit trace。

重放总需当前权限。旧内部收据缺首次version返回静态503 SYSTEM_UNAVAILABLE，不能回填猜ETag；应用内部历史不删。401过期Session、403 Origin/CSRF/License、404无权/跨项目/来源不存在/未知Owner、409版本/指纹冲突、422输入、503未知/DB/缺可信版本；异常无SQL/路径/原因/Secret/traceback。合作取消不回滚已发布副作用、不复活历史。

证据：5单位+5Contract，Windows11后端1177无失败/2既有权限跳过；真实PG-ASGI PM/当前Session-CSRF/Audit Owner、PENDING取消v2、同KeyHTTP并发单次/实际Worker确认当前GET v3与原重放v2、拒绝十一表无写、实际快照insert后故障回滚与分派后撤权Owner写UOW拒绝。原A03 migration/快照与发布回归通过。License为合成/Worker身份实际临时Vault，非正式材料/性能/三平台/全Owner/监听服务/浏览器/包/Gate证据。无本轮Migration/依赖，需0044，撤可选入口回滚保历史。
