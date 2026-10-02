# AI-01-A05 Provider 连通性测试前置核查

日期：2026-10-02；状态：前置核查完成，整体 A05 未完成；来源：冻结 API-03、DM-04、Schema 0054、当前 AI/Job/Secret 代码；变更：CR-AI-002。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase|Phase 2 Platform Core；Gate 2 已批准，Gate 3 未通过|
|当前WBS|AI-01-A05 前置核查；下一独立任务 P01|
|输入基线|冻结 API-03 的 `202 JobRef`、固定无客户探针；DM-04 Provider/Job 不变量；CR-SEQ-001 与 AI Schema 0054|
|前置任务|Provider 创建/PATCH/读取已在 Win11 隔离 PG/ASGI 验证；Job/Outbox 与 SecretResolver 基础存在|
|涉及模块|AI Provider、Job Owner/Worker、Platform Secret/License、Windows 组合|
|涉及实体|AIProviderConfigVersion、拟议 ProviderTestRun、Job/Outbox；此核查不改 Schema|
|涉及API|冻结 `POST .../{provider_id}:test`，本核查不开放路由|
|涉及权限|DeploymentAdmin、Session/CSRF、License、固定探针和受控外发；不得借测试发送客户资料|
|验收标准|逐项核对当前能力与冻结合同，记录不可直接实现之处、变更/回滚/验证和拆分顺序|
|风险|尚无端点策略解析、专用结果证明/Job Owner/Adapter；正式信任源和外发未授权|

## 证据与下一顺序

核查结果：当前 `ProviderConfiguration` 仅验证 `endpoint_policy_ref` 形状；Provider 模块只有配置和安全元数据读写，无 Test/Adapter；Job ORM 支持 DEPLOYMENT scope，但 Job Owner registry/结果类型只覆盖既有两类；SecretResolver 提供失败关闭的 `AI_PROVIDER_ADAPTER` 使用边界。故不得直接开放 Test HTTP 或声称 DeepSeek 连通。完整差异和方案见 CR-AI-002。

1. `AI-01-A05-P01`：受控端点策略与固定探针合同，离线验证未知引用、URL 注入、能力/地区/外发类别错配均失败关闭；不发送网络。
2. `P02`：不可变 TestRun 结果/配置版本绑定 Schema、ORM/Migration、空/有数据 up/down 与审计。
3. `P03`：部署管理员 Test 命令，同事务 Job/Outbox/幂等/审计；可选 202 HTTP 在隔离 PG 验证，不挂生产组合。
4. `P04`：受限 Worker/Adapter 本机合成探针、SecretResolver/License/策略重验、fencing 和安全结果；实际外部发送另行逐次授权。
5. `P05`：Job Owner 只读投影、Windows 显式装配与隔离链路；激活另以当前配置成功证明独立实现/验收。

Changed：设计/追溯文档；Migration/API/程序：无。Tests：静态核查现有合同、ORM、Provider/Job/Secret 实现；未执行新运行时测试。Result：A05 前置核查 PASS，A05 功能未完成。Known Issues：真实厂商/正式信任源、质量、目标三平台、Gate/UAT/发行均待验证。
