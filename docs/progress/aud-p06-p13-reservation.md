# P06-P13-P02：只锁候选预留

2026-09-27 Phase2，输入CR-AUD-005/P13-P01真实55P03证据，前置完整原pair/claim/确认恢复通过。编码前：Jobs Application/Repository与Audit admission；实体/权限/API/Schema不变。新增reserve_next独立于原无锁peek，SELECT FOR UPDATE SKIP LOCKED只预留一个eligible Job，完整Root/pair/identity核验后才执行原claim，所有行锁在同一有界UOW结束释放。

验收：锁优先队首时正常第二实际发布且首无Attempt，释放后首发布；双Scope/双Worker互斥/rollback/commit确认回归。风险：新的Job→Audit锁序可能和旧Audit→Job竞争死锁，保真40P01有界重试，其他错误失败关闭；坏源不在本项吞掉。无Migration/依赖/API升级；回滚撤reserve接线保历史。结果待运行，完整公平/坏源隔离/发行/Gate未完成。

结果 INTERNAL_LOCK_SKIP_PASS：reserve_next独立新增，原无锁peek语义未变，候选只持锁/不commit/不写；Application精确候选验证与脱敏，Admission在Root前预留。3新unit/1116后端通过（2既有权限跳过）；实际PG双Scope并发两UOW取不同reservation、原peek仍看见锁住队首/六表无写；实际Loop跳过外部锁优先队首并发布第二，首PENDING无Attempt，释放后首发布。双Scope独立Supervisor单claim/回滚/到期代际/最多3次原P03、commit前回滚与commit后确认恢复原P06回归通过。坏payload仍六表无写退出，明确未修复。

开发wheel631564 bytes，SHA256 `98b2b828118d9a266c3bd2b61c9589ea6cde7df7c8a4f53b64bc9a50aba96968`。本轮未制造反向锁序真实40P01，不能声称新版锁序死锁验收已关闭；全局公平/坏源/SCM/正式材料/完整包/Gate仍待，CR-AUD-005保持打开。下一P13-P03坏源候选/错误分类设计与实现。

P12-B02真实Windows CLI子进程也在新reservation版本复验通过：双Scope文件哈希/结果、缺公钥与idle无写、active外部CTRL_BREAK只排空一个/第二未领取后再once完成；明确测试License，不提升正式来源/SCM结论。
