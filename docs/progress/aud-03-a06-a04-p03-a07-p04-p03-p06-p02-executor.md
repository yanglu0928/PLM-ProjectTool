# P06-P02 单命令执行器接线

日期：2026-09-27；状态：SINGLE_COMMAND_INTERNAL_VALIDATED / PROCESS_LOOP_PENDING。

编码前：Phase2/P04-P03-P06-P02；CR-AUD-004/ADR011，前置状态事实、周期心跳/RunOnce、成功恢复、终止/取消/retry与确认丢失证明均内部验。涉及Audit执行编排，不新增DB/API/依赖/角色/License面。

验收：同一真实Supervisor和安全Owner identity依赖；原Root/pair/实际facts选分支而非调用者state。当前RUNNING才执行业务RunOnce，成功必须真实已核验结果；失败后实际静止并重新读facts，取消优先、不改新代或成功。固定终止原因→终止+真实失败证明，白名单基础错误→retry+真实转换证明，确认丢失只原源核验；retry途中撤权只能在实际仍RUNNING活代时安全终止。已取消/失败/retry只读证明，不重复Audit；旧代只可返回已证明的历史retry收据。活线程/STOP_TIMEOUT不提前转换，未知错误/缺源/过期不可猜成功。alive ack到期竞争最多一次重读转严格到期恢复，不循环改状态。无claim循环/公开HTTP/文件清理/新业务旁路。

风险/回滚：执行结果属于该command代次，不代表当前Job永远维持该状态；源不可核验就保留错误不伪成功。撤未公开执行器保历史，不复活终态。真实双Scope新执行/重放/撤权终止/用户申请取消/到期/retry/确认丢失/错代/未知缺源验证，主循环/正式材料/质量/Gate/全Scope可用包仍待。

Changed/Files：AuditExportExecutor与严格代次绑定Outcome、unit、真实验证脚本及CR/状态/决策/版本记录。无Schema/Migration/API/依赖变化，0042不改，无生产升级，现有业务权限不放宽。真实当前facts和各阶段原源核验分别进行，hint并不授转换。retry等待期即时取消只改变当前Job，不重写原Worker的已完成retry收据；该旧command返回历史retry，不冒充leased取消ack。写入丢失确认先查原源，实际状态已变重新路由但不再执行业务或静默续租。

Tests/Result：13新unit，Windows11/Python3.13后端1060项无失败、2既有权限环境跳过。unit覆盖首成功/失败后真实成功优先/成功后撤权不改/终止与retry丢失确认/取消优先/ack期间到期最多一次切换/历史retry/停止超时无第二读或写/缺receipt/未知错误/重试授权拒绝仅仍RUNNING终止/不一致Supervisor拒装配。

实际PG18临时库/临时Vault、bounded WorkerDatabaseRuntime与同一真实周期HeartbeatSupervisor两Scope：新0/260行由未capture无文件开始实际成功、重放六表无写；实际User停用安全FAILED且无capture、成功后停用拒返回且六表无写；有首USER源活期/实际2秒到期/同步render中真实申请取消→确认完成；永久内容错误FAILED vs 基础故障RETRY_WAIT。SUCCEEDED/FAILED/CANCELLED/RETRY_WAIT四种均实际commit后raise返回故障，执行器按真实来源确认，重放不重复Audit。等待中即时取消保原retry收据，裸技术CANCELLED缺USER/SYSTEM源拒绝。原发布fixture回归通过；License仍合成，不能称正式发行信任锚验证。

开发wheel613434字节，SHA256 e83953bcf39524c0a1f42d8a4a5bea3039c162019dcdad4262cc7992e1906f6e，构建通过；不是可用安装包。没有新增真实网络断线/执行器并发竞争/生产账户/三平台发行，unit模拟竞争不冒充实际线程竞争。未完整验证claim→所有结果的主进程循环。

Known Issues/Next：P06-P03接实际Audit专属claim到命令适配，再主循环/受控CLI/公开Jobs HTTP。过期RUNNING和容量不足/未知非白名单仍报错，后续调度须安全处理，不猜成功或越权retry。正式材料/目标账户/质量/Gate/全Scope最终程序包待，持续交付目标active。
