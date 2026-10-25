# P07-A23 等价布局验收

2026-09-27 Windows 11/Python3.13.15/coverage7.13.5，exit0。

生产ManagedUserCreate仅六个已审计条件的raise分行。与原提交eeb6558703b059f4742d9d95b8cc32efd60668ae AST（不含位置）完全相同。完整1524unit/contract失败0、错误0、跳过2；实际创建Result来源及原发布链通过。合成用户/License/临时库，不证明正式信任源。

六guard旧→新→raise：63→63→64、65→66→67、74→76→77、75→78→79、84→88→89、88→93→95。全部实际raise行已覆盖、guard无缺失分支。文件108/108行与30/30分支100%；旧A21文件102/102行、24/30分支。行分母+6、分支分母不变，统计位置映射改善，不是新增行为用例，也不得推算完整Auth百分比。

新独立runtime auth-security-create-layout JSON SHA256 `81ad2ba34f984ed4bc8d0ce2268a1092b9dd0d6e13866362d9c9676f44bf0fd8`。旧A21 SHA256 `18ef6f24069eeb56bd306a50b0fc76ba4900f17f2c8e0b44965c144f138c3b22`重验不变。原raw/秘密/日志不上传。A22历史审计原坐标绑定布局前版本，不能把其原坐标直接套在分行后的文件。

无Migration/API/权限/算法/依赖变化，无升级要求，回滚仅撤六处布局。15链完整安全覆盖、性能、wheel本项未跑；最近完整Auth分支86.235%未达90%，CR008性能FAIL/正式trust/Gate/可用包未完成。追溯DEC-20260927-371及同名progress/validation，下一UserRead五个异常坐标逐边核查。
