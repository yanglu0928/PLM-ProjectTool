# P07-A24 UserRead异常坐标审计

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A24；输入冻结64cdf09/0049、A21原raw及当前UserRead。仅审计五个缺失guard62/64/66/67/69→72，读取对应AST与既有拒绝用例；不修改生产/API/权限/Schema/依赖。

验收：三个现有方法分别coverage与独立sys.settrace执行；每个guard实际异常事件必须有证据，输出真实arcs与仍缺坐标。额外断言noCommit、UOW退出和固定拒绝，不记录locals/异常详情。Port合同不冒充SQL。新runtime保旧raw，无排除/门槛变更；若未触发必须补测，不泛化旧结论。完整unit/15链coverage、性能/wheel本项不跑。可撤脚本，无升级；Gate/包仍待。

结果：两轮均3/3通过exit0，guard62/64/66/67/69异常事件分别4/3/1/1/1，实际拒绝跳转到UOW出口60，对应五条到72的统计坐标仍缺。三个方法额外noCommit/UOW退出断言通过。仅证明五个拒绝已执行，不豁免其余完整Auth缺口。下一A25仅这五个guard AST等价分行，再完整unit与实际Windows用户详情读取链验收。
