# CR-EXEC-049：PLG-03-A03 Plugin 应用层派发编码前检查

- 日期：2026-11-07
- Phase/WBS：Phase 2 Platform Core / PLG-03-A03
- 状态：PASS_WITH_LIMITATION（只读边界检查完成；未实现或开放派发）
- 分支：feature/p51-a33-launcher-checksum-recovery；PR #61
- 基线：ADR-005；CR-EXEC-046 Process Host；CR-EXEC-048 Windows 启动 containment；CR-PLG-014 PluginExecution persistence；CR-EXEC-041/045/046 Output admission 与固定来源。
- 类型：编码前安全/依赖检查；不改变冻结架构或外部接口。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLG-03-A03 Plugin 应用层派发边界检查
输入基线：ADR-005、CR-EXEC-046、CR-EXEC-048、CR-PLG-014、OutputJobExecutionAdmissionOwner、PluginOperationCapabilityReader
前置任务：PLG-03-A01/A02 均 PASS_SCOPE_LIMITED；正式 Publisher trust 为空；PluginExecution schema 已通过独立 PG18 验收但 owner-write guard 保持关闭。
涉及模块：Plugin application/infrastructure；Output application admission；Jobs lease；PluginInstallation materializer。
涉及实体：只读检查 PluginExecution、Output Job/Context、PluginInstallation、Package/Manifest operation、RuntimeValidation。
涉及API：无。
涉及权限：不调整；Production Output/Worker 必须继续要求授权 capability 且 fail closed。
验收标准：确认 Admission→安装身份/入口→最小上下文→ProcessHost→Execution lifecycle 的现有边界与缺口；明确唯一安全后续任务及测试边界；不得改 API/Schema/Migration 或生产挂载。
风险：若绕过 Application Owner 或把可伪造路径直接交给 Host，可能形成执行授权旁路；现阶段没有可供正式执行的信任签名来源。
```

## 只读核查结论

1. `OutputJobExecutionAdmissionOwner` 只返回最小输出请求引用和指纹，检查当前输出请求及 Plugin capability；它不持有上下文正文、不返回 Installation/Package/Manifest 身份，也不调用 Plugin。
2. `PluginOperationCapabilityReader` 与 SQL repository 只暴露 operation/output types/enabled/trusted；内部要求唯一 operation、唯一 ENABLED installation、启用 operation、最新兼容 runtime snapshot 和 ACTIVE trusted signer。
3. `PluginProcessHost` 是传输层，要求调用方提供 executable、package root、entry point、work root、Plugin 标识/API 版本与 JSON-RPC params；自身不检查签名、启用状态或数据库授权。
4. `PluginExecutionRow`、结果文件与状态事件 schema 已存在，包含 PENDING/RUNNING/终态、Job/Project/Context/Installation/Package 关系与幂等键；Migration 的写入触发器仅允许显式 `plm.plugin_execution_owner_write=on`，但当前没有负责这项 GUC 和行锁/事件一致性的生命周期 Owner。
5. `LocalPluginInstallationMaterializer` 可在验证精确签名归档后写入数据文件并复验 UUID 目录，但 `PluginInstallationOwner` 仍明确不物化/启用/执行；默认 composition 没有可信 target path/entrypoint Owner。
6. 包内 Publisher keyring 当前为空。不得用合成签名/测试 signer 伪装成正式信任，也不得把 Process Host 接入 Production Output/Worker。

## 决策与下一步

PLG-03-A03 只读前置检查以 PASS_WITH_LIMITATION 关闭，不产生产品代码。直接构造 Host 参数会缺少可信的 Installation/Package 绑定、最小 Context 来源和 Execution 持久化/审计，故不采用“只接 ProcessHost”的快速路径。

下一 WBS：PLG-03-A04，先完成编码前检查并实现 PluginExecution 的内部 Admission/状态 Owner（复用现有 Schema，显式开启 owner GUC、以当前 Job fencing/lease 事实约束状态迁移、同事务写状态事件；不运行子进程、不挂生产 Worker）。优先检查是否可由现有 Jobs lease port 与 Output admission port在同一事务完成；若不能，先登记最小可验证的事务边界调整。验收使用 Hosted Windows runner D 盘合成 PostgreSQL 18 数据，覆盖幂等、Project/Job/Attempt绑定、失效/过期 lease拒绝、状态事件原子性、审计失败回滚、Owner关闭及append-only。生产签名信任未建立期间继续 fail closed。

## 差异、回滚与验证计划

- 本次仅新增审查记录并推进 STATUS/CHANGELOG；无产品代码、API、Schema、Migration 或权限变化。
- 本 CR 可通过追加反向证据修订，不需回滚代码。
- Hosted 验证将用于下一项 A04；本次为静态只读检查，没有运行项目代码。
- Secret 检查覆盖拟提交 CR、STATUS、CHANGELOG 完整文本，提交前须 0 命中。
