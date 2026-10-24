# PLM 项目实施辅助工具 Data Model Candidate V1

## 状态

`DATA-MODEL-CANDIDATE-V1 / DM-01～DM-06_PASS / FROZEN_AT_GATE_2 / NOT_PHYSICAL_SCHEMA`

本文件汇总 DM-01～DM-05 的数据模型结论，统一 22 个客户运行模块、65 个 Aggregate Root、跨聚合关系、基数、生命周期、Scope、删除/保留和风险。详细字段与状态仍以本文件列出的下级候选为准；出现表述差异时，本文件的统一规则优先，但不得覆盖已锁定架构、ADR、用户批准例外或实施方案 V2.1。

本文件已于 2026-09-23 随 Architecture、Database Schema V1 与 API Contract V1 通过 Gate 2 并冻结为 Data Model V1 正式开发基线，冻结内容固定为提交 `64cdf09`。候选标识为保持历史 Trace 不重命名；它仍不是 PostgreSQL Schema、Alembic Migration 或 REST API Contract，物理实现须按冻结 Schema/API 和后续 WBS 完成。

## 输入与组成

|来源|作用|
|---|---|
|`core-entity-aggregate-catalog-v1-candidate.md`|65 个客户运行 Aggregate Root、22 个唯一 Owner、Scope 与事实语义|
|`platform-security-model-v1-candidate.md`|身份、Session、项目成员、Workflow、Review、Audit、Secret、License|
|`document-evidence-trace-model-v1-candidate.md`|Document/FileObject/Parse、Evidence 定位、Trace 与文件恢复|
|`ai-rag-job-plugin-output-model-v1-candidate.md`|AI/RAG、Job/Outbox、Plugin、Output 的运行与建议态|
|`implementation-domain-model-v1-candidate.md`|Capability 到 Plan 的实施业务主链|
|Architecture Candidate、ADR-003～009|模块边界、公共 Contract、信任区和技术约束|
|Phase 0 总结与例外|验证事实、未验证平台、POC-03 质量失败和批准替代控制|

## 汇总结论

1. 客户运行时固定 22 个模块、65 个 Aggregate Root；每个 Root 只有一个 Owner。Developer Workbench 另有 3 个 Root，物理隔离且不进入客户数据库。
2. 所有数据明确属于 `DEPLOYMENT / GLOBAL / PROJECT / GLOBAL_OR_PROJECT / DEVELOPER_WORKBENCH` 之一；PROJECT 数据必须有可验证 ProjectId，跨项目默认拒绝。
3. 正式业务制品统一采用“逻辑身份 + 不可变 Version + current approved pointer”；ReviewRound 绑定固定 Version，修改创建新 Version。
4. AI Suggestion、运行事实、参考资料、用户提交事实、系统事实、正式业务版本和签名安全状态是不同事实语义，不能通过改一个状态字段相互冒充。
5. EvidenceBinding 表达原文对结论的支持/反驳，TraceLink 表达业务制品间来源/实现关系；两者不可合并或复制正文。
6. 文件正文保存在本地文件系统，PostgreSQL 保存元数据、状态和受控 Locator；数据库/文件非原子窗口由 STAGED、恢复器和 Audit 处理。
7. 长任务使用 PostgreSQL Job/Outbox、至少一次、幂等和 Lease fencing；不引入 Redis、消息队列或精确一次承诺。
8. AI、Embedding、Reranker 外发均绑定本次授权快照；业务模块只调用 AIService/RetrievalService，不直连厂商 SDK 或 pgvector SQL。
9. Plugin 只运行开发者签名包，通过独立 Python 子进程和 JSON-RPC stdio；插件无数据库、AI Key 或 License 私钥。
10. 普通“删除”统一解释为撤销、停用、归档或替代。物理清理必须同时满足到期、零保护引用、无 Hold、受权、预检和 Audit。
11. 实际调研记录优先于调研模板；标准/非标/差异/待确认均是项目版本化判断，不自动改变 GLOBAL 标准能力。
12. POC-03 Top-5 98% 通过但分类 48%、引用 74% 失败，继续作为 Gate 3/UAT 阻塞；数据模型完成不代表 AI 质量通过。

## 模块与 Aggregate Root 覆盖

|模块|Root 数|核心 Root / 职责|
|---|---:|---|
|platform|2|SystemConfiguration、SecretRecord|
|auth|2|User、Session|
|project|3|Project、ProjectMember、Department|
|workflow|2|ProjectWorkflow、StageTransition|
|document|4|Document、DocumentVersion、FileObject、ParseRecord|
|evidence|2|Evidence、EvidenceBinding|
|review|2|Review、ReviewRound|
|trace|1|TraceLink|
|audit|1|AuditEvent|
|jobs|2|Job、OutboxEvent|
|ai|4|AIProvider、AIModel、PromptTemplate、AITask|
|rag|4|DocumentChunk、EmbeddingIndex、EmbeddingRecord、RetrievalRun|
|capability|2|CapabilityBaseline、BaselineVersion|
|handover|3|HandoverAnalysis、HandoverAnalysisVersion、ActionItem|
|survey|5|Survey、SurveyVersion、SurveyRound、SurveyAssignment、SurveyConclusion|
|requirement|4|RequirementPackage、Requirement、RequirementVersion、RequirementRelation|
|prototype|5|PrototypePackage、Prototype、PrototypeVersion、PrototypeTemplate、RequirementPrototypeLink|
|solution|6|ReferenceSolution、SolutionOutline、SolutionOutlineVersion、SolutionSection、SolutionSectionVersion、StructuredSolutionSpec|
|plan|3|Plan、PlanVersion、ReferencePlan|
|output|2|OutputRequest、OutputArtifact|
|plugin|3|PluginPackage、PluginInstallation、PluginExecution|
|license|3|LicenseInstallation、LicenseValidationState、TrustedTimeState|
|**合计**|**65**|每个 Root 具有唯一 Owner|

Developer Workbench：LicenseIssuanceRecord、PluginSigningRecord、ReleaseBuildRecord，共 3 个，仅输出签名制品/公钥/发行物，不读取客户项目数据库或客户资料。

## Scope 与授权不变量

### Scope 定义

|Scope|归属|允许引用|禁止事项|
|---|---|---|---|
|DEPLOYMENT|单一安装实例|部署配置、User、Session、Plugin、License|不得承载客户项目正文或充当跨项目共享区|
|GLOBAL|受控公共能力|Capability、标准资料、GLOBAL Review/Evidence/RAG|项目用户不得反写；GLOBAL 内容不得含客户资料|
|PROJECT|恰好一个 Project|同项目对象及明确授权 GLOBAL Version|跨项目关系、共享可写文件、缺失 ProjectId|
|GLOBAL_OR_PROJECT|创建时确定一种 Scope|按具体实例执行 GLOBAL 或 PROJECT 规则|创建后切换 Scope、模糊空 ProjectId|
|DEVELOPER_WORKBENCH|开发者工作台|签名/发行记录|进入客户数据库、接触客户 Key/资料|

### 强制不变量

1. PROJECT Root 的 project_id 创建后不可变；所有子实体和值对象继承 Root Scope。
2. PROJECT 引用 PROJECT 时两端 ProjectId 必须相同；A↔B 跨项目全部拒绝。
3. PROJECT→GLOBAL 写关系默认拒绝；GLOBAL→PROJECT 只允许明确的 Reference/Capability/Evidence/Trace 语义，目标仍属于 PROJECT。
4. GLOBAL 查询、导入和 Review 需要独立全局授权；DeploymentAdmin 也不能绕过 Session、License、资源状态或 Audit。
5. 普通用户无权根据错误、列表、Trace 图、文件路径或 ID 推断其他项目对象存在性。
6. Worker/Plugin/SystemActor 不拥有跨项目通配权，必须继承并复核原 actor、ProjectId、目的和 trace_id。

## 统一引用类型

|引用类型|最小语义|解析 Owner|可否保存正文|
|---|---|---|---|
|ObjectRef|owner_module、object_type、object_id|目标模块|否|
|ObjectVersionRef|ObjectRef + immutable version_id/version_no|目标模块|否|
|EvidenceRef|evidence_id → DocumentVersion + typed locator|evidence/document|否；仅受限显示摘录|
|SecretRef|secret_record/version 的受控引用|platform/Secret Adapter|否|
|ReviewSubjectRef|逻辑主题 + 固定主题版本 + 指纹|review/主题 Owner|否|
|AITaskRef|建议任务、Invocation 和输入版本|ai|否；结果通过受权 DTO|
|JobRef / EventRef|运行/交付身份与策略版本|jobs/事件 Owner|否|
|ArtifactRef|OutputArtifact/DocumentVersion 固定制品|output/document|否|

- 引用只保存稳定身份、版本和必要分类，不共享 ORM Entity。
- Polymorphic Ref 的目标存在性、Owner、Scope 和状态必须由目标 Application Port 或 Schema V1 的受控引用机制验证。
- 正式链优先 ObjectVersionRef；ObjectRef 仅用于逻辑身份、列表导航和 current pointer 解析。

## 关系与基数总表

### Platform、Security 与 Review

|关系|基数|关键约束|
|---|---|---|
|Project → Department|1 : 0..N|DepartmentCode 项目内唯一；被成员引用时不能物理删除|
|Project → ProjectMember|1 : 0..N|同 User 最多一个有效项目成员；普通 User 只能属于一个项目|
|User → Session|1 : 0..N|credential_version/账户状态变化使旧 Session 失效|
|Project → ProjectWorkflow|1 : 1|Workflow 唯一拥有当前阶段；Project 不复制 current stage|
|ProjectWorkflow → StageTransition|1 : 0..N|只追加合法迁移和 GateSnapshot|
|Review → ReviewRound|1 : 1..N|同 Review 最多一个 Active Round|
|Review → logical subject|N : 1|Review 绑定逻辑主题身份|
|ReviewRound → subject Version|N : 1|每轮绑定一个不可变 Version；历史不覆盖|
|SecretRecord → SecretVersion|1 : 1..N|最多一个 Active；明文不进入业务引用|
|LicenseInstallation → validation/trusted time|1 : 1 / 1|签名、机器、时间失败关闭；私钥不在客户侧|
|Aggregate/Command → AuditEvent|1 : 0..N|Audit append-only，不作为业务事务真相来源|

### Document、Evidence 与 Trace

|关系|基数|关键约束|
|---|---|---|
|Document → DocumentVersion|1 : 1..N|version_no 单调；latest/effective 属于同 Document|
|DocumentVersion → FileObject|1 : 1|只引用 PERSISTENT + AVAILABLE；V1 不跨 Document 逻辑复用|
|DocumentVersion → ParseRecord|1 : 0..N|按 parser/profile/version 保留 Attempt 历史|
|DocumentVersion → Evidence|1 : 0..N|Locator 必须在固定版本可重放|
|Evidence → EvidenceBinding|1 : 0..N|PROJECT Evidence 只绑定同项目；GLOBAL 可受控支持项目|
|SubjectVersion → EvidenceBinding|1 : 0..N|送审时冻结 Evidence 集合；冲突证据不得隐藏|
|Object/Version ↔ TraceLink|1 : 0..N|source/target 不自环；跨项目拒绝；逐节点授权|
|TraceLink → replacement|1 : 0..1|更正通过 supersede，不原地覆盖|

### AI、RAG、Job、Plugin 与 Output

|关系|基数|关键约束|
|---|---|---|
|AIProvider → AIModel|1 : 0..N|Model 只属于一个 Provider；Embedding Dimension 固定|
|PromptTemplate → PromptVersion|1 : 1..N|不可变；最多一个 Active 指针|
|AITask → AIInvocation|1 : 0..N|重试创建新 Attempt；输出固定 NOT_FORMAL_FACT|
|AITask → accepted Domain Draft|1 : 0..1|仅人工接受后由业务 Owner 创建|
|DocumentVersion → DocumentChunk|1 : 0..N|按 Parse/Chunk generation 保留|
|EmbeddingIndex → EmbeddingRecord|1 : 0..N|每 Chunk 最多一个 AVAILABLE；Scope/Model/Dimension 一致|
|RetrievalRun → ContextBundle|1 : 0..N|最小已授权 Context；不含 Golden 标签/人工答案|
|Job → JobAttempt / JobLease|1 : 0..N / 0..N|同时最多一个有效 Lease；fencing token 单调|
|AggregateVersion → OutboxEvent|1 : 0..N|与业务事务同提交；消费者去重|
|PluginPackage → PluginInstallation|1 : 0..N|只安装 VERIFIED 未撤销的精确包版本|
|OutputRequest → PluginExecution|1 : 0..N|重试/重新生成不覆盖历史|
|OutputRequest → OutputArtifact|1 : 0..N|校验、Hash、DocumentVersion 完整后 AVAILABLE|

### 实施业务主链

|关系|基数|关键约束|
|---|---|---|
|CapabilityBaseline → BaselineVersion|1 : 1..N|仅 Approved Version 用于正式能力匹配|
|HandoverAnalysis → AnalysisVersion|1 : 1..N|固定项目资料与 BaselineVersion|
|AnalysisVersion → ActionItem|1 : 0..N|每项回溯 source item；Submitted 不等于 Closed|
|Survey → SurveyVersion|1 : 1..N|问题集不可变；模板不生成事实|
|SurveyVersion → SurveyRound|1 : 0..N|Round 绑定一个版本；Closed 不接收提交|
|SurveyRound → SurveyAssignment|1 : 0..N|同对象唯一；Response/Answer 历史保留|
|Survey/Rounds → SurveyConclusion|1 : 0..N|结论按 series/version 替代；必须追溯实际记录|
|RequirementPackage → Requirement|N : N（引用集合）|只组织同项目对象；不级联删除|
|Requirement → RequirementVersion|1 : 1..N|正式指针只指向 Approved Version|
|RequirementVersion ↔ RequirementRelation|1 : 0..N|两端同项目；依赖/父子关系不得非法成环|
|Prototype → PrototypeVersion|1 : 1..N|Artifact、Template 和 Requirement Version 固定|
|RequirementVersion ↔ PrototypeVersion|N : N（Link）|覆盖或明确 NOT_REQUIRED/缺口|
|SolutionOutline → OutlineVersion|1 : 1..N|章节顺序和输入版本固定|
|SolutionSection → SectionVersion|1 : 1..N|正文、Evidence、Requirement 映射固定|
|SectionVersion → StructuredSolutionSpec|N : N（版本引用）|流程/接口/迁移/权限结构校验|
|RequirementVersion → Solution Version|N : N（快照 + Trace）|覆盖快照与 IMPLEMENTS Trace 必须一致|
|Plan → PlanVersion|1 : 1..N|最多六级 WBS、仅 FS、DAG 无环|
|PlanVersion → WbsItem/Dependency/Milestone|1 : 1..N / 0..N / 0..N|同版本内引用；日期/工期/Gate 一致|

## 生命周期族

### A. 逻辑身份类

适用：Project、Document、CapabilityBaseline、HandoverAnalysis、Survey、Requirement、Prototype、SolutionOutline/Section、Plan 等。

```text
ACTIVE → ARCHIVED
ACTIVE / ARCHIVED → RESTRICTED（安全/合规旁路状态）
```

- V1 不提供普通业务反归档；若 Release 前加入，必须专用命令、理由、授权和 Audit。
- 逻辑身份不承载大正文，不允许复用已归档 ID 代表新对象。

### B. 不可变版本类

适用：DocumentVersion、BaselineVersion、业务 Version、PromptVersion、部分配置版本。

```text
DRAFT → IN_REVIEW → APPROVED → SUPERSEDED
   └──────────────→ RETURNED
任意历史可读状态 → RESTRICTED / REVOKED（按对象语义）
```

- Version 内容在创建后不可变；若需要编辑，使用 Draft Builder/Working Copy，提交时形成新 Version。
- RETURNED 后创建新 Version 和 ReviewRound；APPROVED/SUPERSEDED 历史不覆盖。

### C. 追加式记录类

适用：AuditEvent、StageTransition、ReviewRound/Decision、TraceLink、EvidenceBinding、OutboxEvent 历史。

- 只追加、撤销或 supersede，不原地改写业务历史。
- 更正事件指向被更正记录并说明原因；普通用户无物理删除能力。

### D. 可重试运行类

适用：Job、ParseRecord、AIInvocation、RetrievalRun、PluginExecution、OutputRequest。

```text
PENDING/QUEUED → RUNNING → SUCCEEDED
                    ├──→ RETRY_WAIT → RUNNING
                    ├──→ FAILED
                    └──→ CANCEL_REQUESTED → CANCELLED
```

- 每次 Attempt 保留独立记录；终态不复活。
- 重试写必须幂等；过期 Lease 的 Worker 不能发布结果。

### E. 构建与激活类

适用：EmbeddingIndex、PluginInstallation、Prompt/配置 Active 指针。

```text
PLANNED/INSTALLED → BUILDING/VERIFIED → READY → ACTIVE → RETIRED
                                   └──→ FAILED/INCOMPATIBLE
```

- 同 Scope + Purpose 最多一个 ACTIVE；激活切换需审计并保留历史。
- 模型/维度/Chunk Profile 不兼容变化创建新索引并全量重建。

### F. 签名与安全状态类

适用：SecretVersion、PluginPackage、LicenseInstallation/Validation、TrustedTimeState。

- 签名/Hash/机器/时间/Secret 失败关闭，不能自动降级绕过。
- 私钥只在 Developer Workbench；客户侧只保留公钥和签名制品。
- Secret 明文只在单次 Adapter 调用内存作用域；历史仅保留版本引用和 Audit。

## 正式化与变更传播

```text
Source Evidence / Approved Upstream Versions
 → AITask / AIInvocation Suggestion (optional)
 → explicit human accept or direct human authoring
 → new Domain Draft Version
 → Evidence + Trace completeness validation
 → ReviewRound bound to immutable Version snapshot
 → ReviewCompleted
 → Domain Owner updates current approved pointer
 → TraceLink + OutboxEvent + AuditEvent
```

- AI 成功、Schema VALID、高置信度、标准能力直接匹配或插件成功都不能替代人工 Review。
- 上游 Approved Version 被替代时，下游版本不自动改写；标记 `UPSTREAM_CHANGED` 并创建影响分析待办。
- Active Review 期间主题版本锁定；并发修改使用 expected_version/lock_version，禁止 last-write-wins。
- 正式指针更新、所属模块 Trace/Outbox/Audit 在 Owner 的短事务中完成；跨模块结果通过 Port + Outbox 至少一次传播。

## 删除、归档、保留与 Legal Hold

### RetentionPolicy 与 Hold 语义

RetentionPolicy 和 RetentionHoldEntry 由 `platform.SystemConfiguration` 拥有，是配置版本内的受控子实体，不新增 Aggregate Root。每个策略至少包含 policy_id/version、适用对象、起算事件、默认期限、允许的延长规则、清理动作、批准角色和 Audit 要求。

RetentionHoldEntry 至少包含 hold_id、Scope/ProjectRef、object selector、reason、created_by/at、release_by/at 和 state。Active Hold 优先级高于任何 TTL/到期时间；解除 Hold 只允许新增解除记录，不删除原 Hold 历史。

### V1 保留类别与候选默认值

以下为产品候选默认值，不构成法规或客户合同结论。部署/合同可延长；缩短涉及正式/审计数据时必须在 Gate 2/Release 明确评审，且不能突破保护引用和 Active Hold。

|类别|对象示例|起算点|候选默认|到期动作|
|---|---|---|---:|---|
|R0-SIGNED/AUDIT|AuditEvent、License/签名验证元数据、Review Decision、StageTransition|记录创建或项目归档|5 年|只允许受控归档/销毁；普通用户永不删除|
|R1-FORMAL-PROJECT|Approved/Superseded 业务版本、Evidence/Trace、正式 Document/Artifact|Project Archived|5 年|满足零保护引用和无 Hold 后受控销毁|
|R2-BUSINESS-DRAFT|未批准 Draft、返回版本、人工待办历史|终态或 Project Archived|2 年|先脱离活动索引，再受控清理|
|R3-AI/RAG-RUN|AI 输入输出、Invocation、RetrievalRun/Context、质量复现引用|Task/Run 终态|180 天|若被正式版本/Review 引用则升级为 R1；否则受控清理正文，保留最小审计摘要|
|R4-JOB/EVENT|Job/Attempt、Delivered Outbox、Parse/Plugin 运行历史|终态/Delivered|180 天|保留聚合统计/Audit；安全清理运行细节|
|R5-RETIRED-INDEX|Retired Index/EmbeddingRecord/旧 Chunk generation|Retired|90 天|零 AI/质量/正式引用且源文档可追溯时清理向量|
|R6-SESSION|过期/撤销 Session 元数据|失效|90 天|删除不透明 Token 摘要记录；安全 Audit 另按 R0|
|R7-TEMP|上传临时文件、Plugin 工作区、未发布输出|创建或 Job 终态|7 天|无活动 Lease/引用后清理|
|R8-FAILED-STAGE|FAILED/STAGED 孤儿 FileObject、失败中间结果|失败确认|24 小时|恢复器预检后隔离清理并 Audit|

补充规则：

- DEAD Outbox、未解决完整性事件、失败安全事件和开放 ActionItem 不按普通期限清理，直到处置完成后再起算。
- Secret 旧密文仅在无任何有效使用、回滚窗口结束、无 Hold 且受权销毁后删除；Secret 元数据与 Audit 按 R0。
- 客户要求立即删除的数据若仍被合同、Review、Audit、Legal Hold 或正式交付保护，系统必须拒绝自动删除并生成受权处置流程。
- Application/Integration Log 不承载业务正文；其轮转期限属于 Release 运维配置，但不能用日志替代上述业务/Audit 数据。

### 物理清理六项前置

任何持久对象物理清理必须全部满足：

1. 生命周期已进入允许清理的终态，且 retention_due_at 已到期。
2. 不存在 Active RetentionHoldEntry。
3. 不被 Approved/Superseded Version、Review、EvidenceBinding、TraceLink、Artifact、Release、Audit 解释链或开放事件引用。
4. 不存在活动 Job/Lease、未完成 Outbox、完整性事件或恢复流程。
5. 清理命令经过规定角色授权、预览影响集、幂等键和 expected policy version。
6. 清理前后均写 Audit；文件销毁验证 Hash/Locator，失败时保持 CLEANUP_PENDING 并可重试。

Package、集合和逻辑目录移除成员不级联删除成员对象。数据库外键的 `ON DELETE CASCADE` 只允许用于明确的同聚合、非历史、非审计子记录；跨聚合和版本历史默认 `RESTRICT/NO ACTION`，最终在 Schema V1 固化。

## 一致性与事务边界

|场景|单事务内容|事务外协调|
|---|---|---|
|单模块命令|Aggregate 变更 + Owner Outbox + Audit 引用|消费者至少一次处理|
|正式版本通过|Owner 更新 approved pointer + Trace/Outbox/Audit|Review Event 重复消费幂等|
|文件提交|FileObject/DocumentVersion/Job/Outbox/Audit 的数据库状态|文件原子提升、恢复器补偿|
|Index 激活|新/旧 Index 活动状态原子切换 + Audit|构建、Embedding、质量检查先完成|
|Output 发布|DocumentVersion + OutputArtifact + Trace/Outbox/Audit|Plugin/转换器先产出暂存结果并校验|
|Plugin/AI 外部调用|Invocation/Execution/Job Attempt 状态|远端/子进程副作用不承诺精确一次|

- 不使用跨模块数据库事务直接写多个 Owner 的表；调用目标 Application Port。
- 不宣称 PostgreSQL、文件系统、外部 AI 和 Plugin 进程之间存在分布式事务。
- 所有跨边界写以 idempotency_key、版本指纹、fencing token、暂存→校验→发布和恢复审计收敛。

## 数据完整性不变量清单

1. 65 个客户 Root 归属 22 个唯一 Owner；无共享写所有权。
2. PROJECT 数据必须有 ProjectId；GLOBAL 数据 ProjectId 为空且需要全局授权。
3. Scope 创建后不可切换；跨项目关系全部失败关闭。
4. User/ProjectMember 满足部署唯一用户名、普通用户单项目/单角色/单部门。
5. ProjectWorkflow 唯一拥有阶段；StageTransition 只追加。
6. Review 绑定逻辑主题，ReviewRound 绑定不可变主题版本；同 Review 最多一个 Active Round。
7. 逻辑对象的 approved pointer 只能指向自己的已通过版本。
8. Version 内容、Evidence 集合和送审指纹不可在 Active Review 中改变。
9. DocumentVersion 与 FileObject Hash/Size/MIME/Scope 一致；路径不暴露。
10. Evidence Locator 可在固定 DocumentVersion 重放；模板不能独立证明客户事实。
11. EvidenceBinding 与 TraceLink 语义分离，历史通过 supersede/revoke 保留。
12. AI Suggestion 永远是 NOT_FORMAL_FACT；人工接受只创建 Domain Draft。
13. 每个 Active EmbeddingIndex 绑定精确 Model/Dimension/ChunkProfile；不兼容变化全量重建。
14. PROJECT Retrieval 的候选、Rerank 和 Context 全链保持同一 ProjectId。
15. AI/Embedding/Reranker 外发载荷必须被本次授权快照覆盖。
16. Job/Outbox 至少一次；可重试写幂等；过期 fencing token 不得发布。
17. Plugin 只运行 VERIFIED 签名包，无数据库/AI Key/License 私钥。
18. OutputArtifact 只有 FileObject/DocumentVersion/Hash/Execution/Request 完整一致后可用。
19. Capability GLOBAL 基线不被项目反写；项目分类与能力匹配绑定精确版本。
20. 实际调研记录优先于 TEMPLATE；面对面录入保留原记录 Evidence 和记录主体。
21. PENDING_CONFIRMATION 不得成为正式 Requirement；NeedConfirm 必须有明确人工输入规格。
22. Requirement→Solution 覆盖快照与 IMPLEMENTS Trace 一致。
23. Prototype/Solution/Plan 对批准需求有覆盖或显式排除/延期/风险接受。
24. WBS 层级 1..6，仅 FS，依赖图无环，日期/工期/负责人/验收完整。
25. Active Hold 或任何保护引用存在时，物理清理失败关闭。

## 模型风险登记

|Risk ID|风险|影响|当前控制|关闭阶段|
|---|---|---|---|---|
|DM-R01|Polymorphic Object/Version Ref 难以使用普通 FK 完整约束|悬空引用、Scope 绕过|唯一 Owner + Port 校验 + stable type discriminator|Schema V1 选择引用表/组合 FK/校验策略|
|DM-R02|ProjectId 在跨模块引用中重复但可能不一致|跨项目泄露|同项目不变量、默认拒绝、复合所有权校验|Schema V1 + 权限集成测试|
|DM-R03|不可变版本与生命周期状态若实现不当会产生“可变版本”|Review/Trace 失真|内容指纹、独立 Review 状态、升版而非覆盖|Schema V1 约束 + API Contract|
|DM-R04|PostgreSQL 与本地文件系统非原子|孤儿文件或缺失正文|STAGED/AVAILABLE、同卷原子提升、恢复矩阵|Schema V1 + 文件集成测试|
|DM-R05|Trace/Requirement/WBS 图约束可能成环|递归、错误计划|受控关系、同 Scope、写入前无环校验|Schema/API + 图属性测试|
|DM-R06|AI/RAG 正文保留与逐次外发授权可能被误复用|数据泄露|授权快照、最小载荷、期限分级、SecretRef|API Contract + Security/UAT|
|DM-R07|Job/Outbox、Audit、Invocation 和向量增长|数据库膨胀/性能下降|分级保留、清理 Job、索引退休、统计摘要|Schema 索引/容量测试 + Release 运维|
|DM-R08|候选默认保留期不等于客户合同/法规要求|过早删除或过度保存|可版本化 RetentionPolicy、Hold 优先、只允许评审后缩短|Gate 2/合同配置/Release|
|DM-R09|JSON/关系表/文件存储边界未物理确定|查询、Migration、完整性成本|按更新频率、查询和约束需要分类|Schema V1 字段映射评审|
|DM-R10|POC-03 分类/引用真实质量未达标|错误建议进入业务|NOT_FORMAL_FACT、Evidence、强制 Review、Gate 3/UAT 阻塞|新独立留出集质量复验|
|DM-R11|Windows 大小写/重解析点与 Debian 权限差异|路径越界/兼容问题|受控 Locator、内部文件名、UTF-8、平台抽象|Release 三平台验证；Debian 仍未验证|
|DM-R12|V1 无普通反归档和在线物理销毁 UI|恢复/处置依赖管理员流程|专用命令要求、Audit、备份与人工恢复|API/UX/Release 决定是否进入 V1|
|DM-R13|GLOBAL→PROJECT 引用在查询图中泄露无权元数据|标准资料或项目存在性泄露|逐节点授权、相同未找到语义、最小 DTO|API Contract + 权限测试|
|DM-R14|旧模型别名或 Provider 管理版本漂移|结果不可完全复现|记录 observed revision、输入/输出指纹、Quality Profile|Provider Adapter + 质量复验|

以上均为已登记的实现/验证风险，不构成 Data Model 内部冲突。任何风险若要求改变 Scope、Owner、正式化链、安全/License 核心机制或新增基础设施，必须走 L3 Change Request。

## Schema V1 交接清单

Database Schema V1 必须逐项给出物理实现和验证证据：

1. 65 个 Root 到表/列/类型的映射，以及 3 个 Developer Workbench Root 的物理隔离说明。
2. Scope/ProjectId 的 CHECK、NOT NULL、复合唯一/外键或等价数据库约束。
3. 逻辑身份、Version、current approved pointer、ReviewSubjectSnapshot 的不可变与一致性约束。
4. ObjectRef/ObjectVersionRef/EvidenceRef/SecretRef 等多态引用的完整性方案。
5. User、Member、Workflow、Review、Secret、License、TrustedTime 的唯一与并发约束。
6. Document/FileObject 状态、Hash、版本号、恢复扫描和受控 Locator 的物理字段。
7. Evidence Locator 各类型的结构化存储、Schema 校验和查询索引。
8. Trace/Requirement/WBS 图边、去重、Scope 和无环校验边界。
9. pgvector 维度、Embedding Index generation、全文检索、metadata filter 和激活索引设计。
10. Job 原子领取、Lease/fencing、幂等、Outbox/Inbox 去重和清理索引。
11. AI/Prompt/Invocation/外发授权快照与受权大文本的存储边界。
12. Plugin/Output/Artifact 与 DocumentVersion 的一致发布约束。
13. RetentionPolicy/Hold、retention_due_at、保护引用预检和清理审计实现。
14. PostgreSQL 18 空库创建、有数据升级、upgrade/downgrade、失败回滚和备份恢复验证计划。
15. 容量与查询计划：Audit、Job、Outbox、AI/RAG、Trace、WBS 和文件元数据的关键索引。

Schema V1 不得通过触发器或跨模块 FK 建立新的共享写所有权；数据库约束用于保护不变量，业务状态迁移仍由 Owner Application Port 执行。

## 未冻结但非阻塞的配置项

以下不是模型分歧，继续进入 Schema/API/Release 细化：

- ID 的 PostgreSQL 物理类型与生成算法。
- Enum 使用 CHECK、lookup table 或受控文本的具体方案。
- 值对象采用列、关系表还是 JSONB；大正文采用数据库还是受控文件引用。
- 分区、归档表、索引、全文检索配置和 pgvector 参数。
- Session/Job/Lease/Chunk/TopK 等运行参数。
- 候选保留期的客户合同覆盖值与受权销毁操作界面。
- 是否在 V1 提供反归档、物理销毁 UI；默认不提供普通业务入口。

## DM-06 验收

- DM-01～DM-05 的详细候选均纳入单一 Data Model Candidate，优先级与边界明确：PASS。
- 22 个客户运行模块、65 个 Aggregate Root、3 个隔离 Developer Workbench Root 覆盖一致：PASS。
- DEPLOYMENT/GLOBAL/PROJECT/GLOBAL_OR_PROJECT/DEVELOPER_WORKBENCH Scope 和跨域规则完整：PASS。
- Platform/Security、Document/Evidence/Trace、AI/RAG/Job/Plugin/Output 与实施业务主链基数完整：PASS。
- 六类生命周期族、正式化链、并发锁定和上游变更传播完整：PASS。
- RetentionPolicy/Hold、九类候选期限、物理清理六项前置和禁止级联边界完整：PASS。
- 25 条核心完整性不变量可追溯到详细模型或架构基线：PASS。
- 14 项模型风险均有当前控制和关闭阶段，无未登记模型分歧：PASS。
- Schema V1 交接清单覆盖 Scope、版本、多态引用、文件、图、向量、Job、保留和 Migration：PASS。
- POC-03、Server Office、Debian 13 等已知失败/未验证项未被改写为通过：PASS。
- 未引入 Redis、消息队列、独立向量库、本地模型、SSO、第三方插件市场或 AI 原型执行沙箱：PASS。
- Gate 2 批准前未定义物理表、列、索引、REST Contract 或生产 Migration，也未提前开始正式业务编码：PASS。

## 下一步

Data Model Candidate V1 已在 Gate 2 冻结。下列 Schema 候选设计 WBS 已全部完成并形成冻结的 DB Schema V1：

1. `SC-01`：65 个 Root 的逻辑到物理映射与命名规范。
2. `SC-02`：主键、Scope/ProjectId、版本、唯一、外键和 CHECK 约束。
3. `SC-03`：pgvector/全文检索、Job/Outbox、Audit/Trace 和关键查询索引。
4. `SC-04`：Retention/Cleanup、文件恢复、Migration 与有数据升级/回退验证。
5. `SC-05`：汇总 `DB-SCHEMA-CANDIDATE-V1`，再进入 API Contract V1。

Architecture、Data Model、Schema 和 API 已一并通过 Gate 2。后续按 Phase 1 WBS 落实模块目录、正式 ORM/Migration、Application Port 和 API 实现；核心模型变化必须走 L3 Data Model Change Request。
