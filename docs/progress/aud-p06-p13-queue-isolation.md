# P06-P13-P01：队首锁与坏源隔离证据

2026-09-27/Phase2，CR-AUD-004/P12-B02已通过内部验证。编码前：本项只验证Jobs/Audit既有调度，不改API/权限/实体/Schema/依赖。验收为确定当前行为及修复输入，不是声称公平/隔离PASS。

检查证据：ClaimAdmission先读取Audit原Root再queue.find_export；后者advisory锁、Job/Outbox FOR UPDATE，在claim_target SKIP LOCKED前已经可能阻塞。peek仅一个候选，payload UUID错误直接异常，不能查看后续正常任务。计划在实际PG临时库先锁住优先队首，验证有界真实55P03退出/无claim/正常第二任务仍PENDING；再损坏本轮合成队首payload，验证同样无claim，恢复原payload后两任务正常发布，保留客户/生产来源不碰。

候选方向：不得以过滤坏UUID冒充完整隔离；需要所有来源核验错误、真实锁竞争及全局DB/身份错误分类。不得自动把坏源标FAILED/猜成功、修改优先级或跳过授权。具体可追溯修复在CR-AUD-005中记录后实施，无需普通批准；Gate仍待客观验证。

结果 EVIDENCE_CONFIRMED / FUNCTIONAL_ISOLATION_FAIL：真实PG18当前Schema临时库，优先队首被独立事务锁住，实际生产有界Loop抛错链中SQLSTATE55P03；六表无写，后续合法任务未领取。恢复锁、损坏本轮payload后再无写退出，第二仍PENDING/0Attempt；恢复原payload两轮真实执行/发布双方SUCCEEDED，原发布空/260、并发与失败回滚回归通过。没有生产代码/API/Migration/依赖改变，未重复声称全部unit或wheel复验。后续修复已先登记CR-AUD-005；本脚本在修复后须更新为真正反阻塞回归，不永久把缺陷当PASS。

P13-P02后续：脚本已改成双Scope锁竞争真正回归，两个UOW只锁不同候选/六表无写，旧无锁peek保持原head；锁住优先head时实际第二发布/首无Attempt，释放后head正常发布。首次55P03历史保留，不再用该缺陷当脚本成功。坏来源部分仍预期失败/第二不领，直到P03关闭；非全局公平与完整隔离PASS。
