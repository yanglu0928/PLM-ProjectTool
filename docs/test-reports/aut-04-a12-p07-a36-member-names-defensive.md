# P07-A36 成员名称来源防御结果

2026-09-27 Windows11/Python3.13.15。完整1541unit/contract21.763秒，失败0/错误0/既有跳过2、exit0。新增3方法：三错误/真实inactive Session分别空与非空tuple拒绝、三缺来源原AttributeError、真实active无bind Session空tuple返回{}且事务退出闭合。

无成功SQL模拟，空tuple执行无需SQL（Session无bind），合法active事务保持。检查修正计划假设：该适配层是上层Project授权后的最小名称投影，不是权限校验器，未承诺非法编号前SQL验证；不静默添加权限或过滤规则。非法编号真实SQL/缺行/名称映射另A37明确验证。

生产/Migration/API/权限/依赖未变，无升级，可撤测试。17实际链coverage/性能/wheel未跑，不推算完整Auth，原raw/90%保持。完整安全/CR008性能FAIL/正式trust/Gate/包待。追溯DEC-20260927-384及同名progress，下一真实数据库来源。
