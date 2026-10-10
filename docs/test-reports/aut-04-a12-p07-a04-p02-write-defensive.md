# P07-A04-P02 写阶段防御与覆盖复验

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15/coverage7.13.5；输入e3e8ec0、Schema0049，生产源码不改。

新增5个参数化方法：两个正向对照实际执行Service直到收据complete、末核与唯一一次tx.commit调用；在此可达基线注入change credential ID/时间/count错误（4类）、reset view/before/target/version/credential/count违约（8类）、first未知类型/trace错配（两操作各2类）、末核False/整数1/未知异常（两操作各3类）。所有错误用例明确2个UOW均未commit、UOW关闭、秘密擦除；早期错误不record/complete，末核错误可能已经调用同事务complete但仍不commit。

这是可信Port违约的测试替身证据，不表示实际DB已经写入或回滚；两个正向“commit”仅Spy调用，真实原子/审计故障/丢回执/权限竞争/历史来源由同轮四实际PG/Windows入口补证。

5方法专测全部通过；同一branch coverage执行完整1452 unit/contract无失败/errors0/2既有跳过，再实际运行reset-history+原atomic、change-history+原atomic、Windows reset、Windows change四组，全部断言通过。正向role/license/trust明确synthetic，不冒充正式账户/生产信任。

同一21密码文件991/1017行=97.443%，305/370分支=82.432%，综合93.439%；全Auth3079/3334行=92.352%，728/974分支=74.743%；Windows全工厂362/369行8/10分支单列。分支仍未达90，脚本exit1为覆盖率缺口，测试与实际集成无失败，综合高分不抵消未达项。Service reset133/136行40/50分支，change136/137行55/70分支；完整文件范围保A03/A02，不删源码路径/加omit或pragma。

完整原JSON另.poc-runtime/auth-security-service-defensive-coverage/coverage.json，SHA256 e81793fc191d6af500169a5d1beb6843d552698b684809c69591b2c9c2d2e08c。A01/A02/A03原路径/报告/Hash不覆盖，不同步Secret/客户数据/运行日志。未重跑wheel，无生产源码/Migration/API/权限/算法/依赖变化或升级；固定KDF/默认4、性能CR008 FAIL保持。

A04仍有历史写阶段未知/错配reserve hint/first及准备first错误等防御未补；下一A04-P03精确补这些路径，再适配器拒绝边界。覆盖率包含异常清理边，不能人为删未命中路径或造SQL成功。全部Auth权限安全、正式trust/目标账户/三平台/安装/UAT/Gate3与可用包仍未完成。
