# REQ-01-A04-A04：RequirementVersion 支持引用与提交完整性

日期：2026-10-07。结论：`REQ_01_A04_A04_VERSION_SUPPORT_PASS`。`REQ-01-A04` Schema完成；
下一项：`REQ-01-A05` 固定来源证明 adapters。

## 实现与边界

- Migration0118及ORM新增`req_source_evidence_refs`、`req_assessment_evidence_refs`、
  `req_version_ai_task_refs`，分别固定Source的PROJECT Evidence、CapabilityAssessment的STANDARD/PROJECT
  双侧Evidence和Version的AI provenance；没有JSON、UUID数组、动态latest或Secret。
- 延迟constraint trigger在事务提交时核对Version声明的Source/Acceptance/Capability/Assumption/Exclusion/
  Dependency/AI Task计数，七类ordinal必须从0连续；每个CapabilityAssessment必须同时有GLOBAL/ELIGIBLE
  STANDARD与同Project/ELIGIBLE PROJECT Evidence。
- PROJECT_EVIDENCE Source必须存在与`source_object_id`完全相同的PROJECT Evidence引用。AI Task必须为
  同Project的REQUIREMENT_NORMALIZE/MATCH、SUCCEEDED、ACCEPTED_TO_DRAFT，且accepted domain固定为当前
  RequirementVersion；AI只保留Draft provenance，不因存在引用成为正式事实。
- 0118升级允许既有User/Project/Requirement身份数据；由于0116～0117业务Owner从未开放，若发现预先
  存在Version行则拒绝自动升级，要求审计后专门迁移，避免把管理员绕过数据自动背书为完整Version。
- 三类support表写和截断继续关闭；A06创建Owner前不能从产品入口写Version或owned/support集合。

## 验证

- Windows 11 / PostgreSQL 18.6：0117既有Requirement身份安全升级、未审计Version拒升且事务DDL回滚、
  清理不受支持fixture后重升、两次drift、完整快照提交，以及计数不符、ordinal断档、能力缺双证据、
  Evidence角色与Scope错配、PROJECT Evidence缺同一映射、AI未接受到当前Draft六类提交拒绝均通过。
- support Owner直接DELETE、TRUNCATE和有支持历史降级拒绝通过；临时库清理。A02/A03历史验证器为适配
  新的最终提交闭包，仅以管理员身份在各自物理约束验证窗口停用新增completeness trigger并恢复，两个
  标记均在当前head复验通过，不削弱产品Owner。
- 定向18项、后端全量2983项通过，3项既有环境跳过；开发wheel共1127项，SHA-256
  `2d8771dc8aba4d72e18d97a6973f1801fb4210622f5503e91dfc8b2398650d5f`，不是正式发行包。

无公开API、前端、依赖、Secret、客户数据或外发变化；A05～A12、Gate3/UAT/发行仍待完成。
