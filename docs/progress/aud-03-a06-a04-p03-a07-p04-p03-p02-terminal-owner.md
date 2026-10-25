# P04-P03-P02 安全失败终止Owner

日期：2026-09-26；状态：TERMINAL_OWNER_INTERNAL_PASS / LIFECYCLE_WIRING_PENDING。

编码前检查：Phase2；WBS P04-P03-P02，输入CR-AUD-004/V2.1 §3.5/API02强制Audit/ADR010及Jobs P01。前置实际原Root/acceptance/pair、受控SystemActor/当前Lease/周期协调已验证。涉及Audit Application与其心跳静止锁、既有Job/Lease/Attempt/Audit，无Schema/HTTP/依赖。权限仅受控内部安全终止，不读正文、不允许延长租约/发布成果/恢复成功；原User为historical original_actor，License/用户撤权不阻止终止。

单问题：固定不可恢复失败原因、相同Supervisor确认实际无线程且锁住重启→当前SystemActor→原Root/acceptance/pair→最小SYSTEM失败Audit→第二次SystemActor→Jobs actual原pair/current alive generation技术FAILED最后→commit。原成功/取消/过期/旧代拒改；错误或Audit/identity后置失败整体回滚。锁只证明本Supervisor心跳静止，主同步I/O应先返回；不是任意并发线程的强杀或全局协调。

验收：严格原因/命令、活线程/停止超时拒绝、guard持有期间重启被阻止；真实PG/Vault双Scope实际撤权/License拒绝后终止仅最小SYSTEM Audit无成果/正文读取，Audit写后故障/后验identity丢失整UOW回滚，旧代/成功/取消/过期无写。未接runner/主循环/公开POST；瞬时错误retry、取消与提交确认丢失留下一项。

Changed/Files：`worker_termination.py`、`heartbeat_coordinator.py`短静止锁、6新unit、独立真实PG验证脚本、CR-AUD-004/ADR011及本记录。无Migration/API/依赖，head0042不变，原冻结/业务授权不改。

Tests/Result：6新unit、完整1004项无失败（2既有符号链接账户权限跳过）。实际独立PG/临时Vault两Scope各5原因：真实User/角色/License撤销仍拒业务，但受控identity同UOW终止唯一SYSTEM失败Audit，正确original actor/trace/Scope/reason/前后状态；私有stage保留、Result/File无写。真实Audit插入后异常、技术转换全部写后异常、第二identity来源故障都整体回滚；成功/取消/实际过期/真实接管旧代/错Worker/fence/Root无写。实际受权周期线程活跃拒绝终止，真正停止后才允许；原发布空/260回归通过。不声称新Owner有并发publish竞争证明（原发布已有独立竞争验收）。

测试首轮Mock assert方法未声明spec、误用user_state字段失败，均修正为实际合同并从新库完整重跑；模块导入测试类导致重复发现亦改模块引用。开发wheel 588612 bytes，SHA256 `4b19880595f146bfa2da56cc5e08775b5d07cfa89eff7c958c770561bfa00da5`，仅开发库非安装包。

Known issues/Next：实际失去SystemActor拒绝不产生状态写，需正式供给恢复；未接单次runner/故障政策、瞬时retry、取消Owner、提交确认丢失核验、claim主循环/重启/POST。生产材料/三平台/网络/质量/Gate/完整程序包待。Rollback撤未装配Owner、保历史，不复活终态。下一项先失败提交确认丢失原源只读核验，再取消/执行器安全接线。
