# P07-A28 评审启动身份来源防御合同

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A28；输入冻结64cdf09/0049、A21覆盖缺口、现有SqlAlchemyReviewStartAccess。仅Auth适配层非法token/CSRF/time与真实inactive Session拒绝，不改Review业务、API/权限/Schema/依赖。

验收：非法输入返回None且不读取tx.session；合法输入遇错误Session来源或真实未启动事务Session抛原RuntimeError且不启动事务。包括无时区/无utcoffset时间；禁止mock成功SQL，实际当前用户/CSRF查询另A29。完整unit/contract运行，coverage/15链/性能/wheel本项不跑，不推算覆盖提升。风险/回滚：仅新增测试，可撤，无升级；Gate/包待。

结果：新增3参数化方法（14个token/CSRF输入、5个time输入、5个事务来源），完整1528unit/contract21.638秒失败0/错误0/既有跳过2，exit0。非法输入不读取Session来源，真实inactive Session不启动事务；无成功SQL模拟，无生产变化。coverage/15链/性能/wheel未运行。下一A29实际数据库会话/CSRF/当前用户来源与边界拒绝验证，Gate/包待。
