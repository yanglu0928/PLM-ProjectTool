# AI-01 Provider 配置版本物理增量

版本：`20261002_0054`；日期：2026-10-02；来源：冻结 SC-01/02 AI-01、DM-04 与 CR-AI-001。原冻结提交 `64cdf09` 不变。

|表|身份/字段|约束与用途|
|---|---|---|
|`plm.ai_providers`|`ai_provider_id`、`current_config_version_ref`、`provider_state`、`lock_version`、`created_by/at`|部署级根身份；状态只允许 CONFIGURED/ACTIVE/SUSPENDED/RETIRED；复合 FK 锁定当前版本属于本 Provider；当前指针必填；本表不承诺已完成激活证明|
|`plm.ai_provider_config_versions`|`provider_config_version_id`、`ai_provider_id`、`config_version_no`、`provider_kind`、`display_name`、`endpoint_policy_ref`、`secret_ref`、`data_region`、`egress_class`、四个能力布尔位、`created_by/at/xid`|同 Provider 版本号唯一、版本身份/归属唯一；FK 指向 Provider、SecretRecord 与创建用户；类型/引用/地区/能力基础检查；UPDATE/DELETE/TRUNCATE 拒绝；不存 URL、Key 或客户正文|

配置根的当前指针与配置行互指，FK 均延迟到事务提交检查，创建必须在同一事务写入二者；跨 Provider 指针不能提交。`secret_ref` 的 FK 只证明 SecretRecord 身份存在，不证明用途、ACTIVE、消费者权限或密钥可读；AI Application 在使用前必须经 SecretResolver/许可/外发授权重验。能力声明也不是模型质量证明。

升级：从 `0053` 增量建两张空表，不回填旧业务。回滚：两表均空时可降至 `0053`；存在 Provider/版本历史时迁移拒绝降级，先备份并采用向前修复或另行批准的恢复流程。生产库未执行此迁移。
