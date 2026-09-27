# CR-AUT-008 密码计算与全局管理写锁排队

日期2026-09-27；版本0.1.0.dev0；状态CONFIRMED_FAILURE_DESIGN_PENDING_IMPLEMENTATION。来源用户持续授权、冻结64cdf09/CR-AUT007/0049、testing-rules普通写20并发P95<=1秒；保留原实现与冻结版本，不修改算法强度或验收标准。

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

预处理可能引入TOCTOU、资源竞争、重放额外KDF及更多瞬时内存；需bounded资源策略与实际20并发测量，不引入缓存秘密、弱KDF、新认证机制或消息队列。正式编码前补完整proof生命周期/来源与两阶段事务边界设计及编码前检查。只选最小模块内调整，不顺改其他管理命令；如实保留仍未达标的结果。

预期无新Migration/API/依赖，保0049与原历史；回滚撤优化保持旧串行行为及已知性能FAIL，不回写密码或复活会话。实际覆盖当前普通/受限/自reset/唯一Admin/disabled、同不同Key竞争、KDF异常/非bool、预计算期间真实撤权/到期/版本变化、历史密码匹配、写后/precommit/丢确认，以及Windows完整HTTP与20并发正确性/P95。正式供给/TLS/实际浏览器/持续负载/三平台/包/Gate另验。本CR未关闭。
