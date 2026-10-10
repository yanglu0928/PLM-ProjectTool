# P07-A33 用户列表防御结果

2026-09-27 Windows11/Python3.13.15。完整1538unit/contract21.806秒，失败0/错误0/既有跳过2、exit0。新增6参数化方法：四依赖、五clock、四篡改Query、五篡改Page、首末License、三Access/UOW故障。

非法依赖/Query前事务拒绝、clock前身份和列表拒绝、篡改结果不返回、首末License固定码、来源/UOW错误固定码/noCommit/已进入UOW退出通过；enter失败不要求未进入的UOW调用exit。Mock仅Port，不成功SQL模拟，不将noCommit断言当真实数据库回滚。

生产/Migration/API/权限/依赖未变，无升级，可撤测试。17实际链完整coverage、性能、wheel未运行，不推算覆盖率，原raw/90%保持。原三个到68异常坐标下一项独立trace核对，不能假定统计误差。完整安全/CR008性能FAIL/正式trust/Gate/可用包待。追溯DEC-20260927-381及同名progress，下一A34异常坐标audit。
