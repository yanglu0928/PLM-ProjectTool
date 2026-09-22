# 核心实体与聚合目录 V1 候选

## 状态

`CANDIDATE / DM-01_COMPLETE / NOT_GATE_2_FROZEN / NOT_PHYSICAL_SCHEMA`

本文件定义实体所有权、业务 Scope、Aggregate Root 和事实语义。它不定义 PostgreSQL 表名、列类型、外键、索引、约束名称或 Alembic Migration；物理设计属于 Database Schema V1。

## 建模术语

### Scope

|Scope|含义|ProjectId 规则|
|---|---|---|
|DEPLOYMENT|单套部署级身份、配置、安全或运行状态|显式为空；仅受权全局操作|
|GLOBAL|跨项目共享的正式基线或模板|显式为空；必须走 Global Authorization|
|PROJECT|单项目业务与知识对象|必填且必须与主体、引用对象交叉校验|
|GLOBAL_OR_PROJECT|创建时选择且不可静默换 Scope|PROJECT 时 ProjectId 必填|
|DEVELOPER_WORKBENCH|开发者侧离线记录，不进入客户运行数据库|不适用|

### 事实语义

|语义|说明|
|---|---|
|系统事实|经受权命令产生的身份、配置、文件、权限或运行状态|
|运行事实|Job、解析、检索、调用等可重试过程状态；不等于业务结论|
|不可变记录|Audit、Trace、Review Decision、Outbox 等只追加/替代，不原地改写历史|
|AI 建议|模型输出；永远不是正式业务事实|
|可正式化业务版本|先创建 Draft Version，经 Review 后指定版本成为正式版本|
|可正式化业务事实|经受权人工创建或从已确认版本产生，经规则/Review 后成为正式事实|
|用户提交事实|用户明确提交的原始回答/输入；结论仍需独立 Review|
|证据/参考事实|受权文件定位或参考资料；可支持结论但不自动成为项目正式方案|
|生成制品|由已授权输入派生的文件；不反向改变源对象正式状态|
|签名安全状态|由签名、机器、时间或包验证形成的受控状态|
|开发侧记录|只存在 Developer Workbench，不下发客户数据库|

## 聚合通用规则

1. Aggregate Root 是模块内唯一写入口；其他模块只保存稳定 ID/Version Ref，并通过 Owner 的 Application Port 修改。
2. PROJECT 聚合在创建时确定 ProjectId，生命周期内不得换项目；跨项目复制创建新聚合、新版本和 Audit。
3. 逻辑对象与不可变 Version 分离：逻辑对象保存身份和当前正式版本引用，Version 保存内容快照。历史 Version 不覆盖。
4. Package 只组织同 Scope 的对象引用，不拥有被引用对象的完整生命周期，不进行跨聚合级联删除。
5. 跨聚合关联实体必须验证两端存在、Scope 一致和调用者权限；跨项目关系默认拒绝。
6. 运行记录、Audit、Trace、Review Decision 和签名验证历史以追加方式记录；更正通过新记录或 supersede 关系表达。
7. AIInvocation 只能产生 AI 建议。人工显式接受后，由目标 Domain 创建新的 Draft Version，并记录 actor、AIInvocation、Evidence 和 InputVersion；不得在同一 AI 对象上切换“正式”布尔值。
8. ReviewSubject 必须指向不可变 Version Ref。Review 通过后，由主题 Owner 消费结果并更新逻辑对象的正式版本引用。
9. Data Model 中的删除默认解释为状态迁移/归档；物理清理、保留期和级联规则在 DM-06 与 Schema V1 明确。

## 客户运行时聚合目录

### Platform / Security

|ID|Owner|Aggregate Root|包含实体/值对象|Scope|事实语义|核心不变量|
|---|---|---|---|---|---|---|
|PLT-01|platform|SystemConfiguration|SystemSetting、ConfigVersion|DEPLOYMENT|系统事实|非 Secret 配置版本化；修改受权并审计|
|PLT-02|platform|SecretRecord|SecretVersion、SecretRef、EncryptedPayloadMetadata|DEPLOYMENT|签名/安全状态|密文与主材料分离；查询不回显明文|
|AUT-01|auth|User|PasswordCredential、AccountState|DEPLOYMENT|系统事实|用户名部署内唯一；密码仅哈希；停用使 Session 失效|
|AUT-02|auth|Session|SessionState、CsrfBinding|DEPLOYMENT|运行事实|服务端不透明会话；只属于一个 User；可撤销/过期|
|PRJ-01|project|Project|ProjectState、CurrentStageRef|DEPLOYMENT|系统事实|ProjectCode 唯一；Active → Archived 不可反向复活而无专用命令|
|PRJ-02|project|ProjectMember|RoleAssignment、DepartmentRef|PROJECT|系统事实|普通 User 只绑定一个 Project、一个业务角色、一个部门|
|PRJ-03|project|Department|DepartmentState|PROJECT|系统事实|部门只在本项目内唯一引用；停用前处理成员引用|
|WFL-01|workflow|ProjectWorkflow|Stage、StageChecklist、ChecklistItem|PROJECT|系统事实|阶段定义与项目一致；Gate 只消费已授权 Evidence/Review 状态|
|WFL-02|workflow|StageTransition|TransitionReason、GateSnapshot|PROJECT|不可变记录|只追加合法迁移；记录前后阶段、actor 与证据快照|
|RVW-01|review|Review|ReviewSubjectRef、ReviewPolicy、ReviewStatus|PROJECT|系统事实|一个 Review 只绑定一个不可变主题版本；送审期间锁定|
|RVW-02|review|ReviewRound|ReviewAssignment、ReviewDecision|PROJECT|不可变记录|1～N 处理人全部完成才汇总；任一退回则本轮退回；退回意见必填|
|TRC-01|trace|TraceLink|ObjectVersionRef、RelationType、SupersedeRef|GLOBAL_OR_PROJECT|不可变记录|只保存稳定引用；跨项目默认拒绝；历史 Link 不覆盖|
|AUD-01|audit|AuditEvent|ActorRef、ObjectRef、BeforeAfterSummary|DEPLOYMENT|不可变记录|Append-only；普通用户无删除能力；不含 Secret/正文|
|LIC-01|license|LicenseInstallation|SignedLicenseDocument、PublicKeyRef|DEPLOYMENT|签名安全状态|客户侧只验签；不含签名私钥；导入保留历史|
|LIC-02|license|LicenseValidationState|MachineFingerprintHash、EntitlementState、ValidationResult|DEPLOYMENT|签名安全状态|MAC 显式选择→Normalize→SHA-256；失败关闭|
|LIC-03|license|TrustedTimeState|LastSuccessfulTime、IntegrityMetadata|DEPLOYMENT|签名安全状态|原子前移；明显回拨拒绝并审计|

### Document / Evidence / Operations

|ID|Owner|Aggregate Root|包含实体/值对象|Scope|事实语义|核心不变量|
|---|---|---|---|---|---|---|
|DOC-01|document|Document|DocumentKind、CurrentVersionRefs、DocumentState|GLOBAL_OR_PROJECT|系统事实|逻辑身份不承载正文；Scope 创建后不可更换|
|DOC-02|document|DocumentVersion|FileObjectRef、VersionMetadata、SourceLocator|GLOBAL_OR_PROJECT|不可变记录|属于一个 Document；版本号单调；内容 Hash 固定|
|DOC-03|document|FileObject|StorageLocator、SHA256、Mime、Size|GLOBAL_OR_PROJECT|系统事实|StorageLocator 受控；Hash/Size 与落盘内容一致；不返回绝对路径|
|DOC-04|document|ParseRecord|DocumentVersionRef、ParserVersion、ParseStatus、ResultRef|GLOBAL_OR_PROJECT|运行事实|只解析不可变版本；结果绑定 Parser/Input 版本|
|EVD-01|evidence|Evidence|EvidenceLocator、DocumentVersionRef、EligibilityState|GLOBAL_OR_PROJECT|证据/参考事实|必须定位不可变 DocumentVersion；Locator 可解析|
|EVD-02|evidence|EvidenceBinding|EvidenceRef、SubjectVersionRef、Purpose|PROJECT|不可变记录|Evidence 与 Subject Scope 一致；绑定不复制正文|
|JOB-01|jobs|Job|JobAttempt、JobLease、RetryPolicy、CancellationState|GLOBAL_OR_PROJECT|运行事实|至少一次；租约唯一；可重试写必须幂等|
|JOB-02|jobs|OutboxEvent|EventType、PayloadRefs、DeliveryState|GLOBAL_OR_PROJECT|不可变记录|与业务事务同提交；Payload 不含 Secret/正文；消费者去重|

### AI / RAG / Capability

|ID|Owner|Aggregate Root|包含实体/值对象|Scope|事实语义|核心不变量|
|---|---|---|---|---|---|---|
|AI-01|ai|AIProvider|ProviderPolicy、EndpointPolicy、SecretRef|DEPLOYMENT|系统事实|只持 SecretRef；业务模块不可见厂商凭据|
|AI-02|ai|AIModel|ProviderRef、Capabilities、ModelState|DEPLOYMENT|系统事实|Model 标识稳定；Embedding 维度变更视为新模型/版本|
|AI-03|ai|PromptTemplate|PromptVersion、TaskType、OutputSchemaRef、RagPolicy|DEPLOYMENT|系统事实|Prompt 修改创建新版本；已使用版本不可覆盖|
|AI-04|ai|AITask|AIInvocation、InputVersionRef、SuggestionPayload、Usage|GLOBAL_OR_PROJECT|AI 建议|输出固定 NOT_FORMAL_FACT；Schema 失败不能进入 Domain Draft|
|RAG-01|rag|DocumentChunk|DocumentVersionRef、ChunkLocator、Text、Metadata|GLOBAL_OR_PROJECT|知识记录|Chunk 绑定不可变版本；PROJECT 必须含 ProjectId|
|RAG-02|rag|EmbeddingIndex|AIModelRef、Dimension、IndexVersion、ActivationState|GLOBAL_OR_PROJECT|系统事实|一个 Index 绑定一个模型/维度；激活切换受控|
|RAG-03|rag|EmbeddingRecord|IndexRef、ChunkRef、VectorFingerprint|GLOBAL_OR_PROJECT|运行事实|Index/Chunk Scope 一致；不得跨模型复用向量|
|RAG-04|rag|RetrievalRun|QueryHash、CandidateRefs、ScoreBreakdown、RerankState|PROJECT|运行事实|ProjectId 失败关闭；结果绑定 Index/Model/Policy 版本|
|CAP-01|capability|CapabilityBaseline|BaselineIdentity、CurrentApprovedVersionRef|GLOBAL|可正式化业务版本|只能引用已 Review 的 BaselineVersion 作为正式版本|
|CAP-02|capability|BaselineVersion|CapabilityItem、SourceEvidenceRefs、ReviewSubjectRef|GLOBAL|可正式化业务版本|版本不可变；Item 来源可追溯；AI 仅可生成 Draft|

### Handover / Survey / Requirement

|ID|Owner|Aggregate Root|包含实体/值对象|Scope|事实语义|核心不变量|
|---|---|---|---|---|---|---|
|HND-01|handover|HandoverAnalysis|CurrentApprovedVersionRef、AnalysisState|PROJECT|可正式化业务版本|正式状态只指向已 Review 的版本|
|HND-02|handover|HandoverAnalysisVersion|AnalysisItem、SourceEvidenceRefs、ReviewSubjectRef|PROJECT|可正式化业务版本|Gap/Missing/Conflict/Risk/Scope/NeedConfirm 受控；版本不可变|
|HND-03|handover|ActionItem|SourceAnalysisItemRef、OwnerRef、ActionState|PROJECT|可正式化业务事实|必须追溯已确认分析或显式人工创建；AI 不能直接创建正式待办|
|SRV-01|survey|Survey|CurrentVersionRef、SurveyState|PROJECT|可正式化业务版本|定义与执行分离；正式定义指向指定 SurveyVersion|
|SRV-02|survey|SurveyVersion|Question、SourceRefs、ReviewSubjectRef|PROJECT|可正式化业务版本|版本不可变；问题来源可追溯；实际调研记录优先于参考表单|
|SRV-03|survey|SurveyRound|SurveyVersionRef、RoundState、ScheduleMetadata|PROJECT|系统事实|一个 Round 绑定一个 SurveyVersion；关闭后不可接收新提交|
|SRV-04|survey|SurveyAssignment|AssigneeRef、Response、Answer、SubmissionState|PROJECT|用户提交事实|Assignment 属于一个 Round；提交后保留原始回答历史|
|SRV-05|survey|SurveyConclusion|DepartmentConclusion、ModuleConclusion、EvidenceRefs、ReviewSubjectRef|PROJECT|可正式化业务版本|结论与原始回答分离；AI 总结必须经 Review|
|REQ-01|requirement|RequirementPackage|RequirementRefs、PackageState|PROJECT|可正式化业务事实|只组织同项目 Requirement；不级联删除 Requirement|
|REQ-02|requirement|Requirement|CurrentApprovedVersionRef、RequirementState|PROJECT|可正式化业务版本|正式身份只指向已 Review 的 RequirementVersion|
|REQ-03|requirement|RequirementVersion|RequirementSource、AcceptanceCriterion、EvidenceRefs、ReviewSubjectRef|PROJECT|可正式化业务版本|版本不可变；来源和验收标准必可追溯；AI 仅生成 Draft|
|REQ-04|requirement|RequirementRelation|SourceRequirementRef、TargetRequirementRef、RelationType|PROJECT|不可变记录|两端同项目且不能产生禁止的自关系/非法环|

### Prototype / Solution / Plan

|ID|Owner|Aggregate Root|包含实体/值对象|Scope|事实语义|核心不变量|
|---|---|---|---|---|---|---|
|PRT-01|prototype|PrototypePackage|PrototypeRefs、PackageState|PROJECT|可正式化业务事实|只组织同项目 Prototype；不拥有版本历史|
|PRT-02|prototype|Prototype|CurrentApprovedVersionRef、PrototypeState|PROJECT|可正式化业务版本|正式身份只指向已 Review 的 PrototypeVersion|
|PRT-03|prototype|PrototypeVersion|ArtifactRefs、RequirementRefs、ReviewSubjectRef|PROJECT|可正式化业务版本|版本不可变；需求映射完整；生成内容先为 Draft|
|PRT-04|prototype|PrototypeTemplate|TemplateVersion、TemplateArtifactRef|GLOBAL_OR_PROJECT|可正式化业务版本|模板版本化；GLOBAL 模板不得反写项目对象|
|PRT-05|prototype|RequirementPrototypeLink|RequirementVersionRef、PrototypeVersionRef、Purpose|PROJECT|不可变记录|两端同项目并指向不可变版本|
|SOL-01|solution|ReferenceSolution|ReferenceVersion、DocumentVersionRefs、EligibilityState|GLOBAL_OR_PROJECT|证据/参考事实|参考材料不自动成为项目正式 Solution|
|SOL-02|solution|SolutionOutline|CurrentApprovedVersionRef、OutlineState|PROJECT|可正式化业务版本|正式身份只指向已 Review 的 OutlineVersion|
|SOL-03|solution|SolutionOutlineVersion|SectionOrderRefs、RequirementRefs、ReviewSubjectRef|PROJECT|可正式化业务版本|章节顺序和需求覆盖在版本内固定|
|SOL-04|solution|SolutionSection|CurrentApprovedVersionRef、SectionState|PROJECT|可正式化业务版本|每个逻辑章节保留独立版本历史|
|SOL-05|solution|SolutionSectionVersion|ContentRef、EvidenceRefs、RequirementRefs、ReviewSubjectRef|PROJECT|可正式化业务版本|版本不可变；AI Generated Section 必须保持 Draft 直到 Review|
|SOL-06|solution|StructuredSolutionSpec|ProcessModel、InterfaceSpec、MigrationSpec、PermissionDesign、VersionRef|PROJECT|可正式化业务版本|每项绑定 Solution/Requirement 版本；修改产生新版本|
|PLN-01|plan|Plan|CurrentApprovedVersionRef、PlanState|PROJECT|可正式化业务版本|正式身份只指向已 Review 的 PlanVersion|
|PLN-02|plan|PlanVersion|WbsItem、WbsDependency、Milestone、ReviewSubjectRef|PROJECT|可正式化业务版本|版本不可变；WBS 层级≤6；依赖仅 FS；无循环依赖|
|PLN-03|plan|ReferencePlan|ReferencePlanVersion、SourceDocumentRefs|GLOBAL_OR_PROJECT|证据/参考事实|参考计划不自动成为项目正式 Plan|

### Output / Plugin

|ID|Owner|Aggregate Root|包含实体/值对象|Scope|事实语义|核心不变量|
|---|---|---|---|---|---|---|
|OUT-01|output|OutputRequest|OutputContextSnapshot、SourceVersionRefs、OutputPolicy|PROJECT|运行事实|Context 只含已授权最小数据并固定源版本|
|OUT-02|output|OutputArtifact|DocumentVersionRef、PluginExecutionRef、ArtifactHash|PROJECT|生成制品|校验/Hash/登记完成后可访问；不改变源对象正式状态|
|PLG-01|plugin|PluginPackage|Manifest、Signature、PackageHash、PluginApiVersion|DEPLOYMENT|签名安全状态|只接受开发者签名包；入口/OS/依赖必须验证|
|PLG-02|plugin|PluginInstallation|PluginPackageRef、EnabledState、CompatibilityResult|DEPLOYMENT|系统事实|启用只针对已验证 Package；历史安装保留|
|PLG-03|plugin|PluginExecution|OutputContextRef、AttemptState、ResultMetadata|PROJECT|运行事实|最小环境；无 DB/AI Key；timeout/crash 不影响主进程|

## Developer Workbench 聚合（客户数据库之外）

|ID|Owner|Aggregate Root|Scope|事实语义|边界|
|---|---|---|---|---|---|
|DEV-01|developer_workbench|LicenseIssuanceRecord|DEVELOPER_WORKBENCH|开发侧记录|私钥仅在工作台；向客户输出签名 License/公钥|
|DEV-02|developer_workbench|PluginSigningRecord|DEVELOPER_WORKBENCH|开发侧记录|签名开发者 Plugin 包；不接收客户 AI Key/数据库|
|DEV-03|developer_workbench|ReleaseBuildRecord|DEVELOPER_WORKBENCH|开发侧记录|记录制品、Hash、许可证和源码对应关系|

Developer Workbench 数据不进入客户 PostgreSQL Schema，也不与客户 ProjectId 建立 TraceLink。

## 跨聚合引用合同

|引用类型|允许内容|禁止内容|
|---|---|---|
|ObjectRef|owner_module、object_type、object_id|ORM Entity、可变对象副本|
|ObjectVersionRef|ObjectRef + version_id/version_no|“当前版本”模糊指针作为历史证据|
|ActorRef|user_id 或受控 system_actor + original_actor_id|Session/Cookie/密码信息|
|EvidenceRef|evidence_id + document_version_id + locator|文件绝对路径、未授权正文|
|SecretRef|secret_id + active_version_ref|明文 Secret、解密材料|
|Job/Event Payload Ref|对象/版本/策略标识|文件正文、Prompt 全文、客户资料副本|

所有跨模块引用由被引用 Owner 校验存在性和 Scope。读取“当前正式版本”时必须由 Owner 解析，调用方不得自行拼接或更新 current pointer。

## AI 建议到正式版本

```text
AITask / AIInvocation
  → SuggestionPayload (NOT_FORMAL_FACT)
  → human explicitly accepts selected suggestion + Evidence
  → Domain Owner creates new immutable Draft Version
  → ReviewSubject points to that Version
  → ReviewRound completed
  → Domain Owner marks that Version approved/current
  → TraceLink + AuditEvent
```

- AI Suggestion 与 Domain Draft 是两个不同聚合中的对象，具有不同 ID、Owner 和权限。
- 接受动作记录人工 actor、来源 AIInvocation、Prompt/Input/Index 版本和 Evidence；拒绝/未处理建议不得生成正式草稿。
- Review 退回后修改必须创建新 Domain Version 和新 ReviewRound；原建议、原版本和原决定保留。
- 用户直接创建的 Draft 不要求 AIInvocation，但仍需要 Evidence/来源规则和 Review。

## Owner 与覆盖检查

|模块|客户运行 Aggregate Root 数|
|---|---:|
|platform|2|
|auth|2|
|project|3|
|workflow|2|
|document|4|
|evidence|2|
|review|2|
|trace|1|
|audit|1|
|jobs|2|
|ai|4|
|rag|4|
|capability|2|
|handover|3|
|survey|5|
|requirement|4|
|prototype|5|
|solution|6|
|plan|3|
|output|2|
|plugin|3|
|license|3|
|**合计**|**65**|

另有 Developer Workbench 3 个开发侧 Aggregate Root。22 个客户运行模块均有唯一数据 Owner；没有孤立实体或由两个模块共同拥有的实体。

## DM-01 新增的必要版本根

为满足 AF-02 的 Review/Event 和“历史版本不得覆盖”约束，本候选显式补充以下在 V2.1 简表中未完整列出的逻辑版本根：

- `HandoverAnalysisVersion`
- `PlanVersion`
- `SolutionOutlineVersion` / `SolutionSectionVersion`（V2.1 已列出，模块边界摘要未展开）
- `TrustedTimeState`
- `OutboxEvent`

这些是既有架构语义的结构化补全，不新增产品 Scope、技术组件或业务功能。

## 后续任务输入

- DM-02：细化 User/Session/ProjectMember、Role、Workflow、Review、Audit、Secret、License 与可信时间的状态、不变量和关系。
- DM-03：细化 Document/FileObject/ParseRecord、Evidence、Trace 和版本保留。
- DM-04：细化 AI/RAG/Job/Plugin/Output 的状态机和引用约束。
- DM-05：细化 Capability 到 Plan 的业务主链、版本、Review 和 Trace。
- DM-06：统一基数、生命周期、删除/归档/保留策略和模型风险。

## DM-01 验收

- 22 个客户运行模块全部映射到唯一数据 Owner：PASS。
- 65 个客户运行 Aggregate Root 均声明 Scope、事实语义和核心不变量：PASS。
- Developer Workbench 3 个聚合与客户运行数据库物理隔离：PASS。
- 逻辑对象、不可变 Version、ReviewSubject 和 current approved pointer 的职责明确：PASS。
- AI Suggestion 与 Domain Draft 使用不同聚合，不能通过状态字段静默正式化：PASS。
- 跨聚合只使用稳定 ID/Version/Evidence/Secret 引用，不共享 ORM Entity：PASS。
- 新增版本根均可追溯到已批准的 Review、Event、License 或 Outbox 架构语义：PASS。
- 未定义表、列、索引、物理外键或 Migration，未提前进入 Schema/编码：PASS。

## 下一步

DM-02：平台与安全数据模型，冻结身份、Session、Project Membership、Workflow、Review、Audit、Secret、License 与可信时间的不变量和关系。
