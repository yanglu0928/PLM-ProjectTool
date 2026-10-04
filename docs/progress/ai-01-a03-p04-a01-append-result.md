# AI-01-A03-P04-A01：Provider PATCH 原始版本结果前置

日期：2026-10-02；结果：`INTERNAL_APPEND_RESULT_PG_PASS / HTTP_CLOSED`。冻结 PATCH 返回 `200 config version + ETag`；原内部追加仅返回配置版本ID，历史收据内部状态为201。按 `DEC-20261002-634` 补稳定的内部结果，不提前开放 HTTP。

|编码前检查项|结论|
|---|---|
|当前 Phase/WBS|Phase 2；`AI-01-A03-P04-A01`|
|输入基线|冻结 API-01 If-Match/幂等/ETag，API-03 AI_PROVIDER_PATCH 200，DM-04不可变配置版本|
|前置任务|0054、内部追加/审计/收据、Provider当前读取与创建写模式已隔离验证|
|涉及模块/实体|AI Application/Repository；既有Provider及不可变配置版本，不改Schema|
|涉及 API|本项无公开路由，仅准备冻结PATCH响应|
|涉及权限|当前Session/CSRF/DeploymentAdmin/License/Secret有效性、状态/Kind/版本及同事务Audit/收据不放松|
|验收标准|首次/同Key原始版本号+ETag一致；后续配置/状态变化不漂移；旧UUID入口兼容；异载荷/失权/License/并发/回滚失败关闭；单元与隔离PG回归|
|风险|内部收据201不可直接透传为公开PATCH的HTTP状态；重放不得读取当前配置而伪造原始结果|

实现：保留 `append()` UUID 入口与收据 `201` 历史语义，新增 `append_result()` 返回配置版本ID、不可变版本号、原操作后 lock_version/强ETag。首次写入在同一事务内形成结果；重放从收据引用的不可变配置版本取版本号，并以已参与请求指纹的原 expected lock version 还原原始 ETag，绝不读取当前配置指针。当前 Session/CSRF/管理员、License、Secret用途、状态/Kind/版本及 Audit/收据仍原位校验。失效License显式分类为冻结403所需内部码，不回显原异常。

Win11隔离PostgreSQL18.6/Alembic head：首次v2/`"v1"`、同Key重放与旧UUID入口、异载荷冲突、普通用户/License拒绝、二次升版、审计失败原子回滚、双线程同Key单胜、后续状态与Secret变化后原结果不漂移 PASS；既有追加隔离PG回归 PASS。后端全量1927运行/3跳过、0失败；开发wheel SHA-256 `9abf4944875a474b659a7d99a72126da6c3376e1eacbee2391ae87d7975ca73f`。临时库删除，PG恢复原停机状态。

兼容/升级：无Schema/公开API/依赖变化；需既有0054。撤新入口可代码回滚，历史配置与收据不可物理删除。已知问题：公开PATCH仍未接线；正式账户信任、Provider Test/激活/模型路由/逐次外发、质量、Server2025/Debian、Gate/UAT/可用程序包未验，旧平台夹具待更新/重跑。下一项 `AI-01-A03-P04-A02` 可选冻结PATCH HTTP及隔离ASGI/PG验证。
