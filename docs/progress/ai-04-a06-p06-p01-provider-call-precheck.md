# AI-04-A06-P06-P01 Provider 调用边界编码前核查

日期：2026-10-03；状态：`PRECHECK_PASS`；当前 Phase 2 Platform Core。

| 项目 | 结论 |
|---|---|
|输入基线|冻结 ADR-004/DM-04/API-03，Schema0073，CR-AI-015/016，P05-P04 PASS|
|前置任务|Job Claim/Grant、不可变 Content Plan、确定性 Envelope/Proof、PENDING Invocation 均已在 Win11/PG18.6 验证|
|涉及模块|ai、jobs、platform Secret、license；后续才涉及网络 infrastructure|
|涉及实体|AITask、AIInvocation、Job/Lease/Attempt、EgressAuthorization、ProviderConfig/Model、SecretVersion|
|涉及API|本项无公开API变更；后续部署策略是非秘密Bootstrap增量|
|涉及权限|仅已批准Task的AI_PROVIDER_ADAPTER瞬时Secret读取；不授予管理权限|
|验收标准|明确可复用/不可复用边界，建立CR、切片、迁移/回滚/验证计划，不发送数据|
|风险|将探针当业务Adapter、Begin后无发送前实时复核、任意URL/Secret、超时未知结果|

核查证实：Provider Probe 的固定请求/专用 Claim/结果不能执行业务 Envelope；`SecretResolver` 的消费者绑定、期望版本、审计和清零可复用；探针运输的安全 DNS/TLS/有界读取需抽取后复用，不能放宽固定探针接口。Grant Issuer 刻意只允许 QUEUED Task，Begin后需独立 post-Begin pre-send Owner 以 PENDING Invocation 为根重验当前事实。依持续授权登记 CR-AI-017，选择独立业务 execution policy/ModelRouter/ProviderAdapter。

Changed/Files：新增 CR-AI-017、DEC-745、本进度、状态与版本记录。Migration/API/Dependencies：无。Tests：静态交叉核对 Probe Worker/Transport/Policy、Grant Repository、SecretResolver、冻结 AIService 合同；未运行本项新代码测试，不标 Adapter PASS。Compatibility/Rollback：无行为变化；后续保留Probe边界并只显式装配业务Worker。Known Issues：Provider路由/pre-send Owner/Adapter/Windows装配、响应Schema与终态尚未实现；真实Provider数据外发未授权。Next：`AI-04-A06-P06-P02` 实现无正文 execution route/send proof/Adapter observation 合同。
