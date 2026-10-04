# P07-A27 用户状态等价布局

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A27；输入冻结64cdf09/0049、A26四边实际异常证据、原be1d88f。仅UserState _execute guard101/111/116/127的raise独立行；保留ActorProof新增真实测试，不改实体/API/权限/事务/算法/依赖。

验收：对原be1d88f AST忽略位置完全相等，四节点一一对应且raise在条件后独立行；完整unit/contract与实际状态final来源链执行，独立runtime原raw保留，报告文件范围真实覆盖/分母。布局统计映射改善非新增行为测试，不推算完整Auth。完整15链coverage/性能/wheel另项，90%门槛不变。

风险/回滚：仅四布局可撤，无Migration/升级。实际链仅临时PG与合成License/用户，不代表正式trust。下一按原始缺口补真正未测权限来源，Gate/性能FAIL/包待。

结果：对be1d88f745881e1089d3b01755b62e9981389215 AST完全相等，完整1525unit/contract失败0/错误0/既有跳过2，实际状态final来源/回滚及原发布链通过exit0。四旧→新→raise坐标101→101→102、111→112→113、116→118→123、127→130→131，均无缺失分支。文件108/108行、38/38分支100%；A21旧104/104行、33/38分支，行分母+4/分支不变，五分支改善含A26新增真实ActorProof拒绝1边和本轮布局映射4边，不混为新增测试提升。

新raw SHA256 0d251b1cbe1824437d30994fc2a7dc85733ccefdb963c6e622b79a319c502408；A21旧18ef6f24069eeb56bd306a50b0fc76ba4900f17f2c8e0b44965c144f138c3b22重验未变。完整15链coverage/性能/wheel未跑，不推算完整Auth。下一A28仅ReviewStartAccess非法输入/真实inactive Session防御合同，实际当前用户/CSRF来源另分项，Gate/包待。
