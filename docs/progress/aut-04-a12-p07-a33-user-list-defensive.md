# P07-A33 用户列表Service防御验证

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A33；输入冻结64cdf09/0049、A32完整raw、现有UserList。仅Service依赖/clock/篡改Query-Page/首末License/Access-UOW异常合同，不改生产/API/权限/Schema/依赖。

验收：非法依赖/Query拒绝前事务，clock拒绝前身份/列表，篡改Page不返回、首末License固定拒绝、异常固定码/noCommit/已入UOW退出；mock仅Port，不成功SQL模拟，不冒充实际数据库回滚。新增完整unit实跑，原到68缺失坐标另逐边审计，不称全部统计问题。风险/回滚：只测试可撤，无升级；17链coverage/性能/wheel不跑，Gate/包待。

结果：新增6参数化方法，完整1538unit/contract21.806秒失败0/错误0/既有跳过2、exit0。四依赖/五clock/四篡改Query/五篡改Page/首末License/三Access-UOW故障拒绝与noCommit/已进UOW退出通过。仅Port证据，不冒充SQL。无生产变化，17链coverage/性能/wheel未跑，不推算新覆盖率。下一A34原UserList三个到68异常坐标逐边audit，Gate/包待。
