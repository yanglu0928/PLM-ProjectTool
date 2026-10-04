# AUT-04-A12-P07-A05-P01：适配器数据库前拒绝边界

2026-09-27；0.1.0.dev0；P01_INPUT_REJECTIONS_PASS / ADAPTER_AND_FULL_SECURITY_PENDING。Phase2；输入6db71f5/0049/冻结64cdf09/P07分支缺口，前置Service/HTTP防御通过。仅reset/change Repository输入测试，不改生产实体/API/权限/Schema/算法/依赖。

目标：reset非法ID/版本/Hash DTO、change错误proof/Hash DTO以及User版本上限直接拒绝，明确_session/SQL未调用。不模拟成功SQL以伪造PG；正向SQL与回滚仍依据原四实际PG报告。完整unit重跑，本分项不推算新覆盖率/重跑四集成；后续适配器当前数据/异常边界与统一真实覆盖测量，保留历史Hash和完整范围。

风险/回滚：合法Hash格式只是输入元数据控制，不是实际凭据或权限；测试中不写DB。撤测试即回滚，无生产升级。90%与性能CR008 FAIL/默认4保持，正式trust/Gate/可用包未完成。

执行：新增4个参数化方法；reset非法ID/版本/Hash DTO 7类、change proof/hash类型3类、change credential/User锁版本上限2类、两Repo各3类非规范参数（包括p=True）全部拒绝；显式_session Spy未调用，未造成功SQL。完整1460unit无失败/errors0/2既有跳过，exit0。无生产变更；本轮coverage/四真实PG/wheel未跑，不推算新分数，最近P07A04P02密码82.432%分支/全Auth74.743%仍为实际证据，原runtime/Hash不改。

下一P07A05P02 current proof/transaction输入与适配器安全异常边界，随后统一真实PG覆盖复验。单独输入通过不关闭适配器全部或90%/性能/Gate/可用包；详细方法范围与参数控制见test-report。
