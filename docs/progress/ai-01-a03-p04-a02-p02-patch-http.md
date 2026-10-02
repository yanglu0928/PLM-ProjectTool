# AI-01-A03-P04-A02-P02：可选 Provider 配置 PATCH HTTP

日期：2026-10-02；结果：`OPTIONAL_PATCH_ASGI_PG_PASS / PLATFORM_WRITE_COMPOSITION_CLOSED`。按 `DEC-20261002-636` 完成冻结 PATCH HTTP 边界，默认及Windows正式组合暂不挂载。

|编码前检查项|结论|
|---|---|
|当前 Phase/WBS|Phase 2；`AI-01-A03-P04-A02-P02`|
|输入基线|冻结API-01 PATCH部分DTO/If-Match/强ETag、安全Envelope；API-03 Provider PATCH 200/S,L,C,M,A；DM-04历史|
|前置任务|0054、P01内部部分合并/原始结果、Session/License/Secret及安全投影已隔离验证|
|涉及模块/实体|AI API边界与可选应用装配；Provider实体/Schema不变|
|涉及 API|PATCH `/api/v1/admin/ai/providers/{provider_id}`；默认/正式组合暂不装配|
|涉及权限|可信Origin/Host、Session、CSRF、DeploymentAdmin、License、强If-Match；Secret仍仅引用|
|验收标准|200配置版本/ETag；仅受控非空部分字段，Kind/明文Key拒绝；缺/弱/错If-Match、错权限/License/Secret、异Key重放；无Header按版本冲突；默认关闭；隔离ASGI/PG及全量回归|
|风险|内部收据状态不能透传为HTTP201；可选Key不得变成冻结合同外的必填请求条件|

实现：可选 Router 使用强If-Match、可信Origin/Session/CSRF、受控部分JSON和P01锁内合并结果。Kind/null/未知字段及明文Key字段拒绝；客户端幂等Key可选，缺省生成本次随机收据Key；返回冻结200配置版本/强ETag，无Secret值。不存在/无权404，失效License403，版本/状态/幂等409，缺If-Match428，错误Secret安全503。内部收据状态不外露。实现合同见 `docs/api-contract/ai-provider-patch-v1-increment.md`。

Win11隔离PostgreSQL18.6/Alembic head+ASGI真实Session：默认404、无Key首次200/同If-Match重试409、有Key首次200/同Key重放相同结果/异载荷409、部分字段升版、普通用户404、License403、错误用途Secret503、Kind400、缺If-Match428、撤销Session401及两次Audit/三版配置 PASS。定向合同3项、后端全量1931运行/3跳过、0失败；开发wheel SHA-256 `e78f36ce3454e29311b7f64543a94b4bfa8e3b331109d66feb417eaaf99cbe6e`。临时库删除，PG恢复原停机状态。

兼容/升级：无Schema/依赖/Breaking API，需已有0054；不注入Router即可代码回滚，历史配置/审计/收据不删除。已知问题：Windows显式写组合未挂载；正式目标账户信任、Provider Test/激活/模型路由/逐次外发、质量、Server2025/Debian、Gate/UAT/可用程序包未验；旧平台脚本夹具待更新/重跑。下一项 `AI-01-A03-P04-A02-P03` 仅Windows显式写模式挂载PATCH并隔离PG验证。
