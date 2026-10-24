# AUT-04-A12-P07-A04-P03：历史写阶段防御

2026-09-27；0.1.0.dev0；REPLAY_PORT_DEFENSIVE_TESTS_PASS / FULL_SECURITY_PENDING。Phase2；输入939cff0/0049/冻结64cdf09及P07实际分支缺口。前置准备/新写防御通过；仅reset/change history测试，不改生产实体/API/权限/Schema/算法/依赖。

目标：准备first错配/未知类型、写阶段reserve None/错误类型/op/status与first身份或坐标变化、最终当前身份撤回均安全拒绝；严格无repo写/commit、UOW闭合和密码擦除，正常history仍原first。先使用明确Port违约测试，实际PG已由P02同轮四入口验证；本批完整unit重跑，不推算新覆盖率或冒充真实SQL。记录原source与旧测量Hash，随后适配器边界与统一真实覆盖复验。

风险/回滚：不使用omit/pragma或删路径提高分数，commit spy不证明SQL回滚；撤测试即回滚，无生产升级。90%与性能CR008 FAIL/默认4不改，完整Auth/Gate3/正式trust/目标环境/可用包仍待。

执行：新增4个参数化方法（reset准备4/写7、change准备2/写8种场景）通过；准备first未知/错User-Actor-version在KDF/reserve前拒绝，历史写reserve missing/type/op/status、first ID/trace/user变化与最终actor None在真实Service控制路径拒绝。写阶段确认reset1/change2次source verify已执行、2个UOW关闭且无repo/收据complete/commit，两个密码缓冲区均擦除。完整1456unit无失败/errors0/2既有跳过，exit0。

本轮没有运行coverage/四真实PG/wheel，仍以P02的82.432%密码分支为最近实测，不推算提升。详细输入/事务Spy与风险在对应test-report；原JSON/Hash不改。A04准备/新写/历史Port违约分项已补，整体安全目标和异常清理/适配器路径仍待；下一P07-A05适配器拒绝边界，再完整实际覆盖复验，不关闭90%/性能/Gate/可用包。
