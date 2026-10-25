# AUT-04-A12-P06-A02 reset 新密码计算移出全局写锁

编码前检查：Phase2/Gate3未通过；输入64cdf09/API02、CR-AUT007/008、0049，前置8f610ae实际20并发锁超时证据。模块Auth内部PasswordResetService；实体仍User/Credential/Session/first/receipt/Audit；API/权限/算法/Schema/依赖不变。本项仅reset首次new hash，不顺改change或历史KDF。

DEC-20260927-325：原License预检→短独立UOW真实normal Admin-CSRF proof→退出回滚释放所有DB锁→固定Scrypt临时密码hash→新UOW原全局锁/真实当前Admin-CSRF重验→原receipt/版本/写入/first/Audit/末核/commit。预proof不传客户端/不缓存，不作为写权限；写事务新proof为唯一授权来源，目标expected仍真实Repository检查。历史重放仍原first真实KDF/当前权，预hash不影响历史密码校验，虽额外计算需后续优化。预计算期间撤权/失效/版本变化须安全拒绝，不跳过self末核。

资源：reset预hash进程内固定4 slots（单次固定128MiB工作内存/256MiB OpenSSL上界），等待最多5秒，超限固定unknown错误，不降低KDF、不增加持久队列/缓存或依赖。所有路径释放slot/擦除原缓冲；该局部界不冒充全Auth跨进程资源上界。验收unit上下文边界/严格输出/拒绝，真实PG hash期间独立连接可取global+actor锁、实际角色/Session撤销/目标版本变化及License末核、旧原子/HTTP/Windows完整回归与20并发测量。性能不预判PASS。

回滚撤本Service优化保0049/全部历史，恢复已知串行性能FAIL；不复活Session/回写Hash。change/replay/整体1秒目标/正式trust/三平台/包未完成。本项代码前已记录。

## 执行与验收

reset新hash已移出全部DB事务及global锁；短proof不被用于后续授权。新增unit验证上下文结束→hash→新global锁→再次prove、预proof拒绝/坏hash/异常/slot超时无写及擦除；真实5线程最多4活动hash。真实PG/Scrypt计算期间独立native连接获取global/actor/Session锁成功，实际角色撤销、logout、renew和target disable版本变化均拒绝且九表仅保留已发生的独立操作，无reset半写；合成License撤销同样回滚。角色供给明确TEST_ONLY。

原完整原子reset同不同Key/故障/丢确认/disabled/坏旧profile修复/self唯一Admin恢复、实际Windows完整HTTP及真实登录改密恢复/六构造故障/缺正式材料拒绝、原双Scope发布回归通过。只reset预hash优化，未静默改动change、历史验证、API或Schema。

实际20并发复验：GET20成功/P95 106.973ms；reset20成功/P95 1634.810ms（原5653.504ms），明显改善但仍FAIL于1000ms；change14成功/6个503/P95 7559.374ms，六实际SQL55P03仍global advisory lock。失败原凭据/User/Session保持无change first/Audit，完整性20/14/6吻合。脚本原回归完成后exit1明确FAIL。不能以reset改善抵消原普通写验收要求。

开发wheel749632 bytes，SHA256 `2c19214c1a91723062dadffbd7d5e6108a6dbafb9ab985f00731e43e44ec888e`，非安装包。Schema0049、无新Migration/依赖/生产升级。早期只读shell出现一次CLR启动崩溃（未运行目标命令/无修改），换非login shell读回成功，非业务失败；未重复任何已确认活的验证进程。

最终后端1393 tests无失败（2既有跳过）；其中reset Service 9 unit包含真实5线程4-slot界。初次全量1392通过后补slot并发测试，最终全量重跑1393通过，生产源码未再修改。

下一P06A03：本人change固定KDF预计算绑定实际不可变Credential，并保历史重放/当前身份/最终专用证明和资源界；随后history与20并发继续调优。当前本项边界正确性通过，整个性能/CR/Gate/包仍未通过。
