# P07-A32 完整安全覆盖结果

2026-09-27 Windows11/Python3.13.15/coverage7.13.5（测试依赖）。完整1532unit/contract失败0、错误0、既有跳过2；原15实际链加ReviewStartAccess与ProjectReadAccess来源链，共17条全部通过。

完整Auth所有文件3260/3379行（96.478%）、876/988分支（88.664%）；综合94.710%不替代分支90%，ALL_AUTH false/exit1。相对A21行分母+15（创建6/读取5/状态4等价布局），分支分母988不变。覆盖变化含真实新增用例/实际链与布局映射，不能全称新增行为测试提升。范围未删、无排除/pragma/门槛调整。

密码原21文件1031/1047行（98.472%）、350/384分支（91.146%）本范围通过。Windows完整factory362/369行8/10分支单列，不能用密码范围通过认定完整安全通过。

独立runtime auth-security-source-coverage JSON SHA256 `c5cc762578c3cffb1abcdd3f27e244bd5c6a6a832fc1c313a2c0e5db7fd798bf`；旧A21重验`18ef6f24069eeb56bd306a50b0fc76ba4900f17f2c8e0b44965c144f138c3b22`未变，全部旧raw保留。原始产物/诊断/秘密不上传。

仍缺112分支；密码Access/Service、UserList、项目成员名称、初始管理员来源等继续逐项验证，既有布局问题不得泛化所有缺口。性能/wheel未跑，无生产/Migration/API/依赖变，无升级。正式trust/CR008性能FAIL/Gate/可用包仍未完成。追溯DEC-20260927-380及同名progress/validation，下一用户列表Service防御与异常坐标。
