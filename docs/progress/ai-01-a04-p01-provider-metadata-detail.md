# AI-01-A04-P01：Provider 内部安全元数据详情

日期：2026-10-02；结果：`INTERNAL_DETAIL_PASS / LIST_AND_HTTP_OPEN`。依据 Gate 2 冻结 API-03/DM-04、CR-AI-001、CR-SEQ-001 与 AI-01-A03 的 Provider 根/配置链，先验收详情受权投影；Phase 2 和 Gate 3 保持开放。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase/WBS|Phase 2 开放；`AI-01-A04-P01` 内部详情|
|输入基线|ADR-004、冻结 DM-04/SC-01/02/API-03、迁移0054、A03 创建/版本追加|
|前置任务|现有当前 DeploymentAdmin Session 只读证明与 License Guard 可复用；A03 已在隔离PG验证|
|涉及模块/实体|AI Application 与 AI Repository；Provider 根及当前不可变配置版本|
|涉及 API|无公开 HTTP；冻结 GET/LIST 留给后续任务|
|涉及权限|先证明当前 DeploymentAdmin，再校验 License，读取事务内再次证明当前 DeploymentAdmin；无 CSRF 写操作|
|验收|只选安全列、不 JOIN Secret 密文表；返回当前配置/状态/强资源 ETag、仅 SecretRef 遮罩；普通用户/失效 License/撤权/未知ID拒绝|
|风险|完整 SecretRef 或密文从 ORM/日志泄露；使用显式列投影和最小 DTO，列表游标签名/密钥另行验收|

## 结果与验证

`AIProviderMetadataService` 提供内部详情查询；Repository 仅 SELECT Provider 根和当前配置的明确安全列，不访问 SecretRecord/Version 密文，也不把完整 SecretRef 放入返回 DTO。返回 `****` 加 UUID 末 8 位的脱敏标识，以及 `"v{lock_version}"` 强资源版本；它只是读取身份，不代表 Provider 已激活或可用。License 失败映射为拒绝，未知 ID 不暴露其他信息。

Windows 11 隔离 PostgreSQL18.6：真实管理员 Session、普通角色拒绝、合成 License 失效拒绝、未知 ID、v1→v2 配置追加后的当前视图与 ETag 更新、完整 SecretRef 不回显、账户停用拒绝 PASS。定向单元2；后端全量1913运行/3跳过、0失败；开发 wheel SHA-256 `b454256aa7ebfaf37433d24d3ea5ecbe9cb1f55dc171cb8e38d1fb2c5f628ee6`。测试库已删除，PG 恢复原停机状态。无真实 Provider 调用或客户数据外发。

兼容/升级：无 Schema、依赖或公开 API 变化，需既有0054；不装配内部读取即可代码回退。未完成：安全列表游标/正式密钥、GET/LIST HTTP、正式 License/Secret 信任源、激活/模型路由/逐次外发、质量、三平台、Gate/UAT/可用包。下一项 `AI-01-A04-P02` 内部有界 keyset 列表与安全游标设计/验证。
