# P07-A17 Session接口异常合同

2026-09-27；Windows11/Python3.13.15；新增7参数化contract方法，全量1508项failures0/errors0/skipped2、exit0。

|类别|案例|结果|
|---|---|---|
|三个router缺依赖|8|构造拒绝|
|GET validate/投影身份/来源/public flag|4|固定503、无Cookie|
|renew validate拒绝|4|原403/401/503、无投影/renew|
|renew投影拒绝|3|503、无renew|
|renew自身异常|4|固定403/401/503、无Cookie|
|logout非True|4|503、不清Cookie|
|logout自身异常|3|固定403/503、无Cookie|

错误Envelope含有效trace_id，固定error.code，无Synthetic private异常详情/Token/Set-Cookie。Mock只HTTP Port合同，无法证明实际数据库无写/回滚或浏览器Cookie/TLS；原正向契约及实际Windows链保留。

生产/Schema/API规则/权限/算法/依赖无变化，兼容0049无升级。coverage/14PG/wheel/性能本批未跑，A16全Auth84.717%/raw Hash7d6fbfc0…保持，不推算新覆盖。正式trust/性能CR008 FAIL/Gate3/可用包未完成；下一独立User read Service防御。
