# AI-01-A01：Provider 内部配置合同

日期：2026-10-02；按 CR-SEQ-001 前置独立 AI 基础任务。Phase 2 及 Gate 3 仍开放。

## 编码前检查

|项|核查结论|
|---|---|
|当前 Phase/WBS|Phase 2 未关闭；`AI-01-A01` 为批准的依赖前置 WBS|
|输入基线|冻结 ADR-004、DM-04 AI-01、API-03 Provider Contract、应用合同 AIService、SC-01 AI-01；技术栈未变|
|前置任务|Gate 2 冻结、CR-SEQ-001 和 PLT-CORE-DEPENDENCY-A01 已完成；SecretResolver/Job/License 现有边界可供后续 Application 使用|
|涉及模块/实体|仅新增 `ai.domain.ProviderConfiguration`；不改 Platform；Provider 配置快照，不是状态实体或正式激活|
|API/权限|无公开 API、无会话/角色变更；不得由配置形状推定 DeploymentAdmin、许可或外发授权通过|
|验收|四种冻结 ProviderKind、四种能力标记、版本/UUID/显示名/端点策略引用/地区/外发类别校验、不可变和安全错误；完整后端回归与开发 wheel|
|风险|把原始 URL/API Key 混入配置，或把合法形状误报为连通/ACTIVE/客户资料可发送；以不含网络和 Secret 明文的纯 Domain 约束并明确后续证明边界|

## 实施与结果

新增不可变 `ProviderConfiguration`，仅存部署 Provider 身份、配置版本、受控 `endpoint_policy_ref`、不含明文的 Secret 引用 UUID、地区、外发类别及能力集合。原始 URL、空/畸形字段和未定义能力失败关闭；错误不回显输入。Domain 不依赖 Platform Application，后续 Application 必须将 UUID 转为 `SecretRef`，检查用途/消费者、License/Session、真实连通与每次外发授权。该类型不含状态变迁，不能让 Provider 激活，也不实施厂商/客户数据调用。

测试：定向 5/5；Windows 11 本机后端全量 1907 运行、3 跳过、0 失败；开发 wheel SHA-256 `4383e7e4609a7f52afc1792a5e74ed2999fb75dc51c477f9749e53dc92e28825`。无 Migration、API、网络外发或新依赖。API/权限/PG 集成、Provider Test/Activate、质量 Golden Regression、正式三平台均未在本 WBS 执行，不误标通过。

下一项 `AI-01-A02`：冻结物理 Schema 与现有 Secret/Audit 关系前置核查，设计 Provider 配置版本持久化及空/有数据升降级；不得把本项纯形状当成可用 AIService。
