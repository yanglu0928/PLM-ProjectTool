# P07-A30 项目读取Auth防御合同

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A30；输入冻结64cdf09/0049及现有SqlAlchemyProjectReadAccess。仅Auth非法token/time和真实inactive Session来源拒绝，不改Project业务/API/权限/Schema/依赖。

验收：非法输入返回None且不读transaction.session；错误Session/真实inactive Session原固定RuntimeError，事务不启动；缺transaction.session保留原AttributeError，不把它冒充统一RuntimeError或顺手改生产。时间沿现有isinstance(datetime)合同，不强加exact-type。禁止成功SQL模拟，真实Session/User另A31。完整unit实跑，coverage/16链/性能/wheel不跑；可撤测试无升级，完整安全/Gate/包待。

结果：新增4参数化方法（7非法token/5时间/3Session/3缺来源），完整1532unit/contract21.810秒失败0/错误0/既有跳过2、exit0；前来源拒绝/真实inactive不启动事务/缺来源原AttributeError通过。无成功SQL模拟，无生产变更。coverage/实际链/性能/wheel未跑，不推算全Auth。下一A31真实数据库当前Session/User及拒绝边界，Gate/包待。
