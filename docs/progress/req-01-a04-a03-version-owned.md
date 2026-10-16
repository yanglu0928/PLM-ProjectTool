# REQ-01-A04-A03：RequirementVersion 六类 owned 语义表

日期：2026-10-07。结论：`REQ_01_A04_A03_VERSION_OWNED_PASS`。下一项：
`REQ-01-A04-A04` Evidence/AI 支持引用与提交完整性。

## 实现与边界

- Migration0117及ORM新增冻结命名的`req_sources`、`req_acceptance_criteria`、
  `req_capability_assessments`、`req_assumptions`、`req_exclusions`、`req_dependencies`。每行携带
  Version/Requirement/Project三列归属，按Version内非负ordinal唯一有序，不使用JSON或UUID数组承载
  核心业务语义，也不级联删除。
- Source仅允许APPROVED_SURVEY_CONCLUSION、CONFIRMED_HANDOVER、HUMAN_DECISION、PROJECT_EVIDENCE；
  Handover必须同时固定version ref，其余类型不得塞入无意义version。来源对象的资格与当前状态由A05
  专用证明adapter重验，本项不把类型标签当成Approved/Confirmed事实。
- AcceptanceCriterion强制可观察结果、验证方式、必要数据、必要环境和Evidence要求五项均为trim后
  1～4000字符，不能只保存模糊标题或空白。
- CapabilityAssessment以`baseline_version_id + capability_item_id`复合FK精确固定GLOBAL能力项，固定
  DIRECT/PARTIAL/NONE/UNKNOWN、fit gap、约束和CANDIDATE/CONFIRMED/REJECTED。AI_CANDIDATE只能是
  CANDIDATE且不得冒用人工actor；HUMAN必须固定用户。Evidence与AI Task引用留A04规范化物理化。
- Assumption、Exclusion、Dependency是版本内有序文本声明；Dependency不代替A09 RequirementRelation
  图。六表INSERT/UPDATE/DELETE/TRUNCATE全部关闭，A06完整版本创建Owner前无产品写路径。

## 验证

- Windows 11 / PostgreSQL 18.6：0116→head→0116→head、两次drift、六表/trigger/约束、合法集合、
  Handover缺version、空Acceptance、AI伪CONFIRMED、未知Capability、跨Project和重复ordinal负例、关闭写/
  TRUNCATE以及有历史降级拒绝全部通过；临时库清理。
- 管理员fixture使用`session_replication_role=replica`固定上游User/Project/Requirement/Version/Capability；
  六表Owner trigger仅在物理负例和历史保护验证期间停用并恢复，不构成业务数据或后门。
- 定向17项、后端全量2982项通过，3项既有环境跳过；开发wheel共1126项，SHA-256
  `4f8e8316b4aa002dd106501089aec77eb5947ab65744421ec1ff940241dc8a03`，不是正式发行包。

无公开API、前端、依赖、Secret、客户数据或外发变化；A04、A05～A12、Gate3/UAT/发行仍待完成。
