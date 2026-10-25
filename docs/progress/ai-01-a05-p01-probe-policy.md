# AI-01-A05-P01 受控端点策略与固定探针合同

日期：2026-10-02；状态：离线合同 PASS；来源：冻结 API-03/DM-04、CR-AI-002；决策：DEC-20261002-639。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase|Phase 2 Platform Core，Gate 2 已批准|
|当前WBS|AI-01-A05-P01|
|输入基线|固定无客户/无业务 Prompt 探针、符号化 EndpointPolicyRef、首批 DeepSeek；不改变冻结 202 JobRef|
|前置任务|A05 前置核查及 CR-AI-002 已登记并推送；ProviderConfiguration 合同已存在|
|涉及模块|AI domain/application 内部策略解析|
|涉及实体|无持久实体/Schema 改动|
|涉及API|无公开 API 或路由开放|
|涉及权限|本项不授权外发；后续提交仍需管理员、Session/CSRF、License/Job/Secret 重验|
|验收标准|可信 registry 精确解析；未知引用、Kind/区域/外发类别/能力错配、非 HTTPS 与含凭据/查询/片段 URL 均失败关闭；固定探针不接收客户内容；定向/全量测试与 wheel|
|风险|离线合同无法证明 DNS/IP 出站安全、实际 DeepSeek 连通、Secret 生命周期或 Job/Worker；后续 P02～P05 逐项验证|

## 执行结果

- Changed/Files：新增 AI application 的不可变 `EndpointProbePolicy`、精确引用 registry 与固定 `ProviderProbePlan`，另有 6 项单元测试。不把配置中的引用当 URL，不接收客户端正文或业务 Prompt；目前仅支持 OpenAI-compatible CHAT 的离线计划，其他能力/Adapter 失败关闭。
- Migration/API：无新 Migration、公开 API、依赖或运行时组合变化；无外部网络调用、Secret 读取或真实厂商请求。
- Tests：定向 6/6；Windows 11 后端全量 1938 运行、3 跳过、无失败；开发 wheel 构建通过，SHA-256 `190589d1cea1b168e20c9ce9ea666f26029d88a0c1c9f5f3513598a1fcfc0fa3`。
- 兼容/升级/回滚：不需要数据升级；撤内部纯合同可回滚，不改变既有 Provider 配置及历史。
- Known Issues：registry 尚未接正式受控部署来源；URL 形状检查不等于 DNS/IP 出站防护；Job/TestRun/Worker/SecretResolver 接线与真实连接、质量、目标三平台、Gate/UAT/可用包未完成。下一项 P02 持久测试证明设计与 Schema 增量。
