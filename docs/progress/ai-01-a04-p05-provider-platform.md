# AI-01-A04-P05：Windows 显式平台 Provider 只读装配

日期：2026-10-02；结果：`WINDOWS_EXPLICIT_PLATFORM_ASGI_PG_PASS / PRODUCTION_TRUST_PENDING`。依据 `DEC-20261002-630`，本项只将已验证的 Provider GET/LIST 可选 Router 注入现有 Windows 显式平台读/写模式，不扩大默认应用或登录模式。Phase 2/Gate 3 仍开放。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase/WBS|Phase 2；`AI-01-A04-P05` 平台装配|
|输入基线|冻结 `AI_PROVIDER_GET/LIST`；已验证 P01～P04 详情、分页、专用钥只读来源和可选 HTTP|
|前置任务|迁移0054、当前 Windows 显式平台组合、Session/License/管理员边界已存在|
|涉及模块/实体|仅 Windows 生产入口组合及装配合同；Provider 实体/Schema 不改|
|涉及 API|冻结 GET/LIST 在 `--platform`、`--platform-write` 可用；默认/`--login` 保持404|
|权限与信任|复用真实 Session、当前部署管理员、License Guard；专用 Provider 游标 KeyRef 缺失导致整个平台模式启动失败，不降级|
|验收|隔离 PG18+真实 ASGI 双模式分页/详情/脱敏/ETag、非管理员与 License 拒绝、默认关闭、缺钥失败关闭；后端全量回归和开发 wheel|
|风险|合成钥与合成 License 不能证明正式目标服务账户可信材料及部署可用性|

## 结果与验证

入口在两个显式平台模式共用 `AIProviderMetadataService`、现有真实 Session、部署管理员和 License Guard，并从 Windows 当前账户独立 Provider 游标钥解析器取签名钥。默认应用与 `--login` 不挂载该 Router。缺钥或构造失败走原有统一 `ProductionLoginStartupError` 失败关闭和资源清理。合同测试另验证双模式缺钥均清理数据库运行时，异常不回显内部文本。

Windows 11 临时 PostgreSQL 18.6 库应用 Alembic `head`，种入纯合成两用户、三 Provider/Secret，用真实会话与 HTTP 验证两个显式模式各自两页列表、详情强 ETag、固定遮罩、普通用户404、License拒绝403；登录模式404。两个显式模式在专用游标钥缺失时均拒绝启动。隔离库删除，PG 恢复原停机状态。后端全量 `1921` 运行、`3` 跳过、零失败；开发 wheel SHA-256 `909faf0da6e962ddefe144c90809670cce74d1f36560224bd7456cacccc1dba5`。未执行真实目标账户或三平台发行验证。

兼容/升级：无新 Schema、依赖或 Breaking API；需先迁移至0054，并为运行显式平台模式的 Windows 服务账户供给独立 Provider 游标 KeyRef，升级前备份并验证恢复；缺钥会阻止显式平台启动。回滚代码装配不删除 Provider 数据；已产生的游标签名不可用时需重新分页。已知问题：正式服务账户密钥/License/Secret 主钥、Provider 写 HTTP/激活/路由/逐次外发、质量、Server 2025/Debian、UAT/Gate和可用包未验。下一项优先补 `AI-01-A03-P03` Provider 创建 HTTP，并保持生产外发关闭。
