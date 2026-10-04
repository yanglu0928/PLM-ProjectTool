# P07-A34 用户列表三个异常坐标

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A34；输入冻结64cdf09/0049、A32原raw、A33防御测试与UserList。仅57/59/61→68三个guard独立coverage/trace，分别clock/身份/结果类型拒绝；不改生产/API/权限/Schema/依赖。

验收：三个现有方法两轮实际执行，异常事件与真实arcs逐边输出，noCommit/已进UOW退出；原到68缺失不预认误差，不套用UserRead结论。新runtime保旧raw，原90%不改，不收locals或秘密。风险/回滚：只审计脚本可撤，无升级；完整1538/17链coverage/性能/wheel本项不跑，Gate/包待。

结果：三方法coverage/独立trace两轮3/3通过exit0；guard57/59/61异常事件4/1/1次，真实拒绝到UOW出口55，原到68坐标仍统计缺失。noCommit/UOW退出通过，仅三边证据，不豁免其他缺口。无生产变化，完整1538/17链coverage/性能/wheel未跑。下一A35仅三guard AST等价分行、完整unit与Windows实际列表链验收；Gate/包待。
