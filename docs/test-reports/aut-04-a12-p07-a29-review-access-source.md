# P07-A29 评审Auth实际数据库结果

2026-09-27 Windows11/Python3.13.15/PostgreSQL18临时库，exit0。正常真实会话/CSRF/current User返回当前uid，读取不写。

真实未知token、错误CSRF、创建前时间、idle精确到期、absolute精确到期、同UOW实际User禁用、同UOW实际Session撤销均返回None。实际SELECT1/0产生22012，随后认证SQL原DBAPIError 25P02传播，不声称适配层转换为Service错误码。8场景退出九表全行与之前一致，每次后续健康读取可用。

原dualScope空集/260行发布回归通过。禁止模拟成功SQL、停用约束或修改不可变Session凭据；测试仅fixture自建临时库/用户/License/Vault并清理，不操作生产。非正式安全锚、完整Review业务或发行验收证明。

生产/Migration/API/权限/依赖未变，无升级；完整unit最近1528本批未重跑，完整Auth覆盖/性能/wheel未跑，不推算覆盖率、原raw/90%保持。完整安全/性能CR008 FAIL/正式trust/Gate/可用包待。追溯DEC-20260927-377及同名progress/validation，下一ProjectReadAccess合同与来源验证。
