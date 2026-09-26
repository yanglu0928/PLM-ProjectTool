# P06-P11 Windows后台安全来源与CLI

2026-09-27，INTERNAL_PASS / FORMAL_SOURCE_BLOCKED，非生产/完整CLI发行/Gate通过。编码前Phase2/P06-P11，CR-AUD-004/ADR011；原Windows License来源，前置generic组合/信号已验。固定当前账户DB Credential Manager、包内Product公钥/本机选定MAC/可信时间/SystemActor和原Storage/Project授权，无新秘密参数/env来源。

兼容偏差：原License函数只接受普通DatabaseRuntime，后台需保WorkerDatabaseRuntime真实超时；保原函数新增显式Worker函数，固定原product/machine/integrity/_assemble，不增字段/授权/信任根。缺源仍拒绝、不供给秘密/License/写DB。无Migration/API/依赖变化，撤新入口保历史回滚。

CLI仅bootstrap路径及可选--once（LIMIT非服务就绪），新固定WorkerRef；正常/异常返回后只在Supervisor全部真实句柄不活的静止锁内dispose自身DB，活线程拒绝关闭/不强杀。验收Unit固定源/缺源关闭/CLI静态错误/活线程保护与临时PG/Vault合成来源链。正式公钥/目标账户材料、外部Console/Server2025服务/其他平台/质量/Gate/安装包仍待。

Changed/Files：worker_windows.py、windows_license_runtime新增worker专属函数（旧函数不变），Supervisor/Step/Loop quiescent Application保护关闭资源；5新unit、独立validation及runbook、STATUS/CHANGELOG/CR/DEC246。Migration/API/依赖无变化，0042保留，无生产升级或正式秘密供给。

Tests/Result：Windows11/Python3.13后端1111项无失败，2既有权限跳过。Unit固定DB来源不接参数、License固定product/machine/integrity/_assemble、缺源static错误/构造DB释放、CLI非法/缺配置/--once LIMIT非service readiness，真实活心跳拒绝quiescent且静止期禁止并行run。实际python -m CLI无参数退出2仅静态usage。

真实独立PG18/完整Schema：唯一临时Windows Credential Manager目标（测试映射，不触正式DEFAULT目标）、实际temporary Vault SystemActor；当前包内正式公钥确实缺失，原固定信任链startup拒绝、六表不写且构造DB释放。明确仅测试替换License Guard后，两Scope真实Windows工厂→process adapter→Loop→actual claim/heartbeat/物理发布/当前User停用安全FAILED、empty/stop不写，物理I/O在UOW外，静止释放DB，临时Credential删除。License新函数固定信任接线为Unit证据，不冒充正式密码/公钥/可信时间来源已供给或实际签名完整License复验；原发布回归通过。

Build：开发wheel 631338 bytes，SHA256 `ac1b33d248156e3b1ca05fcf3a7467d2b87570d6efe74b3d5b6f587d02988b02`；非完整产品安装包。首个补丁因旧行格式不匹配未应用，重新按实际内容应用，没有未验证覆盖；后续复验与构建成功。

KnownIssues/Next：正式包内公钥缺失/目标账户材料未供给，启动只能保持关闭；外部Console/服务、真实网络黑洞/异账户ACL、未知跨进程恢复/公平隔离/HTTP/质量/其他平台/完整Scope/Gate未完成。下一P06-P12真实Windows后台子进程/外部停止与装配收口，不等待普通继续授权。
