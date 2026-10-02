# AI-01-A03-P03-A01：Provider 创建结果前置检查

日期：2026-10-02；结果：`INTERNAL_CREATE_VIEW_PG_PASS / HTTP_CLOSED`。冻结 `AI_PROVIDER_CREATE` 要求 `201 ProviderView`，原内部 `AIProviderCreateService.create()` 只返回 UUID；如 HTTP 在提交后读取当前配置，同一幂等键可能因后续配置追加/状态变化得到不同结果。本项建立首版不可变响应入口，不提前开放 HTTP。

|编码前检查项|结论|
|---|---|
|当前 Phase/WBS|Phase 2；`AI-01-A03-P03-A01` 原始创建视图|
|输入基线|冻结 API-01 幂等/ETag、安全 Envelope；API-03 `AI_PROVIDER_CREATE` 的 201 ProviderView；DM-04 Provider 配置版本|
|前置任务|迁移0054、内部创建/收据/Audit、只读安全投影已验证|
|涉及模块/实体|AI Application/Repository；既有 AIProvider 与首版不可变配置，不改 Schema|
|涉及 API|本项无公开路由；为后续可选 POST 预备结果|
|涉及权限|现有 Session+CSRF+DeploymentAdmin+License+Secret用途证明、持久幂等和 Audit 不放松|
|验收标准|首次/同 Key 同 payload 返回一致的安全首版 ProviderView；后续配置/状态变化后重放仍固定；坏 Key/权限/License/Secret/并发失败关闭；旧 UUID 入口兼容；单元+隔离 PG 回归|
|风险|不可把最新状态误用于历史创建响应；不能将 Key/Secret 全值或内部异常回显|

决策见 `DEC-20261002-631`。新增 `create_view()`，共享既有当前 Session/CSRF/管理员、License、Secret用途、同事务 Audit/收据，并只从首版不可变配置投影原始 `CONFIGURED/v0`，SecretRef 固定遮罩。原 `create()` UUID 入口保持兼容。新建与重放都在事务内拿首版视图，视图缺失则创建/Audit/收据一起回滚；原始结果不跟随后续配置、状态或 Secret 可用性改变。

Win11 隔离 PostgreSQL18.6/Alembic head：首次/同Key重放、旧UUID入口、配置升版+状态/Secret变化后同Key重放、完整SecretRef不回显，以及投影失败的写/Audit/收据回滚 PASS。既有创建和配置追加两套隔离 PG 验证 PASS；后端全量1922项运行、3跳过、0失败。开发 wheel SHA-256 `aaa8fb02a4856c1fe3a7408d2f036d3f018c215ac35cf5985bff3ad86ce53132`；临时库已删除，PG 恢复原停机状态。

兼容/升级：无 Schema、公开 API、依赖变化；需已有0054；撤除新入口不修改历史数据。已知问题：冻结 POST HTTP 尚未接线；正式服务账户信任/外发、Server2025/Debian、质量/Gate/UAT/可用程序包未验证。下一项 `AI-01-A03-P03-A02` 可选 Provider 创建 HTTP 合同与隔离 ASGI/PG 验证。
