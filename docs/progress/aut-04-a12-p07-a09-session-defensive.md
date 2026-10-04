# AUT-04-A12-P07-A09 Session拒绝与事务边界

2026-09-27；Phase2；SESSION_REFUSAL_TESTS_PASS。输入475e849/冻结64cdf09/Schema0049，前置完整Auth实测80.162%分支未达。仅Session Service unit防御，不改实体/API/权限/Schema/算法/依赖。

验收：缺必需依赖、无proof/非法ID/时间/Token在UOW或写入前拒绝；revoke/renew/logout CSRF或revoke失败不Audit/commit；logout未知/不匹配历史收据固定拒绝，不写complete；admin锁失败不批量撤销。跟踪UOW退出及commit Spy，不模拟成功SQL，规范SessionRecord仅Port路径可达控制。密码proof错误拒绝后擦除。

风险/回滚：Mock合同控制不代表PG回滚，实际证据沿P07A08原11链；完整unit本批重跑，coverage/PG随后同范围实测，不推算新覆盖。撤测试无升级，原raw/Hash/90%与性能CR008 FAIL/默认4保留，正式trust/Gate/包待。

结果：6参数化方法，完整1476unit无失败/2既有跳过，exit0；缺依赖/proof、非法ID/time/token、四revoke/renew组合、四logout早拒绝、五历史错配、admin锁失败边界通过；无commit/Audit/complete或后续撤销，已进入UOW均退出，issue错误proof擦除。coverage/11PG/wheel本批未跑，原80.162%与Hash保持；下一A10 Session投影的依赖/时间/原Project来源异常拒绝，再批量统一实测。
