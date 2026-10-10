# P07-A31 项目读取Auth实际来源

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A31；输入冻结64cdf09/0049、A30合同与ProjectReadAccess。仅Auth当前Session/User实际SQL来源验证，不改Project权限、业务/API/Schema/依赖。

验收：有效会话返回当前uid；未知token、创建前/idle精确到期/absolute精确到期、同UOW真实User禁用/Session撤销均返回None，真实SQL22012后25P02原异常传播；九表全行退出回滚、每次健康重读可用。仅fixture自建临时PG/合成用户/License/Vault，不停约束、不mock成功SQL、不操作生产。当前凭据受限制场景保留原实际Session来源链证据，不在本项推断额外结果。

风险/回滚：故障SQL仅未提交UOW退出回滚；无Migration/升级。unit最近1532本项不重跑，完整coverage/性能/wheel另项。下一17实际链完整安全覆盖复验；Gate/包待。

结果：真实正常读取及7拒绝（6返回None、1实际22012→25P02原异常）全部通过exit0，九表全行回滚与健康重读、原dualScope空集/260行发布回归通过。无生产变更/成功SQL模拟，unit1532本项未跑，完整coverage/性能/wheel未跑；下一A32完整1532测试与17实际链安全覆盖，保原raw与90%，Gate/包待。
