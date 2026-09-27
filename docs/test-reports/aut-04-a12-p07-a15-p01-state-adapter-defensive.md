# P07-A15-P01 状态适配层入口验证

2026-09-27；Windows11/Python3.13.15；4新增参数化方法，完整unittest discover1501，failures0/errors0/skipped2、exit0。

|场景|结果|
|---|---|
|Repo user/actor各四非法ID|VALIDATION_FAILED，未_session|
|八自停用来源错配|False，未_session|
|Proof/Result两个篡改字段|既有合同异常，未_session|
|真正未启动SQLAlchemy Session lock/change/final|AuthTransactionError，Session仍无事务|

不mock成功SQL；patch只断言入口未被访问。Adapter原事务异常传播，不声称已固定码转换（属于Service层）；真实当前行/自停用末核与九表回滚留P02。

生产/Schema/API/权限/算法/依赖无变化，兼容0049无升级。coverage/13PG/wheel/性能本批未跑，原完整Auth82.186%/Hasha2fb0a38…保留，不推算新覆盖。性能CR008 FAIL、正式trust/Gate3/可用包未完成。
