# User状态命令实现增量（CR-AUT-006）

2026-09-27 / 0.1.0.dev0 / INTERNAL_ATOMIC_VERIFIED_HTTP_PENDING。

原冻结64cdf09与AUTH_USER_ENABLE/DISABLE合同保留；当前仅内部服务，不宣称公开路由已实现。

- 当前DeploymentAdmin Session、CSRF及License每次验证，重放也不例外；不接受客户端actor/count/proof。
- 目标强资源版本参与命令，真实转换递增一次。新Key对已目标状态返回状态冲突，旧版本返回版本冲突；同Key不同目标或版本返回幂等冲突。
- 同Key返回不可变首次安全UserView，不使用当前GET代替；目标后来再启用、停用或改名不改变首次快照。提交后确认丢失可用原请求和Key恢复；仍要求当前有效权限。
- DISABLE撤销全部尚未撤销Session，包括过期会话；旧撤销记录不覆盖。ENABLE不能复活旧会话；身份、角色、凭据及创建历史保持。
- 最后启用Admin受保护。有其他启用Admin时支持自行停用；仅首次执行使用绑定本次原身份与实际撤销的专用末核，重放不绕过当前认证。
- 私有first含审计/actor/trace及撤销计数，不因此自动成为公开响应字段；未来HTTP必须按冻结安全UserView合同取字段，不泄露Token、摘要、凭据或内部坐标。

验证证据：`docs/progress/aut-04-a11-p03-user-state-atomic.md`。下一任务单独实现HTTP输入、响应、错误映射及自停用Cookie行为；Windows/UI/性能/正式信任与安装包未完成，无本轮Migration或依赖变化。
