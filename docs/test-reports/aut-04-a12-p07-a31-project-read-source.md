# P07-A31 项目读取Auth实际来源结果

2026-09-27 Windows11/Python3.13.15/PostgreSQL18临时库，exit0。有效实际Session/current User返回当前uid且读取不写。

未知token、创建前时间、idle精确到期、absolute精确到期、同UOW实际User禁用/Session撤销均返回None；实际SQL22012后原DBAPIError 25P02传播。7场景退出九表全行一致，每次健康重读恢复正常。原dualScope空集/260行发布回归通过。

无成功SQL模拟、无停约束、无修改不可变Session凭据；仅fixture自建临时PG/合成用户/License/Vault，不操作生产、不证明Project完整权限或发行安全锚。当前受限制凭据原Session来源链历史证据保留，未在本项新运行该场景。

无生产/Migration/API/权限/依赖变，无升级。unit最近1532本批未跑，完整Auth覆盖/性能/wheel未跑，不推算新百分比，原raw/90%保持。完整安全/CR008性能FAIL/正式trust/Gate/包待。追溯DEC-20260927-379及同名progress/validation，下一A32完整测试与17实际链覆盖复验。
