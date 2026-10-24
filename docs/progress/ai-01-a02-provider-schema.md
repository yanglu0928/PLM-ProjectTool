# AI-01-A02：Provider 配置版本持久化

日期：2026-10-02；结果：`SCHEMA_PASS / SERVICE_NOT_IMPLEMENTED`；依据 CR-AI-001/CR-SEQ-001。Phase 2 与 Gate 3 仍开放。

## 编码前检查

|项目|核查|
|---|---|
|Phase/WBS|Phase 2 开放；前置独立 AI-01-A02|
|输入基线|Gate 2 原冻结 `64cdf09`；ADR-004、DM-04 AIProvider、SC-01/02 AI-01、API-03；AI-01-A01 内存合同与现有 SecretRecord|
|前置|CR-SEQ-001 已记录时序解环；CR-AI-001 在编码前已单独登记并推送；本机 PG18 测试集群可恢复|
|模块/实体|仅 AIProvider 根身份与不可变 ProviderConfigVersion，迁移注册 AI ORM；Secret 表仅读 FK，不改其所有权|
|API/权限|无公开 API、角色/Session/License/外发权限变化；后续 Provider Service 仍需 DeploymentAdmin、License、Secret 目的/消费者和 Audit|
|验收|ORM/Alembic 零差异；空库 up/down/re-up；有数据升级不改变旧行；复合 FK、版本/字段/历史保护；非空降级拒绝；全量测试与 wheel|
|风险|误认为 FK 等同用途与外发授权，或降级丢失配置历史；失败关闭及后续 Service 重验|

## 结果与边界

新增 `20261002_0054` 两表及不可变版本触发器。Windows 11 本机隔离 PostgreSQL 18.6 实测上述空/有数据路径、旧用户行不变、配置追加和切换不覆盖历史、跨 Provider 指针/无效 Secret/原始 URL/空能力拒绝；`alembic check` 两库均无新操作。全量后端 `1907` 运行、`3` 跳过、`0` 失败；开发 wheel SHA-256 `856a4007c223058ed5035861d3bf45d69b2b364fa8c20ddcf3e8ece53384bc16`。首次测试前旧 PG 实例停机，改用后台非等待启动后复验通过；首轮全量的两个固定 head/表清单断言更新后重测全通过。测试临时数据库在脚本 finally 清理，目录无同前缀数据库；测试后正常停机并确认 PG 不再运行，恢复原状态。未运行生产迁移；未外发客户资料。

尚无 Provider 创建/轮换/激活 Service、Secret purpose 运行证明、公开 API、外部连通、模型路由、Golden 质量或三平台验证；这些不算本项 PASS。下一项 `AI-01-A03` 实施内部受权 Provider 创建/配置版本追加，需同事务 License/DeploymentAdmin/Secret 用途/Audit/幂等与并发验证，先做其编码前检查。
