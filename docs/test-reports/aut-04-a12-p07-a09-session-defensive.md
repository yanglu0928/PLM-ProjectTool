# P07-A09 Session Service拒绝边界

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15；输入475e849/Schema0049，生产源码未改。

新增6个参数化方法：四必需依赖为空与无proof在事务前拒绝；四非法User ID、四非法clock、四非法token不访问数据库Port，issue caller proof擦除；revoke/renew分别CSRF错或revoke False共四组合无Audit/Session create/commit且UOW闭合；logout缺receipts/记录缺失/CSRF错/revoke False四场景固定错误，无complete/Audit/commit；logout历史current缺失/未撤销/原因RENEWED或receipt ref/status错五场景SYSTEM_UNAVAILABLE且不撤销、不complete、不Audit、不commit；admin锁用户失败不调用批量撤销或Audit/commit。

规范SessionRecord/Mock Port仅使拒绝路径可达，不能作为实际身份、授权、SQL成功、数据库回滚或客户资料证明。事务Spy跟踪每个进入UOW退出与commit未调用；真实PG回滚仍由P07A08十一入口的原证据支持，本批没有重跑。没有修改生产协议或异常传播机制。

完整1476unit/contract无失败/errors0/skipped2（既有符号链接账户权限场景），exit0。coverage/11实际入口/wheel/性能本批未运行，原完整Auth80.162%分支及Hashf6a57106…保持，不推算新百分比或关闭安全门槛。

无Migration/API/权限/算法/依赖/升级变化，兼容0049；回滚撤新增测试。下一A10 Session投影clock/依赖/Project源错误拒绝，随后完整范围实测；90%、性能CR008 OPEN/FAIL、默认4、正式trust/目标环境/UI/安装升级/UAT/Gate与可用程序包仍待。
