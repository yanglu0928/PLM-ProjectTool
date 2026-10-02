# AI-01-A03-P03-A02：可选 Provider 创建 HTTP

日期：2026-10-02；结果：`OPTIONAL_HTTP_ASGI_PG_PASS / PLATFORM_WRITE_COMPOSITION_CLOSED`。决策 `DEC-20261002-632`；本项完成冻结 `AI_PROVIDER_CREATE` 的显式可选 HTTP 边界与 Win11 隔离 ASGI/PG，默认及 Windows 平台模式暂不挂载写路由。

|编码前检查项|结论|
|---|---|
|当前 Phase/WBS|Phase 2；`AI-01-A03-P03-A02`|
|输入基线|冻结 API-01 JSON/Envelope/CSRF/幂等/ETag；API-03 POST `201 ProviderView`；DM-04/ADR-004 无凭据回显或自动外发|
|前置任务|内部创建/Audit/持久收据、A01不可变首版视图、0054和现有 Session/License/Secret用途证明已验证|
|涉及模块/实体|AI API 边界、可选应用装配；不改 Provider 实体/Schema|
|涉及 API|POST `/api/v1/admin/ai/providers`，仅显式注入；默认404|
|涉及权限|可信 Origin/Host、当前 Cookie Session、CSRF、DeploymentAdmin、License，SecretRef 必须是当前可用的 AI_PROVIDER_KEY|
|验收标准|201安全 ProviderView、原始同Key重放、不同载荷409、无Key/坏JSON/重复键/未知字段拒绝、普通用户/失效License/无效Secret拒绝、无明文/密文/内部异常、默认404；隔离 PG/ASGI及后端全量|
|风险|错误映射必须符合冻结码表；此接口仅配置，不证明 Provider 连通或授权数据外发|

实现：严格8192字节 JSON/重复键/精确字段/枚举/canonical UUID 解析，可信 Origin/Session/CSRF 与内部当前管理员、License、Secret用途证明、同事务 Audit/幂等收据；201返回A01不可变安全 ProviderView、强ETag/Location/no-store。缺License映射冻结403，错误Secret仅输出安全 `AI_PROVIDER_UNAVAILABLE` 503；创建不激活或外发。默认 `create_app()` 仍404，仅 `create_app(ai_provider_create_router=...)` 开放。请求/响应细节见 `docs/api-contract/ai-provider-create-v1-increment.md`。

验证：定向合同3项PASS；Win11隔离PostgreSQL18.6/Alembic head+ASGI真实Session：默认404、管理员201安全投影/同Key重放/异载荷409、普通用户404、失效License403、错误Secret503、原始URL422、明文Key字段400、Session撤销401，数据库仅一 Provider/一创建Audit；后端全量1925运行/3跳过、0失败。开发wheel SHA-256 `5ecb0d46d4d00e92e9f03b13026374492e981f3ff99c649f1b1a6550d08a20c1`；临时库删除，PG恢复原停机状态。

兼容/升级：无 Schema/依赖/Breaking API，需已有0054；不注入Router即可代码回滚，已创建Provider/审计/收据不物理删除。已知问题：Windows显式写组合未挂载、正式账户信任/目标环境/Provider Test/激活/模型路由/逐次外发/质量/Gate/UAT/可用包未验；39份旧平台隔离脚本夹具仍待更新/重跑。下一项 `AI-01-A03-P03-A03` 将 POST 仅挂入Windows `--platform-write` 并隔离PG验证，读模式仍拒绝。
