# P07-A29 评审Auth实际数据库来源

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A29；输入冻结64cdf09/0049、A28合同及SqlAlchemyReviewStartAccess。仅Auth适配层当前会话/用户/CSRF实际SQL验证，不改Review业务/API/权限/Schema/依赖。

验收：真实有效会话返回当前用户；未知token、错CSRF、创建前/idle到期/absolute到期输入、同UOW实际禁用用户/撤销会话返回None；真实SELECT1/0后原DBAPIError 25P02传播，不冒充Service固定码。每场景退出九表全行与之前一致，正常读取无写，后续正常读取仍可用。仅自建临时PG/合成用户/License/Vault，由原fixture清理；不mock成功SQL、不停用约束或篡改不可变Session凭据。

风险/回滚：故障数据仅未提交UOW，退出回滚，生产不操作；无Migration/升级。完整unit最近1528本项不重跑，完整安全coverage/性能/wheel另项，Gate/正式trust/包待。

结果：实际有效会话返回uid，七个正常拒绝返回None、一个实际SQL22012后25P02原异常传播，共8场景通过exit0。每场景九表全行回滚、正常重读可用，原dualScope空集/260行发布回归通过。未模拟成功SQL、未停约束，生产未修改。unit1528本批未重跑，完整coverage/性能/wheel未跑。下一A30仅ProjectReadAccess防御合同与来源计划，Gate/包待。
