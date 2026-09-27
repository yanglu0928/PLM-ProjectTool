# AUTH_PASSWORD_CHANGE V1 实施增量

来源：冻结API02/64cdf09、CR-AUT007、DEC315。原冻结保留；可选POST `/api/v1/auth/password:change`，当前本人普通或受限Session，S/C/I/A，无License/Admin/If-Match要求。

可信Origin/Host，唯一plm_session Cookie、X-CSRF-Token、Idempotency-Key；无query。唯一application/json Content-Type，最多16384 bytes，拒绝重复键/非标准常量；对象仅`current_password`、`new_password`，均write-only UTF8字符串1～1024 bytes，不含NUL，不trim/normalize密码。不接受UserId或Hash。

200：`data`仅`credential_version`，当前请求trace_id/X-Trace-Id，no-store/nosniff；不返回CredentialId/Hash/KDF/密码/Session/CSRF。首次转换撤销全部旧Session（包括当前和过期未撤销Session），明确旧Session失效时delete HttpOnly/Secure（HTTPS）/SameSite=Lax/path=/ Cookie；重新登录才能继续。

幂等历史恢复必须当前有效本人Session和原Key/原两密码；校验first前后不可变Credential实际Scrypt，不与最新Credential混淆。原Cookie失效时401；重新登录后历史重放200且保留新Cookie。差异409 CONFLICT_IDEMPOTENCY。

坏Origin/CSRF403，失效Session/授权竞争401，错误当前密码401 AUTH_INVALID_CREDENTIALS，畸形请求400/密码或Key422，未知服务/输出/提交后末读503 SYSTEM_UNAVAILABLE，无秘密和猜测回滚。503后重新登录，再以同Key原两密码恢复；不得盲用旧Session或创建新Key重做未知提交。

当前仅可选ASGI router，默认404，Windows生产组合尚未接线；浏览器UI、reset、正式来源/性能/三平台/发行未验，不代表完整Auth或Gate3。
