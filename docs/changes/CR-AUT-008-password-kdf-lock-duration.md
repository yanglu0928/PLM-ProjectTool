# CR-AUT-008 密码计算与全局管理写锁排队

2026-09-27/AUT-04-A12-P06-A04-P02-A02补充：reset/change历史first精确Credential源、无DB真实KDF、fresh full-first/source无KDF复核已内部通过；原verify兼容委托。1409 tests/实际PG reset2-change3-later4历史真实KDF/独立锁/READ ONLY末核/九表无写/原原子与发布/wheel通过，正向License合成。Service未接入，性能未重跑/上轮FAIL保留，CR OPEN；无Migration/API/依赖，回滚接口保历史，下一reset编排与bounded race后change，风险/计划见progress与DEC329。

日期2026-09-27；版本0.1.0.dev0；状态CONFIRMED_FAILURE_DESIGN_PENDING_IMPLEMENTATION。来源用户持续授权、冻结64cdf09/CR-AUT007/0049、testing-rules普通写20并发P95<=1秒；保留原实现与冻结版本，不修改算法强度或验收标准。

P06A02最新：reset新hash预计算已实施/真实PG边界与撤权竞争、原原子及Windows完整链通过。20并发reset20成功/P95 1634.810ms（原5653.504ms），仍未达1秒；change尚原实现，14成功/6实际55P03、P95 7559.374ms。旧状态/发布及失败无半写通过，整个CR仍FAIL/OPEN；以下拟选方向保留实施前历史，下一change和history优化，不降低标准。

P06A03最新：本人change actual current不可变Credential source短UOW退出后verify/new hash及4-slot调度已实施；fresh写UOW重新身份/相同Credential ID/version/flag，历史仍original first双KDF。真实锁释放/注销续期停用实际reset竞争无额外写、原原子及Windows两链通过。20并发GET111.960ms/reset1631.262ms/change3178.707ms；三组全20成功，SQL错误空，20/20first与新凭据/旧Session一致。本轮功能恢复，但普通写P95仍FAIL，CR保持OPEN，下一有界资源校准及history锁段优化。

P06A04P01最新：test-only8/16/20-slot顺序真实校准，新写均20成功/无SQL错误；reset P95 1110.913/1064.465/957.033ms，change2142.248/1674.781/1446.926ms，process峰值工作集约1.13/2.13/2.63GiB，均无slot等待超时。只reset20-slot单轮达标，整个普通写仍FAIL，生产4不改。另原4-slot历史reset20成功/P95 6014.758ms、change14成功6个实际global55P03/P95 7908.389ms，九表快照不写、first保持。下一优先历史KDF事务外source与最终重新授权，不以提高资源掩盖全局锁缺口；CR OPEN、无生产变更。

## 实际证据

P06A01在Windows11、32逻辑CPU/约31.63GiB RAM、原SQLAlchemy默认pool5+overflow10、真实PG18/Scrypt、实际Windows写Factory的ASGI完整HTTP处理路径测试。20独立客户端同时放行，独立目标reset及本人change；正向License/密钥来源合成，无客户资料/秘密外发。

带SQLAlchemy实际handle_error诊断轮：Session GET 20/20 200，P95 109.572ms；reset 20/20 200，P95 5643.324ms；change 14/20 200、6/20 503，P95 7301.993ms。六实际数据库错误均`55P03`、语句种类`deployment_advisory_lock`，未打印SQL参数、凭据或连接串。失败用户仍Credential/User版本2、两条凭据、原受限Session有效、没有change first及PASSWORD_CHANGED审计；20 reset first/14 change first实际计数吻合。另两轮观测同样14成功6失败，不改写失败证据。

原Service在global `pg_advisory_xact_lock`内执行固定Scrypt：reset一次hash，change当前密码verify及new hash。锁超时5秒；真实55P03与代码结构共同确认全局锁排队是503直接原因。不据此假设移出KDF就能达1秒；CPU/内存带宽及其它锁需实际复验。本轮原Windows状态和双Scope发布回归通过，不能抵消密码并发FAIL。

最终脚本退出语义复验：GET113.978ms/reset5653.504ms/change7301.987ms P95；20/20/14成功及6个同类55P03，失败回滚和原回归后实际exit1。脚本不因成功收集诊断而在验收自动化返回绿色结果。

## 比较及拟选方向

1. 降低Scrypt参数或省略当前密码/权限/License/CSRF/first校验：不选，破坏安全与冻结语义。
2. 增大锁超时/连接池并宣称达标：不选，只掩盖排队且不达1秒。
3. 去掉全局锁或异步受理密码变更：不选，会影响最后Admin/锁序/冻结同步HTTP及未知提交恢复。
4. 预认证、释放短只读事务后计算固定KDF，再进入原全局原子事务完整重验：作为下一分项设计方向。保持原锁序、first/receipt/Audit、全Session撤销、self专用末核、License前后和密码擦除；不缓存权利或持久化密码等价物。必须证明预计算绑定实际不可变Credential，事务内认证不因预计算被跳过，预处理撤权/凭据变化/Session续期或过期仍安全拒绝，历史重放不被“与最新密码不符”错误拦截。拟选不代表已实现或验证。

## 风险、迁移、回滚及验证计划

P06A03实施前：本人change短UOW新读实际proof及current hash/profile，退出后4-slot/5秒真实校验+新hash，原global事务再prove及Credential ID/version/flag绑定，fresh必须true；历史仍原不可变first双密码KDF，current false不能提前拒历史。源DTO只内存/隐藏repr，无新缓存或权限，资源上界仅局部；当前原子/错误/License-free/self末核均保。实测DB锁释放与logout/renew/disable/实际reset凭据竞争，未预判1秒达标。

P06A02实施前精化：先仅reset新临时密码hash；当前Admin-CSRF短UOW结束后计算，进程内固定4 slots/5秒有界等待，写事务仍原global锁+重新获取实际current proof/版本/receipt/全部末核。预proof不复用为授权；历史KDF暂仍原事务、每请求额外预hash，change不顺改。验证hash时原事务已退出/独立PG获取global及actor锁、预处理实际撤权/Session失效/目标版本变化和原完整链。局部resource界不声称整个Auth或跨进程已限流，20并发原标准保留。

预处理可能引入TOCTOU、资源竞争、重放额外KDF及更多瞬时内存；需bounded资源策略与实际20并发测量，不引入缓存秘密、弱KDF、新认证机制或消息队列。正式编码前补完整proof生命周期/来源与两阶段事务边界设计及编码前检查。只选最小模块内调整，不顺改其他管理命令；如实保留仍未达标的结果。

预期无新Migration/API/依赖，保0049与原历史；回滚撤优化保持旧串行行为及已知性能FAIL，不回写密码或复活会话。实际覆盖当前普通/受限/自reset/唯一Admin/disabled、同不同Key竞争、KDF异常/非bool、预计算期间真实撤权/到期/版本变化、历史密码匹配、写后/precommit/丢确认，以及Windows完整HTTP与20并发正确性/P95。正式供给/TLS/实际浏览器/持续负载/三平台/包/Gate另验。本CR未关闭。
# 2026-09-27 补充：AUT-04-A12-P06-A04-P02-A01

仅新增 caller UOW 已完成收据只读提示，标量投影、无 autoflush/行锁/提交，strict scope/fingerprint，未知固定拒绝；不代表授权，不替代原 reserve/complete、first 历史来源、当前身份及末核。编码前风险与验证见对应 progress/DEC-328。1405 tests/真实PG只读可见性/锁竞争/九表无写及旧原子/发布回归、开发wheel通过；密码 Service 尚未调用，历史 KDF 锁段与性能 FAIL 保留。兼容0049无Migration/API/依赖，回滚撤未接入方法保历史；下一 detached first/Credential 及 Service 编排，CR/Gate 不关闭。
