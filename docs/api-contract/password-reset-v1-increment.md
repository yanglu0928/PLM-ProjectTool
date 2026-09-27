# AUTH_USER_RESET_PASSWORD V1 实施增量

来源：冻结API02/64cdf09、CR-AUT-007、DEC-20260927-322。原冻结保留。可选POST `/api/v1/admin/users/{user_id}:reset-password`，S/L/C/I/M/A；当前正常Admin、License、CSRF、幂等、强If-Match和Audit均由原子Service实施。默认应用404，Windows组合另项。

可信Origin/Host，唯一Session Cookie、CSRF/Idempotency-Key；禁止query。If-Match仅强`"v0"`或规范`"vN"`：缺失428、格式错误400、当前版本冲突409。目标非零UUID。唯一application/json，最多16384 bytes，严格UTF8/JSON，拒绝重复键和非标准常量。对象仅`temporary_password`字符串及`must_change_password`严格true；密码UTF8 1～1024 bytes、非NUL、不trim/normalize，write-only且缓冲finally擦除。

200正文data仅credential_version；ETag为首次结果User版本，不是凭据版本，历史重放保首次ETag而非最新版本。当前请求trace、no-store/nosniff。不得返回密码、Hash、Credential ID、KDF、Cookie/CSRF秘密。disabled目标保持停用；self允许，首次明确旧Session失效才删除安全Cookie。其他目标和正常Admin新认证历史重放不清Cookie。

重放需当前正常Admin/License/CSRF、原Key、原expected及原临时密码，与当次不可变新Credential实际Scrypt验证；后来改密不改变首次响应。旧及受限Session不授新管理写；self需临时登录后完成本人改密、再正常Admin登录恢复原Key。参数/密码差异409，权限/未知目标统一404，License403，输入422，未知错误固定503 SYSTEM_UNAVAILABLE。

提交或末读503不得猜测回滚、盲换Key或复活旧Session；以当前正常Admin认证恢复原请求。真实PG/Scrypt-ASGI、Audit回滚及self提交后末读503恢复已验，详见A06 progress。Windows/browser/性能/正式信任/三平台/发行未验；无新Schema/依赖或破坏性API变更。
