# P06-P13-P04：反向锁序真实死锁

2026-09-27/Phase2，CR-AUD-005。编码前：仅验证脚本，既有Audit/Jobs/Worker实际组合，实体/权限/API/Schema/依赖无变化。前置候选预留与明确来源隔离内部通过。验收：临时库独立事务先Audit Root后Job，与真实后台先Job后Root造成40P01；生产分类识别真实SQLSTATE，回滚释放后原有界重试成功，原pair/单Attempt/单Lease/无猜终态。

测试协调仅局部deadlock_timeout（Worker事务50ms、竞争事务5s）控制检测方，原生产lock/statement/transaction限制不改；读pg_blocking_pids确认实际阻塞，不以时间推测。分类器测试包装记录实际异常、在原UOW已回滚后等待竞争事务释放，再返回原分类结果，不注入伪死锁或修复生产流程。所有来源/文件为本轮隔离合成，License测试替身。失败/观察超时仍查看同一Future，不重启进程。回滚撤验证脚本，无Migration/升级；完整公平/耗尽坏源/正式材料/Gate待。

扩展验收先记录：同一次claim准入制造3个真实反向锁环，前2次实际40P01有界重试，第三次退出且六表无写；释放测试竞争后同一Loop实例可发布，不能无界重试/虚报SOURCE_REJECTED。双Scope均执行1次恢复及3次耗尽矩阵。

非死锁矩阵先记录：仅Root锁竞争，不建立循环，实际Worker lock_timeout触发55P03，原deadlock分类必须False，后台失败而非SOURCE_REJECTED/猜成功；六表无写，释放后同实例实际发布。保持生产timeout默认值，不以Future观察超时替代数据库终态证据。

结果 INTERNAL_PASS：PROJECT/DEPLOYMENT各单死锁、连续3死锁、无环Root锁超时共六场景；实际pg_blocking_pids证实竞争，8个真实40P01（各1+3），每次回滚后六表不写；单死锁原分类/有界重试成功，3死锁严格到上限失败并保原Root/Job，竞争释放后同Loop无重启发布，1Attempt/1RELEASED Lease/原不可变结果。2个真实55P03分类False/失败且六表不写，释放后同实例成功/零SOURCE_REJECTED。原发布空/260、并发与回滚fixture同次通过。无生产代码/API/Migration/依赖改变，不重复声称unit/wheel重跑（此前1125/2跳过保留）。

原可信身份为真实临时Vault，License仍合成。耗尽扫描坏来源、Acceptance真实故障矩阵、复杂Lease不一致和长期优先级公平未闭；下一P13-P05耗尽扫描坏源影响核查/隔离。CR-AUD-005、完整Scope/正式信任源/SCM/其他平台/完整包/Gate不关闭。
