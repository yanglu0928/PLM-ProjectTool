# AUT-04-A12-P07-A02：真实PG/Windows覆盖补证

2026-09-27；0.1.0.dev0；REAL_INTEGRATIONS_PASS / BRANCH_COVERAGE_BELOW_90。上一轮35072d0提供实际1433测试与覆盖基线，属于进展。

编码前检查：Phase2；本WBS；输入0049/冻结64cdf09/CR-AUT007/008/P07A01完整21文件范围。前置满足测量要求，90%与性能缺口仍在。仅验证入口与证据，不改生产实体/API/权限/Schema/算法/依赖。coverage启动后执行全部unit/contract及实际隔离PG reset/change history+原atomic、Windows reset/change HTTP完整矩阵；正向信任合成，临时库/凭据/文件由已有fixture拥有并清理，无生产操作、客户正文或外发。

验收：保持全21文件/全Auth/全Windows工厂三个范围，不删错误路径；每个实际集成入口完成且断言通过后才登记通过，出错固定类型与入口名，不回显Secret/SQL/URL。报告真实行/分支分子分母与90%目标；未达保持exit1，不拿局部PASS关闭Gate。结果放独立runtime目录，不覆盖A01原JSON/Hash历史。

风险/回滚：插桩有开销，不能使用本次时间推算性能；已有覆盖不等于所有短路数据组合/实际权限场景完整。撤测量入口即可回滚，不改原业务实现/DB历史；真实授权/角色来源限定synthetic。下一按实际缺口补单元边界/权限异常，不把mock SQL执行当真实PG证据。原性能FAIL、正式trust/服务账户/三平台/可用包未完成。

执行：1433unit无失败/errors0/2既有跳过，四个实际PG/Windows入口全通过。密码968/1017行95.182%、282/370分支76.216%、综合90.123%，仍未满足行/分支均90/exit1；全Auth91.662%/72.382%，工厂362/369行8/10分支单列。详细21文件与原JSONHash/完整测量范围在test-report；A01原Hash复核保持不覆盖。没有生产变更，wheel未重跑。本项真实集成测量完成，不等于安全验收关闭；下一P07A03 HTTP失败关闭异常边界，随后Service/授权防御路径，不降低门槛或删源码。
