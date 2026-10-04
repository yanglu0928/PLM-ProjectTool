# AUT-04-A12-P07-A04-P02：写阶段Service防御

2026-09-27；0.1.0.dev0；FRESH_WRITE_DEFENSIVE_PASS / FULL_BRANCH_COVERAGE_BELOW_90。Phase2；输入e3e8ec0/0049/冻结64cdf09与P07覆盖缺口；前置准备边界已验证。仅reset/change Service测试与后续覆盖入口，不改生产实体/API/权限/Schema/算法/依赖。

目标：真实类型但错配repo返回/immutable first/source/当前末核及未知类型均拒绝commit，验证密码擦除与UOW关闭。成功fixture必须先跑通真实Service控制流程，防止所有错误测试在错误的更早位置停止；Port替身不冒充真实PG提交。完整unit实际跑，随后同一21文件/Auth/工厂四真实PG覆盖复验，保留旧runtime/Hash；90%与性能未达不得关闭Gate。

风险/回滚：测试会模拟不可信可信Port违约，不修改生产安全机制或事务行为；撤测试即回滚，无生产升级。准备/写两个分项均通过也不证明整个Auth安全；真实PG与正式trust/平台/可用包缺项仍在，性能CR008 FAIL/默认4保持。

执行：新增5参数化方法专测通过，正向Spy控制唯一提交可达、repo/first/final错误无commit且擦除/UOW关闭。完整1452unit无失败/errors0/2既有跳过，同轮四实际PG/Windows全通过。密码991/1017行97.443%与305/370分支82.432%，全Auth92.352%/74.743%，工厂362/369行8/10分支单列；exit1保90%缺口，原JSONHash与边界细节见test-report。无生产变更，wheel未跑。

A04整项未完成：下一A04-P03历史写UOW reserve hint/first违约与准备first错配拒绝，再适配器防御；先补当前Service遗留，不提前称所有写阶段/安全/Gate/包通过。
