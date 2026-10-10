# AI-01-A03-P03-A03：Windows 显式写平台 Provider 创建装配

日期：2026-10-02；结果：`WINDOWS_WRITE_PLATFORM_ASGI_PG_PASS / PRODUCTION_TRUST_PENDING`。决策 `DEC-20261002-633`，仅 `--platform-write` 挂载 Provider POST；默认/登录模式保持未挂载，`--platform` 保持只读。

|编码前检查项|结论|
|---|---|
|当前 Phase/WBS|Phase 2；`AI-01-A03-P03-A03`|
|输入基线|冻结 API-03 `AI_PROVIDER_CREATE`；A01首次安全视图、A02可选POST；现有Windows显式写组合|
|前置任务|0054、Session/CSRF、License、Secret用途证明、收据/Audit及可选POST已隔离验证|
|涉及模块/实体|仅生产组合根/装配测试；AIProvider实体/Schema不改|
|涉及 API|`--platform-write` POST 201；`--platform` 无POST；默认/登录无POST|
|涉及权限|沿用当前写组合的真实Session、受控Origin、管理员、License和Secret；缺写依赖整模式失败关闭|
|验收标准|Win11隔离PG18/ASGI写模式创建/重放、读模式不可创建、默认/登录关闭、缺依赖失败关闭、权限/License/Secret不泄露；后端回归和wheel|
|风险|合成信任源不等于目标服务账户正式密钥/发行可用；GET同路径使只读模式POST按405而非404|

实现：写组合复用当前 Session/Origin、License Guard、Secret用途证明、同事务 PG UoW/幂等收据/Audit，创建服务或Router构造失败则整个写模式拒绝启动并清理资源。读模式完全不构造 Provider 写服务；同一路径已有GET，因此读模式 POST 返回冻结的405安全错误而非404。

验证：Win11 隔离 PostgreSQL18.6/Alembic head+ASGI真实 Session，默认与登录 POST404、只读 GET200/POST405、写模式 POST201首版脱敏视图/同Key重放/异载荷409、普通用户404/License403、数据库恰一Provider/一创建Audit PASS。合同测试验证缺写服务依赖时写模式失败关闭与资源清理，读模式仍可构造。后端全量1926运行/3跳过、0失败；开发wheel SHA-256 `678c794080f69e4c422d4e1e5478b900c5df6af1ce3136976ae9c0151c9e9619`。临时库删除，PG恢复原停机状态。

兼容/升级：无 Schema/依赖/Breaking API；需既有0054和写模式既有正式 License/Secret/数据库信任材料，且运行账户须具独立Provider只读游标钥。缺任一写依赖应拒绝写模式启动。撤除组合注入可代码回滚，已创建Provider/审计/收据仍保留。已知问题：正式目标账户信任/密钥备份恢复、Server2025/Debian、Provider PATCH/Test/激活/模型路由/逐次外发、质量/Gate/UAT/可用包未验证；39份历史平台脚本夹具仍待维护。
