# AUT-04-A12-P07-A06-P02 实际最终核验拒绝

2026-09-27；Phase2；ACTUAL_FINAL_FAULT_ROLLBACK_PASS。输入cdb9f2e/冻结64cdf09/Schema0049；前置结果适配器拒绝通过。涉及Auth实际Service/Access、Credential/User/Session/first/Audit/Receipt，不改实体/API/权限/生产Schema或依赖。

验收：隔离PG18与真实SCRYPT，change及Admin自reset两种路径，真实final正向先可达；在同UOW最终核验前实际插入额外活/同批撤销Session、改变当前User版本、SQL除零使事务中止，实际Access拒绝后九表全行不变、原Session仍可用、密码擦除。后续正常提交证明入口未被绕过。不能使用伪造成功SQL或强行关数据库触发器。

风险/回滚：故障行仅隔离测试库/同失败事务内，可信角色供给TEST_ONLY/License合成；非正式部署/浏览器/灾备证明。撤验证入口，无生产升级。独立实际运行并保结果，不推算覆盖率；下一同轮coverage，90%/性能CR008 FAIL/默认4/Gate/可用包仍待。

结果：八真实故障全部安全拒绝/九表全行回滚/原Session可用/密码擦除，两真实提交与新Session控制通过；两除零SQLSTATE22012后actual Access固定错误。实际双Scope发布原回归也通过，exit0。unit最近1470保留本批未重跑，coverage/wheel/性能未跑；下一P03完整unit+原四链+本链同轮覆盖，不关闭安全/Gate。
