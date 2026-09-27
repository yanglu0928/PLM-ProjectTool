# User管理详情运行Contract

2026-09-27 / AUT-04-A02；冻结API-02/64cdf09保留。可选GET `/api/v1/admin/users/{user_id}`，默认404/Windows暂未挂。

可信Host、唯一合法plm_session Cookie、当前有效Session，然后同UOW当前ENABLED DeploymentAdmin与License；不要求GET CSRF、不续Session、不写Audit/receipt。无管理权或未知目标404，Session过期/撤销401、Host/License403、query400、零UUID404/畸形UUID422、未知异常503 SYSTEM_UNAVAILABLE静态。

成功data仅user_id、username_display、account_state、deployment_role、credential_version、created_at、updated_at、etag及Envelope trace_id。禁止canonical用户名、CredentialID/hash/算法参数/密码、Session/token/CSRF、retention。目标DISABLED允许Admin管理读取，目标启用不是访问授权条件。ETag来自User lock_version，不是credential_version；UTC timestamps、no-store/nosniff。If-None-Match不绕实时权限，当前实现返回200真实状态，不承诺304缓存。

5契约测试+真实PG权限/版本分离/拒绝五表无写、1258无失败/2既有跳过；正向License合成，非正式供给/Windows/列表/管理写/性能/完整包证明。无Migration/新依赖/角色/Breaking；回滚撤router保历史。
