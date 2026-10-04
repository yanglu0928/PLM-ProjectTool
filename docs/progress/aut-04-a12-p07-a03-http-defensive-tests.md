# AUT-04-A12-P07-A03：HTTP失败关闭边界

2026-09-27；0.1.0.dev0；HTTP_DEFENSIVE_TESTS_PASS / FULL_BRANCH_COVERAGE_BELOW_90。Phase2，本WBS；输入冻结64cdf09/0049/CR-AUT007/008、P07A02真实覆盖缺口，前置满足。仅Auth HTTP测试与覆盖测量入口，不改实体/生产源码/API/权限/Schema/算法/依赖。

验收：reset/change缺依赖、不可信初始principal、Service异常与result错配、postcommit不可信/异常Session均固定拒绝、不泄露错误和秘密、不猜测清Cookie；只有确认Session过期才清Cookie。合法Port结果与原body/trace合同保留，secret buffer所有写后失败均擦除。HTTP Port故障用明确测试替身，不冒充真实PG提交；仍同一覆盖中重跑1433+新增unit与四组真实PG/Windows场景，21文件完整范围/全Auth/工厂分列，90%未达保持FAIL。

风险/回滚：覆盖率不证明所有输入组合；postcommit503不等于事务回滚，只验证HTTP不伪报成功/不清未知Cookie，真实原子/丢回执依据原PG测试。撤测试入口即回滚，无生产升级；结果另runtime目录保A01/A02历史Hash。性能CR008、正式信任/Gate/可用包缺项仍待。

执行：新增8个参数化方法专门测试全通过，完整1441unit无失败/errors0/2既有跳过，四组真实PG/Windows全部通过。两个API行/分支100%；密码982/1017行96.559%与293/370分支79.189%，全Auth92.082%/73.511%，工厂362/369行8/10分支单列。综合91.925%不抵消分支未达，exit1未关闭整体安全验收。原JSONHash及完整行为/范围/剩余路径在test-report；无生产改变，wheel未跑。下一P07A04 Application Service违约proof/first/receipt/source/repo结果/时间与依赖边界，无额外写与擦除，真实PG证据保持。
