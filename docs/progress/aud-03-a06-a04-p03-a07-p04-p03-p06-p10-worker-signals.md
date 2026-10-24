# P06-P10 后台信号生命周期

2026-09-27，INTERNAL_PASS，非完整CLI/生产服务/发行/Gate通过。编码前Phase2/P06-P10，CR-AUD-004/ADR011；前置原Loop/真实组合已验。入口适配SIGINT/SIGTERM及Windows可用SIGBREAK；只主线程注册、实例进程级互斥、退出恢复原handler，不新增DB/API/权限/依赖或生产来源。

偏差/风险：Python signal callback不得调用可能加锁的Event.set或执行DB/I/O。选择callback只置本次内存标志；独立有界50ms桥接线程调用原loop.request_stop，唤醒空闲并请求排空。桥线程退出/join验证，handler恢复全尝试；失败安全报错，不假称退出，无法恢复信号环境时拒绝后续适配（需操作员重启进程）。不强杀、不自动dispose caller数据库，不把Windows硬TerminateProcess或未验Ctrl-Break当温和停止。

信号兼容补充（修改Loop前记录）：Windows主线程长期等待锁可能延迟执行Python signal handler，桥线程不能在handler尚未执行时看到标志。保原poll截止时刻，以最长50ms Event.wait小段实现空闲等待，留解释器处理signal机会，不缩短业务poll频率、不忙轮询，不改活动正文/DB超时。需实测60秒poll下信号能及时停止；活动阻塞I/O仍不强杀。

验收：Unit真实signal.raise_signal→Loop idle等待停止/handler恢复、非法/非主线程/重复注册/异常退出/部分安装失败恢复；独立合成子进程同解释器真实信号派发，安全退出/无码秘密输出。实际Windows Console Ctrl-C/服务控制/生产账户/其他平台未验，不能宣称完整CLI/安装包。撤未公开适配保历史，无迁移/升级。

Changed/Files：entrypoints/audit_worker_signals.py及worker_loop._wait_idle信号兼容调整，6新信号unit/1新poll截止unit、独立合成进程validation，STATUS/CHANGELOG/CR/DEC245。Migration/API/依赖无变化，0042保留，无生产操作/资源自动关闭。

Tests/Result：Windows11/Python3.13 1106后端无失败（2既有权限跳过）；原60秒wait定向信号测试确实延迟、5项60.052秒，调整后同5项0.122秒并追加<2秒断言；50ms小段不提前结束.15秒poll截止。真实解释器SIGINT idle及时stop、原handler恢复/主线程及嵌套拒绝/部分安装恢复、恢复失败poison后拒绝再次适配、异常保原pending；测试中故意恢复失败仅在unit最后人工还原该测试进程signal及poison，不在生产入口提供绕过。

两个独立合成Windows Python进程：实际signal.raise_signal(SIGINT)，idle60秒配置及时停止，活动已知命令发信号后仍完成一次且一claim，真实STOPPED、handler还原、无pending。未读取客户/秘密或强杀进程。信号是解释器派发，不是外部Windows Console控制事件/SCM/SIGTERM硬终止的证明。真实PG-Vault两Scope完整组合发布/撤权安全失败及原发布夹具回归通过。

Build：开发wheel 629579 bytes；SHA256 `b3028a394e461816191b4fd31e2492f59863acb7be2e1dcab2db8cc0d9fe3cb1`，非完整安装包。

KnownIssues/Next：活动阻塞I/O不强杀；外部Console/服务控制/正式来源、CLI/公平隔离/未知跨进程恢复/其他平台/质量/全Scope/Gate未完成。下一P06-P11 Windows安全来源及CLI装配前置核查。
