# AUT-05-A12-P05-A01 Windows11隔离User状态回归

2026-09-28 / 0.1.0.dev0 / PASS（仅实际Windows11合成信任ASGI/PG后端链；首轮基础设施失败保留）。

编码前检查：Phase2/Gate2已批准；输入冻结`AUTH_USER_ENABLE/DISABLE`及已有Windows显式write组合/隔离验证脚本，前端A12-P04页面合同通过。DEC-423先登记；本项只重跑原隔离后端验证，不改生产代码、Schema/Migration、API/权限/依赖；回滚无代码变化。

首轮`validation/aut-04-a11-p05-windows-user-state/verify.py`在连接本机PG18.6/55432时超时；`pg_ctl status`确认服务未运行，旧postmaster.pid的PID无对应进程。检查历史日志后用原data目录启动，恢复日志记录之前非正常停机、WAL自动恢复并就绪；重跑前检查`publication_%`及旧`prj05a04_%`catalog库均0。具体停机原因未证实，未修改数据目录/清未知源。

重跑exit0：Windows显式write Factory/真ASGI/隔离PG和Scrypt链验证User创建、普通用户状态命令404、Admin停用后旧Session401和禁登录、启用后新登录200且旧Session仍401、原Key首次结果重放不写；readonly405/default-login404、五个构造依赖故障安全停止及无正式信任拒绝。原双Scope文件发布回归也PASS。结束外部复查`publication_%`临时数据库0，PG服务仍运行。

限制：正向License/游标和Vault为显式合成测试源；本项未点击前端状态页面，也未验正式HTTPS/信任、20并发、Server2025/Debian或可用程序包。首次停机与恢复是基础设施稳定性待排风险，不能归因为User状态代码。无生产迁移。下一独立浏览器页面联调。
