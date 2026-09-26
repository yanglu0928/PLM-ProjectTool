# ADR-011：审计Worker终止不是业务授权

日期：2026-09-26；状态：ACCEPTED_UNDER_CONTINUOUS_AUTHORIZATION / TERMINAL_OWNER_VALIDATED。

## Context / baseline

V2.1 §3.5与冻结API02禁止撤权/无效License业务操作，且导出失败属于强制Audit。原64cdf09、ADR010和当前授权链保持；CR-AUD-004记录安全终止边界补充。若复用业务授权则撤权任务不能终止；若略过授权继续正文读取/发布则越权，二者均不选。

## Decision

只新增内部安全终止Owner：主同步操作返回、同Supervisor静止锁拒活线程/阻止重启，真实受控SystemActor→原Root/acceptance/pair→最小SYSTEM Audit→再次identity→Jobs owned actual当前活代失败最后→同UOW commit。原User只作historical original_actor，不授系统User/Role，无公开HTTP、无新License恢复面，不read/capture/render/publish/recover-success/heartbeat。五个固定终止原因，不接受异常正文或自由retry。原三次尝试限制及业务授权不变。

## Evidence / boundaries

P04-P03-P01技术Port与P02 Owner实际PG/Vault验证：两Scope撤User/角色/License业务拒绝仍能终止一条SYSTEM审计，后置Audit/状态写故障和identity丢失回滚；成功/取消/过期/接管旧代拒改，私有字节不变。真实线程静止/停止超时/重启互斥unit、真实受权心跳活跃拒终止。1004后端无失败（2环境跳过）、开发wheel成功。

静止锁只限同实例，不强杀线程/磁盘/网络，不是跨进程全局协调；真实Job/fence/Lease保护其他进程。接入执行器必须使用相同Supervisor并先返回同步I/O。瞬时retry、取消Owner/到期恢复、提交确认丢失原源核验、调度/正式信任源/发行仍未完成。

P03补充实测：提交确认丢失原源核验已通过内部证明；真实PG actual commit后raise，再核验Jobs owned当前FAILED/RELEASED Lease/Attempt与Audit owned唯一SYSTEM事件、固定原pair/原因/时间。多次无写，缺错重复审计拒绝；1008无失败（2环境跳过）。仅此核验子项完成，自动执行器/取消/retry/发行未完成，不覆盖前段历史状态。

## Migration / rollback / Trace

2026-09-27/P05：重试并非撤权安全终止例外，必须当前原User业务权限前后通过；同Supervisor静止/SystemActor/原pair与当前活代的最小SYSTEM Audit同UOW。仅固定AUDIT_UNAVAILABLE，5/15秒退避，总三次；第三次FAILED，旧字节/尝试保留，新代重新授权。真实PG/Vault两Scope真实等待/新代新文件/回滚与拒绝矩阵、1037后端无失败（2环境跳过）/wheel通过。确认丢失/执行器/主循环及发行仍待，不修改前段仅终止Owner的历史边界。

无Schema/API/依赖；撤未装配Owner保留状态/审计/字节，不复活失败或成功历史。Trace：V2.1 §3.5/API02强制Audit→P04-P02失败保留RUNNING→CR-AUD-004→P04-P03-P01/P02证据。接受及局部验证不等于Gate或可用安装包通过。
