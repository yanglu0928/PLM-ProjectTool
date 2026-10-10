# AUTH_USER_CREATE V1 实现增量

2026-09-27 / CR-AUT-005 / AUT-04-A09-P04～P05；原冻结64cdf09/API02保留。`POST /api/v1/admin/users`可选实现，Windows仅显式platform-write挂载；platform只读GET-only405、default/login404。

请求仅`username`（显示名称）和write-only `password`，均字符串；不接actor/canonical/deployment_role/query。单JSON Content-Type、严格UTF8/重复key/非标准常量、16KiB body、密码UTF8 1～1024 bytes且无NUL；用户名用原NFC/strip/casefold规则。Origin/Host、有效Session/CSRF、Idempotency-Key、当前ENABLED DeploymentAdmin、License必需，无If-Match创建前置。

成功201 Envelope data固定`user_id/username_display/account_state/deployment_role/credential_version/created_at/updated_at/etag`；初始ENABLED/NONE/credential1/etag v1；Location为详情GET、ETag/no-store/nosniff，无Set-Cookie。密码/hash/algorithm参数/Session信息/canonical/内部credential或Audit坐标不返回。

scope当前actor+V1_AUTH_USER_CREATE+Key，非秘密指纹与原Credential1真实Scrypt密码一致性组合证明完整请求。每次重放须当前Session-CSRF/Admin/License；原201安全View和ETag不随当前User变动，trace_id为本轮，不复活停用账户或重写历史。

HTTP错误：401 AUTH_SESSION_EXPIRED，403 AUTH_CSRF_INVALID/ LICENSE_OPERATION_DENIED，404 RESOURCE_NOT_FOUND（非Admin），409 CONFLICT_DUPLICATE（用户名）/ CONFLICT_IDEMPOTENCY，400 REQUEST_MALFORMED，422 VALIDATION_FAILED，503 SYSTEM_UNAVAILABLE（来源/KDF/审计/事务故障含提交确认未知）。提交确认未知只能同Key重放取实际已提交首结果，不猜成功或改Key重建。

Schema0046/P03原子、P04真实PG HTTP、P05实际Windows写创建/真实新账户登录及只读关闭已内部验证，正向信任明确Synthetic；正式供给/性能/三平台/完整管理/最终包未完成。撤router接线回滚保原冻结/0046历史，无P05 Migration/新依赖/权限变化。
