# CR-SOL-005：ReferenceSolution 来源资格与 GLOBAL 脱敏确认分层

日期：2026-10-08；状态：依据 CR-EXEC-001 持续授权先记录后实施；原冻结提交 `64cdf09` 保留。TraceLink：CR-SOL-004/Schema0139 → SOL-01-A04-P01 → 本 CR。

## 冲突和证据

冻结 DM-05 要求 GLOBAL/PROJECT 参考方案、来源适用性及脱敏分类；API-04 只授 DeploymentAdmin 写 GLOBAL。现有 `DocumentFixedSourceProofService` 可核真实字节，但 GLOBAL 专用的 `GlobalStandardReferenceProofService` 强制文档类型 `STANDARD_CAPABILITY` 且要求目标项目 PM，用于标准能力引用而非一般参考方案。Evidence 固定来源服务也分别面向 PROJECT 或 GLOBAL 标准能力。若直接复用 GLOBAL 标准服务，会错误拒绝合法 `REFERENCE_MATERIAL`；若仅凭 0139 单列 FK 或客户端自称“已脱敏”，会错误准入跨项目/未脱敏来源。

## 方案与选择

- 不选放宽现有 GLOBAL 标准能力服务的类别与角色：可能扩大原消费者权限边界。
- 不选只依据 `deidentification_class` 自填字符串：不构成已核实的人工脱敏事实。
- 选择在 Solution Application 层增加 Reference 专用来源资格合同：每个固定 DocumentVersion 和 Evidence 必须由上游受权 Port 在同一事务证明 Scope/Project、内容摘要与当前性；GLOBAL 另要求独立的 DeploymentAdmin 人工脱敏确认 Proof，并与本次固定输入指纹绑定。先实现判定合同和失败关闭测试，Port 适配、人工确认记录与原子写 Owner 后续单任务完成；当前 0139 DML/公开 API 继续关闭。

## 影响、迁移、回滚与验证

本项不增删产品 Scope，不修改旧服务、Schema、迁移或 `/api/v1`，也不外发正文。增加内部 Application Port/DTO 与纯判定规则，不把 AI 结果当人工确认。回滚删除新模块/测试即可；0139 表仍封闭。必须测 GLOBAL/PROJECT 各自完整通过、项目/Scope/来源不匹配、重复、缺文档/证据、摘要不一致、GLOBAL 缺/过期/错误绑定的人工确认，以及 Port 错误失败关闭。只有合同 PASS，不能声称真实 Owner/PG/HTTP/Review/Gate 通过；剩余风险是上游适配、确认凭证的持久化与管理员资格实际证明。
