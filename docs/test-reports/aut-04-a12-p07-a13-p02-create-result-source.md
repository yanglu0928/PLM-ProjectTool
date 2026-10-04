# P07-A13-P02 真实创建结果来源与回滚

2026-09-27；Windows11/Python3.13.15/隔离PG18/current0049；入口validation/aut-04-a12-p07-a13-p02-create-result-source/verify.py。

首次exit1是验证脚本fixture未导出ManagedUserCreateError，实际Service已按预期拒绝；修正为正式模块导入后全部重跑exit0，原fixture正常清理owned DB/临时文件/Vault来源。

通过：真实first读回/缺first None，缺User/原Credential record固定拒绝；真实Credential1密码True/False；两个明确DTO错配、四明确verifier非bool/异常，在真实原源SQL后拒绝；三独立事务实际SELECT1/0 SQLSTATE22012中止，get/record/verify统一固定码。读和拒绝九表无变化。

真实创建record INSERT/get成功后，adapter故障显式返回None；原record拒绝、Service AUTH_CREATE_UNAVAILABLE，无commit，九表SELECT全部行与之前完全相同、密码清零。故障不是SQL mock/触发器禁用；之后同名称真实正常创建并读回first通过。原dualScope空/260行真实文件/publication回归同轮通过。

不称数据库实际损坏/生产trust证明；正向License仍合成。unit最近1491本批未跑，coverage/wheel/性能未跑，旧82.186%/Hash保持；性能CR008 FAIL/正式trust/Gate3/完整程序包未完成。下一独立User状态Service防御与后续13链统一实测。
