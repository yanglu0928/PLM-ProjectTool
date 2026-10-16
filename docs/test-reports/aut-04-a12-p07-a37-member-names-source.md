# P07-A37 成员名称实际SQL结果

2026-09-27 Windows11/Python3.13.15/PostgreSQL18临时库，exit0。七真实投影：空集、单用户、多用户、重复+缺行、全缺行、None编号、有效UUID字符串；结果仅数据库当前display，缺行不造名称。重复映射为字典去重，None不匹配、有效UUID字符串由PG转换，不冒充前SQL输入校验。

同UOW实际改名并禁用后读取当前新名称，九表退出回滚。非法UUID字符串真实SQL22P02原DBAPIError传播；实际SELECT1/0的22012后读取产生25P02原DBAPIError。每次九表全行退出一致、健康重读正常。原dualScope空集/260行发布链回归通过。

只做上层Project授权后的最小名称投影，不扩权限、不把适配层当授权/编号校验器。没有成功SQL模拟或停用约束，仅fixture自建临时库/合成用户/License/Vault，无生产操作。无生产/Migration/API/权限/依赖变，无升级。完整unit最近1541本批未跑、完整coverage/性能/wheel未跑、不推算百分比，保旧raw/90%。完整安全/CR008性能FAIL/正式trust/Gate/包待。追溯DEC-20260927-385及同名progress/validation，下一初始管理员Service防御。
