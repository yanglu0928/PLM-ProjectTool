# P07-A10-P01 会话投影入口验证

日期2026-09-27；Windows11/Python3.13.15；新增4参数化方法；完整unittest discover实际1480项，failures0/errors0/skipped2，exit0。

|验证|结果|
|---|---|
|构造依赖None与四非法uid|拒绝，未开启UOW/未读Project|
|非Session与真实未启动Session|SQL前拒绝，真实Session仍无事务|
|token绑定转接成功/LookupError/RuntimeError|精确转交参数，绝不fallback|
|四非callable绑定/无绑定或None|错误拒绝，既有legacy兼容不变|

Mock只验证公开Port转接，不模拟SQL成功；无实际数据库读取/当前Credential错配/Project错误投影证据，本轮未运行11PG/coverage/wheel/性能。最近A08全Auth分支80.162%不变，不推算新覆盖。P01 PASS，A10/完整安全/CR-AUT-008性能/正式信任/Gate3/可用包仍未关闭。
