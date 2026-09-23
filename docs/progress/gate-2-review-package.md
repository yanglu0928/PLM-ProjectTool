# Gate 2 正式确认包

## 状态

`READY_FOR_USER_DECISION / GATE_2_PENDING / FORMAL_CODING_BLOCKED`

## 待确认的四份候选

|基线|候选标识|完成范围|当前状态|
|---|---|---|---|
|Architecture|`ARCH-CANDIDATE-V1`|22 模块、依赖、运行/部署视图、ADR-001～009|候选，未冻结|
|Data Model|`DATA-MODEL-CANDIDATE-V1`|22 Owner、65 Root、Scope、生命周期、关系、保留|候选，未冻结|
|Database Schema|`DB-SCHEMA-CANDIDATE-V1`|PostgreSQL 18/pgvector 物理组织、Root/Profile、约束/查询/Migration 边界|候选，未冻结|
|API Contract|`API-CONTRACT-CANDIDATE-V1`|323 Operation、150 错误、18 SSE、DTO/权限/兼容性|候选，未冻结|

## Gate 2 确认含义

批准 Gate 2 表示：

1. 上述四份候选成为正式开发基线。
2. 允许按 WBS 进入模块化单体的正式基础工程与业务实现。
3. 后续保持 Python 3.13/FastAPI/Vue 3/PostgreSQL 18/pgvector、本地文件系统、统一 AI/RAG、独立 Plugin 子进程和现有 License 机制。
4. 冻结后的 Breaking API、核心数据模型、技术栈、总体架构、安全/License 机制或 Scope 变化必须走 L3 Change Request。
5. 批准不代表实现、性能、AI 质量、三平台发行或 UAT 已通过。

## 保留风险与例外

- POC-03：Top-5 98% PASS，但分类 48%、引用 74% FAIL；继续阻塞 Gate 3/UAT，不能因 Gate 2 批准而关闭。
- SC-04 是验证性 Schema/Migration，不是生产 ORM/Migration；正式实现需逐模块生成并验证。
- Windows Server 2025 Office 实开、Debian 13 对应范围尚未验证，保留为 Release 约束。
- Ghostscript AGPL 发行前仍需公开完整对应源码、兼容许可证和第三方声明。
- Plugin 独立进程不是强恶意代码沙箱，只允许开发者签名包。
- SecretKeyProvider 平台实现、正式性能/容量、长期 Job/Outbox 故障恢复和完整备份恢复仍在后续 Gate 关闭。
- 本轮没有客户数据外发、数据库 Migration、正式业务代码或外部 AI 调用。

## Gate 2 验收摘要

- Architecture：8/8 AF-05 验收 PASS。
- Data Model：12/12 DM-06 验收 PASS。
- DB Schema：12/12 SC-05 验收 PASS。
- API Contract：14/14 API-05 验收 PASS；Contract Lint 5/5 PASS。
- 65 Root 在 Data Model、Schema、API 三层一致；22 Owner 唯一。
- 无未登记且需要改变架构/技术栈/Scope 才能解决的候选内部冲突。

## 用户决策

Gate 2 必须由用户明确批准，AI 不自动代批。批准后将：

1. 更新四份候选和 `STATUS.md` 为 Gate 2 已冻结。
2. 记录正式 Gate 2 决策与保留风险。
3. 创建 Gate 2 后首批正式开发 WBS，不一次性生成全库/全业务实现。

若不批准，项目保持设计候选状态，正式业务编码继续阻塞；可按用户指出的问题修订对应候选后重新提交 Gate 2。
