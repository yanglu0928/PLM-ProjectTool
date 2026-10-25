# P06-P13-P05：耗尽扫描明确坏来源隔离

2026-09-27/Phase2，CR-AUD-005。编码前：Jobs耗尽扫描/Application DTO，Audit Sweep/Exhaustion内部只读原源检查与Step；无Schema/API/权限/依赖变化。前置常规准入隔离、真实死锁矩阵已通过。

冲突：旧耗尽扫描仅首候选，损坏export_ref会抛错且SWEEP先于普通CLAIM，阻塞整个循环。选择新增独立expiry/JobId技术游标与只读scan_next，旧peek/run默认保留；后台明确开启isolate_sources，固定引用错/Root缺失/原Acceptance或pair明确不一致可技术拒绝、向后推进，不改耗尽Job/Lease/Attempt/Audit。正常候选仍原Exhaustion expire/verify安全Owner最终重核，提交后异常仍真实原源证明，不猜成功。

原源预检在Owner公开内部方法中完成，当前identity前后、原Root/Acceptance/Jobs完整pair锁，只有固定reason可拒绝；全局DB/identity/期限/Lease不一致继续失败关闭，不以预检授终态权限。游标只保一个，当前末尾/成功收口清除；Step遇Sweep拒绝后让下一轮优先Claim，Loop正常poll/计数，原STOP/pending排空保留。

验收：类型/来源/未知故障/identity/原证明unit；真实双Scope第三次到期候选引用损坏/缺Root时六表无写拒绝、正常新任务实际发布、坏第三代原行不动，恢复来源后原安全失败/commit确认仍通过，旧字节保留。无生产Migration/升级；回滚撤新Port/显式接线保原历史。长期公平/复杂Lease/Acceptance真实审计故障/正式材料/Gate仍待。

结果 INTERNAL_EXHAUSTED_SOURCE_SUBSET_PASS：新增expiry/JobId严格Cursor/只读scan，旧peek与run_next默认保留；后台显式模式只保常数cursor/实例锁、固定拒绝DTO，Sweep拒绝后下一轮优先Claim。Owner.inspect_source在当前identity与Supervisor静止下只读重核原Root/Acceptance/pair，未知异常脱敏并失败，不授expire权；仍原expire/verify收尾与确认恢复。

5新unit/1130后端通过（2既有权限跳过）。真实PG双Scope6场景，第三次actual到期候选malformed ref/ROOT_MISSING/PAIR_MISMATCH核精确reason，Loop拒绝六表无写，后续健康Job实际SUCCEEDED，坏Job/Lease/Attempt全行保持原值；恢复本轮合成来源后原Exhaustion actual Audit/终态/commit-lost-ack真实证明与旧stage字节保留。原发布回归与P12-B02真实Windows CLI子进程双Scope/缺公钥及idle无写/外部active停止单次排空通过。正式License仍测试替身，不提升生产结论。

开发wheel635109 bytes，SHA256 `54caec21777de5aca566beb853e2abaece2d915f4f6e783455aebf26d41e6f5d`。无Migration/API/依赖/升级；长期混排公平、Acceptance真实审计矩阵/复杂Lease/预检竞争变化仍待，CR-AUD-005不关闭。下一P13-P06持续循环混合队列/Acceptance实际分类收口，完整Scope/正式来源/SCM/其他平台/安装包/Gate仍待。
