# PLAN-02-A04-P04-A04-P03-P04：PlanVersion 草稿写入前置核查

日期：2026-10-26。结果：`PRECHECK_ADJUSTED / SCHEMA_GAP`；未开放写口。

## 编码前检查

|项目|结论|
|---|---|
|Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P03-P04`；原计划实现PlanVersion完整DRAFT写Owner。核查后先调整为补齐冻结完整快照所需物理Schema，不接业务写入。|
|输入基线|Gate 2冻结DM-05/API-04、SC-01～SC-03；Migration 0170～0177；DEC-20261019-1231～1235；CR-PLAN-001；P03内部来源证明Owner。|
|前置任务|Plan/PlanVersion/WBS身份、依赖、里程碑和当前Solution来源证明已存在；现有业务版本写Owner、Migration ORM模型尚不覆盖完整 `PlanVersionInput`。|
|涉及模块/实体|Plan ORM/Migration；PlanVersion、WbsItem、Member、Requirement/Solution/Evidence固定引用、Milestone。OutputArtifact 未有持久化Owner/目标表。|
|涉及API|无本片HTTP变更；后续仍须消费冻结 `POST /api/v1/projects/{project_id}/plans/{plan_id}/versions`，不能丢弃未知/已有合法字段。|
|涉及权限|本片不写业务数据/不新增授权；后续Owner必须项目事务授权且责任人引用固定到同项目ProjectMember。|
|验收标准|本片完成正式CR/字段映射后逐字段扩展Schema；提供ORM、migration up/down、防历史破坏和实际PG空/有数据升级验证。当前具体映射未完全设计，故本次编码前检查禁止直接写Migration。|
|风险|静默丢弃字段、弱JSON/裸UUID引用、历史快照不可降级、未完成Output目标Owner却伪造交付链接。|

## 代码事实与处理

- 当前 WBS 表已能保留层级身份和 Requirement/Solution/Evidence 引用，但不含任务分类、责任人、角色、日期/工期、进入/验收条件、风险/排除等DM-05字段；PlanVersion root也缺日历/版本排除快照。
- `OutputArtifact` 目前无目标ORM/Migration/Owner；按原冻结合同的可证明引用要求，非空 output ref 暂不能合法持久化。
- 已先登记 `CR-PLAN-002`，选择增量强类型/owned child Schema，不采用不完整快照或整体JSON塞入方案。实现前每个子片必须另完成精确字段/枚举/FK映射，迁移追加在0185后，不改写Gate 2原冻结提交。
- 本记录仅为代码/合同核查，无功能测试；无Schema/API/业务数据更改。后续继续在本CR内按明确字段片完成，而不是等待用户普通确认。

下一片：`PLAN-02-A04-P04-A04-P03-P04-S01`，先依据冻结ProjectMember枚举及Plan/WBS数据模型完成精确字段到表/FK映射，再实现第一组Schema增量和真实PG迁移验证；完成前不可开放PlanVersion CREATE。
