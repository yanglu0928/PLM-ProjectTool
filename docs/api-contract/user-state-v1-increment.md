# User状态命令实现增量（CR-AUT-006）

2026-09-27 / 0.1.0.dev0 / WINDOWS_INTERNAL_COMPOSITION_VERIFIED。

原冻结64cdf09与AUTH_USER_ENABLE/DISABLE合同保留；可选POST `/api/v1/admin/users/{user_id}:enable`、`:disable`已实现，Windows仅显式platform-write安装；readonly405、默认/login404，无默认公开写操作。

- 当前DeploymentAdmin Session、CSRF及License每次验证，重放也不例外；不接受客户端actor/count/proof。
- 目标强资源版本参与命令，真实转换递增一次。新Key对已目标状态返回状态冲突，旧版本返回版本冲突；同Key不同目标或版本返回幂等冲突。
- 同Key返回不可变首次安全UserView，不使用当前GET代替；目标后来再启用、停用或改名不改变首次快照。提交后确认丢失可用原请求和Key恢复；仍要求当前有效权限。
- DISABLE撤销全部尚未撤销Session，包括过期会话；旧撤销记录不覆盖。ENABLE不能复活旧会话；身份、角色、凭据及创建历史保持。
- 最后启用Admin受保护。有其他启用Admin时支持自行停用；仅首次执行使用绑定本次原身份与实际撤销的专用末核，重放不绕过当前认证。
- 私有first含审计/actor/trace及撤销计数，不因此自动成为公开响应字段；未来HTTP必须按冻结安全UserView合同取字段，不泄露Token、摘要、凭据或内部坐标。

HTTP要求空body/无query、可信Origin-Host、当前Session-CSRF、合法Idempotency-Key及强If-Match；缺版本428、格式400、状态AUTH_USER_DISABLED409、版本/幂等409、非Admin或未知目标404、无效Session401、CSRF/License403、未知故障503。成功200安全8字段/首次ETag/no-store/nosniff，响应trace使用当前请求而非历史trace。

自行停用实际使当前Session失效才清除同Path的Secure/HttpOnly/SameSite Cookie；新认证恢复历史first不清新Cookie。提交后确认/Session复读不可用不能推断未执行，应保留原Key及原If-Match；权限恢复后可原Key取首响应，另GET辨当前状态，不盲重试新Key。

验证证据：P03、P04及`docs/progress/aut-04-a11-p05-windows-user-state.md`。Windows实际组合通过，UI/性能/正式信任与安装包未完成，无本轮Migration或依赖变化。
