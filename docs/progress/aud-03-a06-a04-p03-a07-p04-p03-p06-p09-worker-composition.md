# P06-P09 后台运行组合与启动检查

2026-09-27，INTERNAL_PASS，非正式生产/发行/Gate通过。编码前Phase2/P06-P09，CR-AUD-004/ADR011；前置原单步/Loop/所有安全Owner与证据已验。入口组合根显式接入有界PG18 runtime、完整migration head、已有Project授权/License Guard、受控SystemActor及Document owned存储Port；实际Repo/Jobs Port固定，无注入伪Root/假Job事实。

不新增配置密钥/环境变量/Schema/API/技术栈。缺依赖、DB非ready、Schema非当前或identity无效则拒绝构造，无后台线程/claim。License由正文操作实时检查，启动不把License有效性当安全收尾前提，过期时安全失败/取消仍应可运行；禁止据此称生产License已供给。caller保数据库生命周期，组合不关闭/创建资源/写业务或生成秘密。

验收：Unit设置边界/缺源/启动关闭/同Supervisor及identity固定/不在启动授业务权限；真实PG/Vault两Scope实际组合根经Loop准入/发布/撤权失败/stop，不读客户资料；版本与旧链回归。正式Windows密钥供给/CLI信号/服务账户/公平隔离/未知恢复/其他平台/Gate/安装包仍待。撤未公开组合保历史回滚。

Changed/Files：entrypoints/audit_worker.py非CLI显式组合、不可变有界AuditWorkerSettings；4新unit、独立validation与STATUS/CHANGELOG/CR/DEC244。Migration/API/依赖无变，Schema仍0042，读migration元数据不写业务，无生产升级/秘密供给。

Tests/Result：Windows11/Python3.13后端1099项无失败，2既有权限跳过；unit当前Schema/DB/身份/缺源关闭、同Supervisor/identity、启动不调用License.require_valid或文件提升；实际独立bounded PG18/current完整head/临时Vault SystemActor两Scope，固定真实Repo/原授权/合成License/实际存储通过组合Loop真实PENDING至发布、当前User撤权安全FAILED、empty/stop无写、原发布回归通过。实际存储在活动UOW外，由真实计数wrapper检查。合成License不是正式公钥供给，当前generic组合不可冒充Windows生产CLI。

异常记录：首次integration在连接已有测试PG前超时未进入本项case；确认postgres原进程仍活、55432 accepting connections后重跑通过，未重启/重建旧数据库。后端测试一次报告8404.191秒，原因未验证，不推断性能达标；仅记录功能无失败。工具首个路径搜索PowerShell花括号语法错误已用目录过滤重查，不影响程序。

Build：开发wheel 628381 bytes，SHA256 `c9d4e14fe2a7d5270af45b3b4f4c5d3496c8ab1b3b8dd7bfdec40abda15e0691`；非完整安装包。

KnownIssues/Next：正式Windows/Server2025来源/CLI/信号/服务生命周期、未知跨进程恢复/公平隔离/HTTP/质量/其他平台/完整Scope/Gate待；下一P06-P10进程生命周期/信号适配。数据库由caller管理，不允许组合在活任务下擅自dispose。
