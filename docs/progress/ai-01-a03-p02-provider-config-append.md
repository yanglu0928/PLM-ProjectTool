# AI-01-A03-P02：内部 Provider 配置版本追加

日期：2026-10-02；结果：`INTERNAL_APPEND_PASS / PUBLIC_API_CLOSED`。本项遵循 Gate 2 冻结内容、CR-AI-001、CR-SEQ-001 和 P01；仅完成 AI-01-A03 的追加子任务，不关闭 Phase 2/Gate 3。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase/WBS|Phase 2 开放；前置独立任务 `AI-01-A03-P02`|
|输入基线|ADR-004、冻结 DM-04/SC-01/02/API-03、A01 形状、A02 迁移0054、P01 受权创建|
|前置任务|A01/A02/P01 已验证；当前 Auth Session/CSRF/DeploymentAdmin、License Guard、ACTIVE Secret 证明、收据与 Audit 可复用|
|涉及模块/实体|AI Application/Repository；`AIProvider` 根当前指针、锁版本、不可变配置版本；既有收据及 Audit|
|涉及 API|无公开 HTTP 变更；冻结 Provider PATCH 仍需独立路由/装配|
|涉及权限|当前管理员与 CSRF 在读/写事务重验；License 每次调用重验；首次写同事务锁定 ACTIVE `AI_PROVIDER_KEY` Secret；历史重放不等于使用许可|
|验收|CONFIGURED/SUSPENDED 可追加；ACTIVE/RETIRED 拒绝；强预期版本、Kind 不变、旧版不可变；同 Key 历史回放、异载荷冲突、不同 Key 并发单胜；Audit 故障完全回滚；后端回归和 wheel|
|风险|活动 Provider 直接切换配置会影响正在使用的调用；此路径明确禁止 ACTIVE；后续暂停/激活和逐次外发仍需独立证明|

## 结果与验证

新增内部 `AIProviderAppendService` 与 AI 自有 Repository。服务先核请求形状、当前管理员和 License，再在单一写事务中预留收据；历史同 Key 仅在当前管理员/License 均有效且收据版本确属目标 Provider 时返回已成功配置 ID，不检查历史 Secret 的现行状态，不产生新 Audit。首次写锁定根行，要求 CONFIGURED/SUSPENDED、预期 `lock_version`、原 Kind 一致及当前 Secret 可用，插入不可变配置版本，推进根当前指针/版本并写成功 Audit 与收据。同事务异常整体回滚。未解密 Secret、未连接厂商、未外发客户数据。

Windows 11 隔离 PostgreSQL 18.6 验证：真实 Session/CSRF/DeploymentAdmin、合成 License、真实 Secret 元数据、错误 Secret/Kind/版本/状态、审计故障回滚、配置历史与指针、同 Key 重放和异载荷冲突、不同 Key 并发单胜、ACTIVE/RETIRED 拒绝、停用 Secret 后历史身份返回、License/账户失效拒绝均 PASS。定向单元2项；后端全量1911运行/3跳过、0失败；开发 wheel SHA-256 `f256f544c5a32759b0c9d7352391682a3c190abe2f096e09637f24cf11fd19f4`。隔离测试数据库已删除，PG 实例恢复原停机状态。

兼容/升级：无新 Schema、公开 API 或依赖；先应用已验证迁移0054。撤除服务调用可回退代码，但已提交的配置历史不得物理删除；更正应追加新受权版本。正式生产迁移、信任材料/主密钥、Provider Test/Activate、ModelRouter、逐次外发、POC-03 质量、Server 2025/Debian、UAT/Gate/发行仍未验证。下一项 `AI-01-A04` 的 Provider 安全元数据读取/列表需另做权限与 Secret 不回显设计。
