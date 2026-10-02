# AI-01-A03-P04-A02-P01：Provider 受控部分更新内部命令

日期：2026-10-02；结果：`INTERNAL_PARTIAL_PATCH_PG_PASS / HTTP_CLOSED`。冻结 API-01 指定 PATCH 缺失字段不修改；原内部追加只收完整配置。依据 `DEC-20261002-635`，完成锁内合并和原始变更集幂等，不提前开放 HTTP。

|编码前检查项|结论|
|---|---|
|当前 Phase/WBS|Phase 2；`AI-01-A03-P04-A02-P01`|
|输入基线|冻结 API-01 PATCH/If-Match/幂等、API-03 Provider PATCH、DM-04不可变配置历史|
|前置任务|0054、内部完整追加/首版结果、收据/Audit/Session/License/Secret证明已验证|
|涉及模块/实体|AI Application/Repository；已有 Provider 与配置版本，不改Schema|
|涉及 API|本项无公开路由；为后续可选PATCH预备内部命令|
|涉及权限|当前 Session/CSRF/DeploymentAdmin/License、行锁、If-Match、状态/Kind、Secret用途及Audit/收据不放松|
|验收标准|受控非空部分字段、锁内合并、版本追加；同Key原始重放不依赖后续当前态；异载荷/错版本/失权/失许可/Secret及审计失败关闭；旧完整追加入口兼容；隔离PG/全量测试|
|风险|路由预读当前配置会导致重放指纹漂移；不允许把Kind或任意字段作为PATCH透传|

实现：新增 `PatchAIProviderConfig`/`patch_result()`，只接受非空受控字段子集（显示名、EndpointPolicyRef、SecretRef、地区、外发类别、能力），拒绝Kind/null/未知字段与错误类型。规范化原始变更集、ProviderId及If-Match版本形成指纹；当前管理员/License核验后先预约与完整追加分离的PATCH收据，历史重放从不可变配置版本和原If-Match返回原始200语义/强ETag。新写入同事务行锁、读取当前完整配置、合并校验与证明Secret、追加版本/Audit/收据。旧完整追加入口与历史收据保持不变。

Win11隔离PostgreSQL18.6/Alembic head：只改显示名时其他字段不变、同Key重放、异载荷409、普通用户/失效License/错用途Secret/错版本拒绝、二次局部升版、审计失败原子回滚、双线程同Key单胜、后续配置/状态/Secret变化后原结果不漂移 PASS。A01原始结果及旧完整追加两套隔离PG回归 PASS；后端全量1928运行/3跳过、0失败；开发wheel SHA-256 `babaad45fc95aaf9f38cd49b659c4ed3473564be2b65e0d231974073914175d7`。临时库删除，PG恢复原停机状态。

兼容/升级：无Schema/公开API/依赖变化；需既有0054；撤新入口可代码回滚，已产生版本/审计/收据不删除。已知问题：可选PATCH HTTP未实现，正式账户信任/Provider Test/激活/模型路由/逐次外发、质量、Server2025/Debian、Gate/UAT/可用程序包未验；旧平台夹具待更新/重跑。下一项 `AI-01-A03-P04-A02-P02` 可选PATCH HTTP及隔离ASGI/PG验证。
