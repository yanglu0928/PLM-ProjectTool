# P03-A07-P04-P01 Worker 专用数据库等待边界

日期：2026-09-26；状态：PASS（Worker opt-in服务器/连接/池边界；非全网络硬截止）。

编码前检查：Phase2/P03-A07-P04-P01；前置周期协调PASS但join无法终止阻塞SQL，现有runtime普通API默认池等待30秒且未设SQL超时。单一问题为opt-in Worker专用runtime/UOW，不改变普通API/通用数据库默认，不增新Schema/角色/依赖或冻结架构。

策略：专用池/连接建立超时、每个新Worker短事务SET LOCAL lock/statement/transaction timeout及读回核验，PostgreSQL18强检查；事务超时终止连接，底层原UOW负责rollback/close，池在失效后恢复。普通池保持旧行为。所有参数严格有限正整数，lock < statement < transaction；参数绑定，不拼Secret/环境路径。

依据：[PostgreSQL18 timeout说明](https://www.postgresql.org/docs/18/runtime-config-client.html) 与 [libpq连接参数](https://www.postgresql.org/docs/18/libpq-connect.html)。transaction timeout终止会话，不能误作query取消后仍可commit；事务local设置不污染后续普通UOW。不设置服务器全局配置。

风险：超时短事务失败必须由Owner安全传播/恢复，不能标发布成功；多host连接超时非单一总时限，网络黑洞不保证客户端及时收到server timeout。本项不声称全网络硬截止/正式Worker停机，通过实际PG锁、pg_sleep、transaction超时/连接恢复/池满超时验证。

验收：strict policy/default不变、真实SQL设置和LOCAL恢复、真正另一连接锁等待限时失败且写回滚、慢query取消、多statement总transaction终止/后续新连接可用、专用池满等待超时、现有受权心跳/周期协调在该UOW下锁超时退出且容量真实释放。生产装配/单次协调与整体包待。

## 验证结果

- Changed/Files：新增Platform infrastructure `worker_database.py`，strict WorkerDatabaseLimits/专用factory与LOCAL核验UOW，4unit、真实PG validator、配套进度/状态/决策/版本说明。原普通API数据库选项不改，SQL参数绑定，不设服务器全局值。
- Migration/API/依赖/升级：无，head0042；无新角色/Scope/HTTP，未挂生产Worker。按后续显式Worker装配使用，不需数据迁移或新密钥。撤opt-in factory保所有历史可回滚。
- 默认：lock1000ms < statement2000ms < transaction5000ms，pool/connect各2秒，4槽/overflow0；仅有限正整数与严格顺序。可配置至事务60秒上限，仍需实际吞吐/最小资源验证，不宣称默认适合所有极限capture数据。
- Tests：4新unit实际执行，参数含bool/范围/顺序拒绝、exact LOCAL/no commit/unsupported PG或不生效核验拒绝、ready关闭与dispose/普通池30秒默认保持。首次全量4错误是测试Mock没有context magic methods，修正MagicMock后4项及全量重新执行；首次validator字典转换CursorResult错误已修正后实际PG全链路重跑。
- 实际PG18临时库：LOCAL三配置精确生效且下一普通UOW恢复原值；真实Audit append后慢SQL statement超时57014整UOW回滚；多条各自短query总transaction终止连接，失效池连接恢复ready；真正单槽池占满第二连接等待1秒超时；另一连接User FOR UPDATE实际阻塞心跳，服务器lock timeout使受权周期线程安全AUDIT_UNAVAILABLE退出，期限未写、实际join完成，释放后同Job/槽可复用。
- 原实际发布/故障回滚/双Scope与取消锁竞争回归通过。Windows11/Python3.13全后端982项无失败（2既有符号链接权限跳过）；开发wheel成功582385字节，SHA256 `19284b0e6bc70d4aa1dc8b98717d63220d28aef275f2431dbdd8b92e5ffff8ac`，不是可用安装包。
- Result/Known Issues：只证明服务器SQL与池等待边界，connect配置存在但未模拟连接黑洞；libpq多host连接及pre_ping/读写网络故障无总墙钟截止证明，不能声称正式停机无阻塞。测试License合成/系统Vault临时；正式账户/三平台/性能/质量/Gate3/UAT/整个包仍待。
- Next：P03-A07-P04-P02 审计Worker单次协调原源恢复/捕获渲染发布及周期收尾；正式失败取消Owner和主循环/网络停机策略按实际依赖核查，POST保持关闭。
