# Gate 2 冻结记录

## 状态

`APPROVED / FOUR_BASELINES_FROZEN / FORMAL_DEVELOPMENT_AUTHORIZED`

|字段|值|
|---|---|
|Gate|Gate 2|
|批准日期|2026-09-23|
|批准主体|用户明确批准|
|批准原文|“批准 Gate 2，冻结 Architecture、Data Model、DB Schema V1 和 API Contract V1”|
|冻结内容提交|`64cdf09`|
|冻结记录决策|`DEC-20260923-059`|
|后续阶段|Phase 1：架构冻结与基础工程|
|下一 WBS|`1.01 定义模块目录规范`|

## 冻结基线

|正式基线|保留的候选标识|规范入口|冻结结论|
|---|---|---|---|
|Architecture V1|`ARCH-CANDIDATE-V1`|`docs/architecture/architecture-freeze-candidate-v1.md`|22 个客户运行模块、Developer Workbench、依赖方向、运行/部署视图和 ADR-001～009 冻结|
|Data Model V1|`DATA-MODEL-CANDIDATE-V1`|`docs/data-model/data-model-candidate-v1.md`|22 Owner、65 Root、Scope、关系、生命周期、正式化、保留和 25 条不变量冻结|
|DB Schema V1|`DB-SCHEMA-CANDIDATE-V1`|`docs/database-schema/database-schema-v1-candidate.md`|PostgreSQL 18/pgvector 物理组织、Profile、约束、索引、20 个 Query 与 Migration 边界冻结|
|API Contract V1|`API-CONTRACT-CANDIDATE-V1`|`docs/api-contract/api-contract-v1-candidate.md`|`/api/v1` 的 323 Operation、363 Method/Path、150 错误、18 SSE、DTO、权限和兼容性边界冻结|

候选标识是历史可追溯对象名，本次冻结不通过重命名制造第二份规范。批准时的规范正文以 Git 提交 `64cdf09` 为内容身份；本记录及状态回写只改变批准状态，不改写该提交中的技术结论。API-01～API-04 明细及 API-05 机器 manifest 继续是 API Contract 的受控组成部分。

## 批准效果

1. Gate 2 对正式开发的阻塞解除，可按批准的 WBS 开始模块化单体基础工程和业务实现。
2. 实现必须遵守冻结架构、数据模型、Schema 和 `/api/v1` Contract；实际 OpenAPI 必须与 API-05 manifest 做差异检查。
3. DB Schema V1 的冻结是设计冻结，不表示生产 ORM/Alembic 已生成；SC-04 仍是验证性 Migration，不得直接作为生产全库 Schema。
4. 冻结后的总体架构、核心数据模型、DB Schema V1、Breaking API、技术栈、安全/License 机制或 Scope 变化必须提交 L3 Change Request。普通缺陷修复和向后兼容扩展仍按 WBS 执行，但不得静默改变基线语义。
5. 正式成果继续保留历史版本和 TraceLink；AI 建议经人工确认后才能成为正式业务事实。

## 保留风险与未通过项

- POC-03 的 Top-5 为 98%，但分类 48%、引用 74% 仍 FAIL；继续阻塞 Gate 3/UAT。
- Windows Server 2025 Office 实开和 Debian 13 对应范围未验证，继续作为 Release 约束；不得从 Windows 11 结果外推已通过。
- Ghostscript AGPL 发行合规尚未完成，发布前仍须满足完整对应源码、许可证和第三方声明要求。
- Plugin 独立进程不等于强恶意代码沙箱；仅允许开发者签名包。
- 正式性能/容量、长期 Job/Outbox 故障恢复、完整备份恢复、SecretKeyProvider 平台实现和生产 Schema/OpenAPI 仍需后续 WBS/Gate 验证。
- 新的客户数据或最小候选正文外发仍需逐次明确授权；历史 PoC 授权不得复用。

## Gate 2 验收证据

- Architecture：AF-05 8/8 PASS。
- Data Model：DM-06 12/12 PASS。
- DB Schema：SC-05 12/12 PASS；SC-04 Windows 11 验证通过但保持验证性边界。
- API Contract：API-05 14/14 PASS；Contract Lint 5/5 PASS。
- 跨层一致性：22/22 Owner、65/65 Root、323/323 Operation ID、363/363 Method/Path、150/150 错误、18/18 SSE、20/20 Query 映射一致。
- 本次冻结实际外部调用 0，未创建或执行生产数据库 Migration，也未宣称性能、发行或 UAT 通过。
