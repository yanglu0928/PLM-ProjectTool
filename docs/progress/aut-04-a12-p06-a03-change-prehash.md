# AUT-04-A12-P06-A03 change 固定KDF移出写事务

编码前检查：Phase2；输入64cdf09/API02/0049、CR-AUT007/008，前置5a27020 reset优化和change六实际55P03。Auth内部change/access；实体不变，无Migration/API/依赖/License门槛变化。原本人普通/受限Session-CSRF、幂等及self末核保留。

DEC-20260927-326：短UOW真实本人proof+精确current不可变Credential hash/profile快照→退出释放DB锁→固定4 slots/5秒等待中真实current verify及新hash→原global写UOW重新prove/reserve。新写仅actualTrue且当前proof credentialID/version/required等于预源绑定；不复用旧proof授当前身份。source仅请求内repr隐藏DTO，非客户端/缓存/持久新密码等价物；异常严格bool/固定错误/finally擦两密码及释放slot。fresh false保持原错误；历史重放先原receipt/first双密码实际KDF，不因当前密码与原历史密码不同而拒绝，无License要求。历史KDF仍原写UOW，下一项优化。

验收：unit事务边界/源绑定/严格bool/hash/超限/无身份；真实PG KDF期间独立global/User/Session锁可取、logout/renew/disable/actual reset凭据变化拒绝无额外写、current密码错误/历史后来凭据恢复、原原子/Windows全链/20并发。回滚撤新Port/接线保历史恢复已知串行FAIL，不复活Session或回写密码。资源界只change局部非全Auth跨进程，正式材料/性能目标/包/Gate保留。

## 实施与真实结果

新增current_password_source精确当前不可变Credential source及无事务verify_password_source，原verify_current_password兼容入口保留。Service短UOW退出后4-slot真实current verify/new hash，再原global UOW重新获取当前身份，fresh额外精确Credential ID/version/flag绑定；false不提前拒历史，原first真实双密码保持。局部源PasswordHashResult repr隐藏，不新增持久hash/profile/密码等价物。

真实PG/Scrypt current verify和new hash期间独立native连接取得global/User/Session锁成功；实际logout、renew、disable、另一次真实reset四类竞争均AUTH_ACCESS_DENIED，九表仅保留已完成的独立操作；错误原密码AUTH_INVALID_CREDENTIALS，无新hash。普通及合成License-disabled本人change通过（保持冻结noLicense），TEST_ONLY角色供给变化时实际使用新User版本，不靠旧proof授写。

原原子change完整同不同Key/三Session含expired撤销/真实新登录/后来凭据历史双密码/五Port+三SQL/precommit回滚/丢确认恢复通过；Windows actual Factory change及reset两完整HTTP链/登录强制改密/构造失败安全关闭/缺正式材料拒绝及原发布均通过。

20并发真实Windows/PG/Scrypt：GET20成功/P95 111.960ms；reset20成功/P95 1631.262ms；change20成功/P95 3178.707ms（上轮14成功/6个503/P95 7559.374ms），实际SQL errors为空。20reset first/20change first、正常新凭据3和全部旧Session失效一致。功能本轮通过，但reset/change均超1000ms，性能仍FAIL，脚本真实exit1，不降低标准或声称正式服务性能已通过。

开发wheel749932 bytes，SHA256 `04ae6393396416af291fe68c5835f4f26d74c1ca6e7b8e1be830f982a5eca84f`；Schema0049保留，无Migration/依赖/API/生产升级，非安装包。下一P06A04测量固定KDF资源并发与历史重放锁段，选择有证据的有界调度；不得改弱profile或以20成功冒充1秒达标。正式供给/覆盖率/三平台/包/Gate仍待。

最终后端1400 tests无失败（2既有跳过）；change Service11 unit含source绑定/事务结束/strict bool及hash/异常/slot超限和真实5线程最多4活动校验。早期全量1398通过后补新hash错误与活动上界，再完整重跑1400通过；生产源码未再次修改。
