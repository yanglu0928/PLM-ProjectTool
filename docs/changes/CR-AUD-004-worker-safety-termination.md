# CR-AUD-004：审计Worker安全终止与失败追溯

日期：2026-09-26；状态：RECORDED_UNDER_CONTINUOUS_AUTHORIZATION / TERMINAL_OWNER_INTERNAL_VALIDATED / REMAINING_LIFECYCLE_PENDING。
来源：P03-A07-P04-P02失败会保留RUNNING/private字节；当前业务授权拒绝后不能再调用capture/render/publish，通用Jobs retry_or_fail自有UOW不能与Owner失败Audit原子提交。原64cdf09/原权限/License保留，不追写。

比较：撤权/License拒绝后继续业务以完成任务，拒绝；仅等租约到期会重复失败及丢失当前失败追溯，不作为最终方案；采用固定安全终止Owner与Jobs专属caller-UOW失败Port。安全终止不是业务授权例外：不得读取正文、render/publish/恢复成功、延长Lease或修改已成功历史。

拟定Owner边界（实施前还须完成正式基线对应约束核查）：受控SystemActor每次真实来源→原Root/acceptance/pair固定源→当前代/Worker/Lease或真实取消来源→同UOW失败/取消技术转换与最小SYSTEM Audit。原User仅历史original_actor，已停用用户或License拒绝不能保活/发布，但不能阻止仅终止未成功任务。Admin无项目旁路；不接受浏览器/插件/自由路径/自由错误正文，不能从裸UUID猜Root或授予系统业务角色。

错误政策需Owner明确固定：授权/License/上限等终止、可恢复基础故障限次retry，停止超时仍活跃的线程不能提前转换或重试；当前代已过期/被接管则不允许旧Worker改状态，取消只走既有首申请历史/确认/到期恢复，不造新申请。技术Port本身不选择业务retry策略或校验Audit权限。

偏差影响：内部安全终止的授权边界需单独实现/测试，原业务当前权检查不放宽；无新增DB/API/角色/权益/技术栈。旧文件和失败尝试永久保留，不删除/回填历史，不修改原冻结API。Rollback撤未装配终止Owner，保原技术状态/审计/字节；不复活FAILED/CANCELLED。

验证计划：先Jobs原pair/current lease失败Port及caller整UOW回滚，再实际Owner受控identity与最小Audit；User/角色/License撤销、取消/过期/接管/成功拒改、同事务Audit故障回滚、确认丢失源核验。实际独立库/临时Vault/文件；正式材料/三平台/网络停机/质量/Gate/可用包仍待。不以CR记录或技术PortPASS宣称Owner政策已生效。

实施前基线复核（P02）：已读取总控V1.1、实施方案V2.1、ADR010及冻结API02强制Audit边界。V2.1 §3.5/License当前权限禁止业务操作；API02要求导出失败Audit与状态同事务。新增仅内部安全终止，不属于License业务恢复面、不新增HTTP/角色或客户事实，不调用现有当前权限业务入口。原授权链/成功发布不改。此处为可追溯安全边界补充，按持续授权接受，不回写64cdf09。

P02首先实现固定不可重试原因AUTH_ACCESS_DENIED/RESOURCE_NOT_FOUND/LICENSE_OPERATION_DENIED/AUDIT_EXPORT_LIMIT_EXCEEDED/AUDIT_EXPORT_CONTENT_UNAVAILABLE的当前活代FAILED及SYSTEM审计；瞬时错误retry、取消、到期恢复、丢失提交确认独立待验。要求与执行器相同Supervisor的短事务静止锁防止本实例心跳重启；该锁不是多进程全局证明，其他进程靠真实Job/fence/Lease拒绝。调用者只能在主执行同步I/O已返回后调用；不会自动终止线程或磁盘I/O。已有成功/取消/过期/新代均拒绝且审计回滚。

实施证据：P01 caller-UOW技术Port及P02终止Owner/静止锁已真实PG/临时Vault验证（详细进度/ADR011）；1004后端无失败（2环境跳过），开发wheel成功。撤权业务拒绝保持、最小SYSTEM失败Audit同事务、所有后置故障回滚/旧代终态拒改。仅终止Owner内部通过，剩余取消/瞬时retry/提交确认丢失及主循环未通过；不把CR整体或Gate标PASS。
