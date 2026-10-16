# P07-A25 UserRead等价布局结果

2026-09-27 Windows11/Python3.13.15/coverage7.13.5，exit0。与原f936ff0dcca266408651532b7b37e8b452474cbc生产文件AST（不含位置）完全相同。仅五guard raise分行；1524unit/contract失败0/错误0/既有跳过2，Windows真实用户详情链通过（临时库/合成信任源，非正式账户验收）。

旧→新→raise：62→62→63、64→65→66、66→68→69、67→70→71、69→73→74。五guard分支和raise行均覆盖，文件61/61行、20/20分支100%。旧A21 56/56行、15/20分支；行分母+5、分支不变。改善为布局位置映射，不是新增行为测试，不推算完整Auth覆盖率。

独立runtime auth-security-read-layout JSON SHA256 `40f6e859ef12199d0c040da56b0c4a42c428451ed9b17ea7a3d38b565fb14e67`；A21原JSON重验`18ef6f24069eeb56bd306a50b0fc76ba4900f17f2c8e0b44965c144f138c3b22`未变。原始产物/诊断不上传；A24历史审计坐标绑定分行前版本。

无Migration/API/权限/依赖变，无升级；回滚仅撤五布局。完整15链coverage、性能、wheel未跑；完整安全/CR008性能FAIL/正式trust/Gate/交付待。追溯DEC-20260927-373及同名progress/validation，下一UserState异常坐标逐边核查。
