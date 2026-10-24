# P07-A25 UserRead等价分行

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A25；输入冻结64cdf09/0049、A24五边拒绝证据、原f936ff0。仅UserRead get内五guard raise独立行，实体/API/权限/事务/依赖不变。

验收：原f936ff0与新文件AST忽略位置完全一致；五节点对应、条件和raise不同行，完整unit/contract与Windows实际用户详情链执行，新runtime保旧raw，报告本文件实际行/分支及分母差异。位置映射改善不冒充新增用例，不推算完整Auth百分比或关闭Gate。

风险/回滚：仅表达布局，可撤五处改动，无Migration或升级。真实链合成License/用户与临时库/Vault，不证明正式账户安全锚。完整15链coverage、性能/wheel另项。下一真实UserState异常坐标核查，安全/性能FAIL/trust/Gate/包待。

结果：对f936ff0dcca266408651532b7b37e8b452474cbc AST完全相等；1524unit/contract失败0/错误0/既有跳过2，Windows实际详情链通过exit0。五坐标旧→新→raise：62→62→63、64→65→66、66→68→69、67→70→71、69→73→74。文件61/61行、20/20分支100%；原56/56行、15/20分支，行分母+5、分支不变，为布局统计映射改善，不是新增测试。

新raw SHA256 40f6e859ef12199d0c040da56b0c4a42c428451ed9b17ea7a3d38b565fb14e67；原A21 18ef6f24069eeb56bd306a50b0fc76ba4900f17f2c8e0b44965c144f138c3b22重验未变。完整15链coverage/性能/wheel未运行，不推算完整Auth。下一A26 UserState五个异常坐标逐边核查；Gate/包待。
