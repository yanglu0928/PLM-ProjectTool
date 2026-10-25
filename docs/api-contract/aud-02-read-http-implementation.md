# Audit GET 实施说明（非冻结合同替换）

2026-09-26；来源API-01分页、API-02/AUDIT_PROJECT_LIST/GET与AUDIT_ADMIN_LIST/GET，DEC-20260926-188。原冻结提交64cdf09不变。

四个冻结路径仅显式注入create_audit_read_router时挂载。项目范围仅当前PM；部署范围仅当前DeploymentAdmin且只DEPLOYMENT，不隐式授予项目Audit。HttpOnly Session Cookie传入受权service，在同一事务重核；可信Host检查，GET不要求写操作CSRF。License失效拒绝，不属于恢复白名单。普通默认应用404，Windows正式组合尚未接线。

列表白名单：start_at/end_at、page_size、cursor、action、outcome、actor_id、target_object_type、target_object_id、trace_id。重复或未知参数400；非法筛选/非零UUID/时间/大小422。start_at/end_at须同时提供或均省略；ISO时间含时区且转UTC，`start <= event time < end`，最大31天。默认最近24h，page_size默认50/范围1..200；排序UTC时间、event UUID降序。省略日期续页使用签名原窗口，明确日期须与原窗口一致。详情不接受查询参数。签名绑定Actor/Session/Scope/全部参数，失效400；每页重新授权，不能作为加密或数据库快照。

成功外层data/trace_id，Cache-Control:no-store。列表data为items/next_cursor/has_more；详情为同一种安全事件。安全事件字段：audit_event_id、occurred_at、event_scope、project_id、actor(type/user_id/original_user_id)、action/outcome、target(owner_module/object_type/object_id/version_id)、summary(reason_code/before_state/after_state)、trace_id。summary仅校验过的code/状态，无自由正文。未resolved身份不包含hint摘要。无密码/hash/Session/Secret/文件/Prompt正文。缺资源/跨项目404，失效Session401、License403、异常503；响应不返回异常正文。

本项不实现AUDIT_EXPORT/Job/下载，不新增公开写操作，无Migration/角色/依赖或Breaking API变化。生产Audit专用key来源、恢复、显式组合及三平台验收另列后续任务。
