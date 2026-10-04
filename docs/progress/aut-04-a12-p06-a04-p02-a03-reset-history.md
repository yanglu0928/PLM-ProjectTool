# AUT-04-A12-P06-A04-P02-A03 reset 历史KDF事务外编排

## 编码前检查

- Phase2/Auth；单一问题：reset历史校验移出global锁。输入64cdf09/CR007/008/0049，A01 readonly receipt、A02 exact historical source已验证并同步294786d。
- 无Migration/API/依赖/算法参数/权限变化；reset现4-slot/5秒共用于fresh hash或history verify，change另项不顺改。
- 短准备UOW取当前Admin-CSRF、精确scope/fingerprint已完成hint、fullfirst+actual source。事务退出后真实KDF；false冲突、非bool未知拒绝。
- 原global写UOW重新身份+相同scope、reserve、原first相等及fresh实际source复核、原License/current末核仍保持。hint不是权限；无权、旧Session/受限Session不能重放。
- readonly miss后reserve发现first：无业务写，退出/回滚写UOW；最多一次重新准备+事务外verify。不允许无限循环、锁内KDF或猜测提交结果；秘密finally擦除。
- 原replay_verifier构造参数保兼容，历史校验改用既有Result Repository实际verifier的detached端口；不降低真实KDF或权限。错误/原原子self/丢确认链不变。
- 风险：准备与写间撤权/Session变化、first/source错配、race重试、slot泄漏；Unit及真实PG KDF时独立锁、实际撤权/注销/续期/目标后续变更、first中途由另一实际reset提交及错密码/版本/历史重放、Windows完整链回归。
- 回滚恢复旧串行history且保历史/0049，已知性能FAIL。计划最后20历史验证；本项功能PASS不等于总体1秒性能、正式安全、包或Gate通过。

## 实际结果

- Unit 1414 tests无失败（2既有跳过）；history事务外、fresh来源/身份/hint再核、false/非bool异常擦除及slot释放、miss后一次回退、连续miss有界失败均通过。
- 真实PG历史first在实际change3后保持；KDF时独立连接可取global/caller/Session锁；不做fresh hash。TEST_ONLY角色撤销、真实logout/renew、合成License撤销全部拒绝，目标另一次actual reset4仍可返回原first；九表仅外部操作变化，无本请求额外写。
- 实际另一reset在outer准备MISS后的hash阶段提交：正确密码一次重新准备后返回原first，错误密码CONFLICT_IDEMPOTENCY；仅一fresh hash、无第二次变更、九表完全保持另一次提交后状态、秘密擦除。原atomic reset并发/rollback/丢确认/self/真实change-history和publication回归通过。
- Windows actual factory/PG/Scrypt 20并发五组：GET P95 104.920ms（20成功）、fresh reset1598.708ms（20成功）、fresh change3195.512ms（20成功）、history reset1634.794ms（20成功，原6014.758ms）、history change8114.279ms（14成功/6个实际global55P03）。history两组九表均无写/original first保持；fresh SQL错误空；reset活动峰值4/最终0/等待超时0，process peak working set807972864 bytes。
- 整体验收脚本真实exit1 FAIL，旧Windows状态与publication回归通过不抵消性能/未改change历史功能FAIL；本轮不是网络/TLS/生产信任/持续负载验证。
- 开发wheel751120 bytes，SHA256 `e7fe249754e3d362a4042103c2003e29e1312aff81e2afd3ca263d2e7a50b439`；内部构建、不上传、不标安装包。无Migration/API/依赖/生产升级，兼容0049。
- Windows reset专门完整链A07实际运行exit0：真实Factory/HTTP create-login-reset→受限login→本人change→正常login/原first恢复、Cookie/ETag/缺信任源/构造失败与原state/publication回归通过。A03 reset历史锁段功能内部PASS，整个Auth性能FAIL。Next：change历史同样两阶段与bounded race，然后完整并发/资源/覆盖率等，不关闭CR008/Gate3。
