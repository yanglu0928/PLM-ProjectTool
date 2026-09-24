# 实施业务域数据模型 V1 候选

## 状态

`CANDIDATE / DM-05_COMPLETE / NOT_GATE_2_FROZEN / NOT_PHYSICAL_SCHEMA`

本文件细化 Capability、Handover、Survey、Requirement、Prototype、Solution 与 Plan 的业务身份、不可变版本、来源、Review 和 Trace 主链。它不固定 PostgreSQL 表/列、REST URL、页面、工作流配置或客户项目中的具体业务结论。

## 设计结论

1. GLOBAL CapabilityBaseline 是标准能力事实；项目中的“标准功能、非标功能、差异项、待确认项”属于 RequirementVersion 的项目判断，不能反写 GLOBAL 基线。
2. HandoverAnalysis、Survey、Requirement、Prototype、Solution 和 Plan 均采用“逻辑身份 + 不可变 Version”；正式指针只指向通过 Review 的指定版本。
3. 实际调研记录、会议纪要和客户答复优先于调研业务表单。表单是 TEMPLATE，只能提供问题结构，不能独立证明客户现状。
4. AnalysisItem、SurveyConclusion、RequirementVersion 和 SolutionVersion 必须引用可定位 Evidence；待办列表只保存 EvidenceRef，界面通过 Evidence Viewer 打开固定文档版本的页/节/单元格。
5. AI 只创建 Candidate/Suggestion；人工接受后由业务 Owner 创建新的 Domain Draft Version，再经 Review 才能成为正式事实。
6. Requirement、Prototype、Solution、Plan 的关系必须引用不可变 Version Ref；“当前版本”仅用于界面导航，不进入正式 Trace、Review 或输出快照。
7. Review 决定指定版本是否通过，不直接修改业务模块内部状态；业务 Owner 消费 ReviewCompleted 后原子更新正式版本指针、Trace 和 Audit。
8. 项目归档后业务对象只读；任何修订都保留旧版本、旧 Review、EvidenceBinding 和 TraceLink。

## 共同事实层级与正式化规则

### 来源优先级

当来源冲突时，按以下次序判断，但高优先级并不自动覆盖已确认事实：

1. 已生效合同、技术协议及客户明确批准的项目约束。
2. 当前项目实际调研记录、会议纪要、客户原始答复和正式补充材料。
3. 已 Review 的项目结论、需求和方案版本。
4. 已批准 GLOBAL CapabilityBaseline、标准接口、用户手册和部署手册。
5. 历史方案、参考计划和其他 REFERENCE_MATERIAL。
6. 调研表单、文档模板等 TEMPLATE。
7. AI Suggestion。

冲突来源同时保留并建立 `CONTRADICTS` EvidenceBinding；无法消解时创建 NeedConfirm/ActionItem，不允许模板、参考方案或 AI 静默覆盖实际调研记录。

### 共同版本状态

版本内容创建后不可变。业务状态使用以下共同语义，具体模块可取其子集：

```text
DRAFT → IN_REVIEW → APPROVED
   └──────→ RETURNED
APPROVED → SUPERSEDED
任意可读历史版本 → RESTRICTED（安全/合规限制，不删除）
```

- `RETURNED` 后修改必须创建新 Version 和新 ReviewRound。
- `APPROVED` 只表示该版本通过 Review；逻辑对象的 current_approved_version_ref 由 Owner 在消费 ReviewCompleted 时更新。
- `SUPERSEDED` 不撤销历史交付或当时的 Review 结论。
- 版本内容、Evidence 集合和 Trace 输入在送审时形成不可变 ReviewSubjectSnapshot。

### 共同引用合同

|引用|用途|约束|
|---|---|---|
|EvidenceRef|证明原文、原始答复或标准资料位置|绑定固定 DocumentVersion + Locator|
|ObjectVersionRef|跨业务聚合引用指定版本|必须同项目；允许受控 GLOBAL→PROJECT|
|ReviewSubjectRef|审核指定不可变版本|一轮只绑定一个版本|
|TraceLink|来源、细化、实现、验证、生成关系|不复制正文；逐节点授权|
|AITaskRef|保留 AI 建议来源|永远不是正式事实引用|

## Capability：标准能力基线

### CapabilityBaseline Aggregate

|语义字段|要求|
|---|---|
|capability_baseline_id|GLOBAL 逻辑基线身份|
|baseline_code / name|部署内稳定编码和名称|
|baseline_state|`ACTIVE / ARCHIVED / RESTRICTED`|
|current_approved_version_ref|只指向已 Review 的 BaselineVersion|
|source_collection_ref|标准能力库受控来源集合|
|lock_version|乐观并发|

### BaselineVersion Aggregate

|语义字段|要求|
|---|---|
|baseline_version_id / baseline_ref|不可变版本与逻辑基线|
|version_no|基线内单调唯一|
|capability_items|本版本完整能力项集合|
|source_evidence_refs|标准接口、用户/部署手册等 GLOBAL Evidence|
|review_subject_ref|GLOBAL Review 指定版本|
|version_state|共同版本状态|
|supersedes_version_ref|同基线较早版本，可为空|
|created_by / created_at|责任主体与 UTC 时间|

CapabilityItem 是 BaselineVersion 内不可变实体：

|语义字段|要求|
|---|---|
|capability_item_id|跨 BaselineVersion 稳定逻辑身份；升版时显式保留或替代|
|capability_code|基线内唯一编码|
|domain / module / feature|受控分类层级|
|name / description|标准能力说明|
|boundary / prerequisites|适用边界和前置条件|
|interface_refs / document_refs|标准接口和手册版本引用|
|evidence_refs|可定位 GLOBAL Evidence|
|item_state|`AVAILABLE / DEPRECATED / WITHDRAWN`|

- 只有 APPROVED BaselineVersion 能用于正式能力匹配；Draft 可供分析但必须明确标记。
- 项目引用精确 BaselineVersion + CapabilityItem，不引用可变“最新标准能力”。
- 标准资料变化创建新 BaselineVersion；不得批量改写既有项目的历史匹配结论。
- AI 抽取的能力项先进入 Suggestion，必须由有 GLOBAL 权限的人工确认。

## Handover：项目交接分析与待办闭环

### HandoverAnalysis Aggregate

|语义字段|要求|
|---|---|
|handover_analysis_id|PROJECT 逻辑分析身份|
|project_id|必填且不可变|
|analysis_purpose / source_set_ref|分析用途和固定输入版本集合|
|analysis_state|`ACTIVE / ARCHIVED / RESTRICTED`|
|current_approved_version_ref|只指向已 Review/确认的 AnalysisVersion|
|lock_version|乐观并发|

### HandoverAnalysisVersion Aggregate

|语义字段|要求|
|---|---|
|analysis_version_id / analysis_ref|不可变版本与逻辑分析|
|version_no / supersedes_ref|单调版本与替代链|
|source_document_version_refs|合同、技术协议、调研记录等固定版本|
|capability_baseline_version_ref|分析时使用的 GLOBAL 基线版本|
|analysis_items|完整分析项集合|
|version_state / review_subject_ref|共同状态与 Review|
|ai_task_refs|AI 建议来源，可为空|

AnalysisItem 是 Version 内不可变实体：

|语义字段|要求|
|---|---|
|analysis_item_id|版本内稳定标识|
|item_type|`GAP / MISSING / CONFLICT / RISK / SCOPE / NEED_CONFIRM`|
|title / statement|问题与结论陈述|
|impact / severity / priority|影响、严重度和优先级|
|evidence_refs|支持与冲突 Evidence|
|related_capability_item_refs|可为空；精确 BaselineVersion/Item|
|recommendation / options|建议及可选处理方案|
|confirmation_question|需要人工确认时的明确问题|
|required_input_spec|需维护的信息名称、格式、示例和是否必填|
|item_state|`CANDIDATE / CONFIRMED / RESOLVED / ACCEPTED_RISK / REJECTED / SUPERSEDED`|
|resolution_ref|ActionItem、Decision 或后续正式版本引用|

- `NEED_CONFIRM` 必须提供 confirmation_question、impact、options、recommendation 和 required_input_spec，禁止只显示空白输入框。
- 每项至少一个 EvidenceRef，或明确标记“资料缺失”并创建 ActionItem；长段原文不复制到分析表。
- 点击“定位原文”使用 EvidenceRef 打开固定版本位置，不依赖文件路径或当前最新版。
- 只有人工确认项可进入 CONFIRMED/RESOLVED/ACCEPTED_RISK；AI 不能自行关闭问题。

### ActionItem Aggregate

|语义字段|要求|
|---|---|
|action_item_id / project_id|PROJECT 待办身份|
|source_analysis_version_ref / source_item_id|来自已确认分析项，或记录人工创建来源|
|action_type|`PROVIDE_INFO / CONFIRM_DECISION / RESOLVE_CONFLICT / MITIGATE_RISK / DEFINE_SCOPE / OTHER`|
|title / requested_input_spec|清晰动作和维护提示|
|owner_ref / due_at / priority|责任人、期限和优先级|
|action_state|`OPEN / IN_PROGRESS / SUBMITTED / VERIFIED / CLOSED / CANCELLED`|
|response_document_version_refs / evidence_refs|补充材料与定位证据|
|verified_by / verified_at|关闭前验证主体与时间|
|resolution_trace_ref|指向后续 Survey/Requirement/Decision Version|

- SUBMITTED 不等于 CLOSED；关闭必须验证所需信息、Evidence 和后续影响。
- 关闭/取消记录原因且不可删除；重新打开创建新状态事件或替代待办，不覆盖历史。
- Gate 只能消费已 VERIFIED/CLOSED 且满足规则的待办；逾期或阻塞不能被 AI 自动忽略。

## Survey：调研定义、执行与结论

### Survey 与 SurveyVersion

|对象|核心字段|不变量|
|---|---|---|
|Survey|survey_id、project_id、name、survey_state、current_version_ref|逻辑调研身份；正式定义指向指定 SurveyVersion|
|SurveyVersion|version_no、questions、source_refs、target_departments、review_subject_ref、version_state|不可变问题集；来源、顺序、必填和条件逻辑固定|

Question 是 SurveyVersion 内实体：

|语义字段|要求|
|---|---|
|question_id / sequence|版本内唯一和顺序|
|topic / question_text / objective|主题、问题和目的|
|answer_type / validation_rule|文本、单选、多选、日期、数值、附件等语义|
|required / condition|必填和显示条件|
|source_refs|Handover Item、Capability、模板或人工来源|
|expected_output|希望形成的事实/决策|
|evidence_required|回答是否必须附 Evidence|

- 实际调研内容可以来自面对面记录，不要求客户维护模板；系统允许把 PROJECT_RECORD 绑定到 SurveyRound/Question 并由实施人员结构化。
- TEMPLATE 只能生成/提示问题，不自动生成 Answer 或 Conclusion。
- AI 建议的部门、问题和追问必须经项目负责人确认后才进入 SurveyVersion 或新 Round。

### SurveyRound 与 SurveyAssignment

|对象|核心字段|不变量|
|---|---|---|
|SurveyRound|round_id、survey_version_ref、round_no、schedule、round_state、source_record_refs|一轮绑定一个不可变 SurveyVersion；关闭后不接收新提交|
|SurveyAssignment|assignment_id、round_ref、department_ref、assignee_ref、submission_state、responses|同 Round/对象唯一；提交历史保留|

Round 状态：

```text
PLANNED → OPEN → CLOSED
   └────→ CANCELLED
```

Assignment/Response 状态：

```text
ASSIGNED → IN_PROGRESS → SUBMITTED → VALIDATED
                         └──────────→ RETURNED
```

Answer/Response 至少记录 question_ref、原始回答、结构化值、response_source、evidence_refs、submitted_by/at 和 correction_of_ref。面对面记录由受权实施人员录入时必须保留原始 PROJECT_RECORD Evidence 和记录人，不能伪装为客户在线自填。

### SurveyConclusion Aggregate

|语义字段|要求|
|---|---|
|conclusion_series_id / survey_conclusion_id|稳定结论序列与不可变结论版本身份|
|project_id / survey_ref / round_refs|项目、调研和输入轮次|
|conclusion_version_no / supersedes_ref|单调版本与替代链|
|department_conclusions / module_conclusions|分部门与分模块结论|
|evidence_refs / conflict_refs|支持和冲突证据|
|open_issue_refs|未关闭 Handover/Survey 待办|
|conclusion_state / review_subject_ref|共同版本状态与 Review|
|ai_task_refs|AI 总结来源，可为空|

- 结论必须从实际回答/调研记录追溯；模板、空白问题或 AI 总结不能单独成为正式结论。
- 存在冲突或关键缺失时不能 APPROVED，除非形成显式范围排除/风险接受并由 Review 决定。
- Review 通过的 SurveyConclusion 才能作为正式 Requirement 来源。

## Requirement：正式需求与能力匹配

### RequirementPackage 与 Requirement

|对象|核心字段|不变量|
|---|---|---|
|RequirementPackage|package_id、project_id、name、requirement_refs、package_state|只组织同项目 Requirement；移除不删除需求|
|Requirement|requirement_id、project_id、requirement_code、requirement_state、current_approved_version_ref|稳定逻辑身份；正式指针只指向通过 Review 的版本|

Requirement 状态为 `ACTIVE / DEFERRED / REJECTED / ARCHIVED`；DEFERRED/REJECTED 必须保留决策、Evidence 和影响，不能从 Scope 清单静默消失。

### RequirementVersion Aggregate

|语义字段|要求|
|---|---|
|requirement_version_id / requirement_ref|不可变版本与逻辑需求|
|version_no / supersedes_ref|单调版本与替代链|
|title / statement / rationale|需求名称、陈述和业务理由|
|domain / priority / risk|领域、优先级和风险|
|requirement_classification|见受控分类|
|capability_assessments|对固定 BaselineVersion/Item 的匹配判断|
|requirement_sources|SurveyConclusion/Analysis/人工决策/Evidence 引用|
|acceptance_criteria|可验证验收条件集合|
|assumptions / exclusions / dependencies|假设、排除和依赖|
|version_state / review_subject_ref|共同状态与 Review|
|ai_task_refs|候选/改写来源，可为空|

requirement_classification 固定为：

- `STANDARD_FUNCTION`：批准的标准能力可直接满足，通常采用标准配置。
- `NONSTANDARD_FUNCTION`：无直接标准能力，需要扩展、接口、迁移或专用实现。
- `DIFFERENCE`：客户现状/约束与标准能力存在差异，需要适配、治理或流程决策。
- `PENDING_CONFIRMATION`：关键输入或决定未闭合，不能进入正式实施承诺。

CapabilityAssessment 是 Version 内不可变判断：

|语义字段|要求|
|---|---|
|baseline_version_ref / capability_item_ref|精确 GLOBAL 能力版本/项|
|match_type|`DIRECT / PARTIAL / NONE / UNKNOWN`|
|fit_gap / constraints|满足范围、缺口和前置条件|
|evidence_refs|标准与项目双方 Evidence|
|assessment_by / at|人工或 AI Candidate 来源|
|confirmation_state|`CANDIDATE / CONFIRMED / REJECTED`|

- classification 与 match_type 不是 AI 置信度的别名；必须结合项目事实、范围和人工判断。
- STANDARD_FUNCTION 必须至少一个 CONFIRMED DIRECT 匹配；NONSTANDARD/DIFFERENCE 必须说明缺口、解决方向和明确排除。
- PENDING_CONFIRMATION 不得被输出为“已确认需求”，也不得通过填默认值静默转正。
- AcceptanceCriterion 必须具有 criterion_id、可观察结果、验证方式、必要数据/环境和 Evidence 要求；模糊陈述不能作为唯一标准。

### RequirementRelation Aggregate

|语义字段|要求|
|---|---|
|requirement_relation_id|不可变关系身份|
|project_id|两端同项目|
|source_requirement_version_ref / target_requirement_version_ref|固定版本|
|relation_type|`DEPENDS_ON / PARENT_OF / RELATED_TO / DUPLICATES / CONFLICTS_WITH`|
|relation_state / superseded_by_ref|`ACTIVE / SUPERSEDED / REVOKED`|
|created_by / created_at|责任主体与 UTC 时间|

- DEPENDS_ON 与 PARENT_OF 不得自环或形成非法环；DUPLICATES/CONFLICTS_WITH 的方向/对称规范在业务规则中统一。
- 合并/拆分需求创建新 Requirement/Version 与 TraceLink，不覆盖原始候选或已批准需求。

## Prototype：范围、模板与评审制品

### PrototypePackage、Prototype 与 PrototypeVersion

|对象|核心字段|不变量|
|---|---|---|
|PrototypePackage|package_id、project_id、prototype_refs、package_state|只组织同项目 Prototype|
|Prototype|prototype_id、project_id、name、prototype_state、current_approved_version_ref|逻辑原型；可明确 `NOT_REQUIRED` 并记录原因/Review|
|PrototypeVersion|version_no、artifact_refs、interaction_spec、requirement_version_refs、template_version_ref、review_subject_ref、version_state|内容不可变；需求映射与制品版本固定|

Prototype 状态为 `ACTIVE / NOT_REQUIRED / ARCHIVED / RESTRICTED`；NOT_REQUIRED 必须绑定范围决定、理由、受影响 RequirementVersion 和 Review/确认记录。

PrototypeTemplate 可为 GLOBAL 或 PROJECT：

- GLOBAL Template 不含客户数据，项目定制创建 PROJECT TemplateVersion。
- 模板版本、布局/组件合同和适用终端固定；升版不改写已生成 PrototypeVersion。
- AI 生成原型只形成 Draft Artifact/PrototypeVersion，不执行任意代码，不引入 AI 原型执行沙箱。

### RequirementPrototypeLink Aggregate

|语义字段|要求|
|---|---|
|link_id / project_id|不可变同项目关系|
|requirement_version_ref / prototype_version_ref|两端固定版本|
|purpose|`ILLUSTRATES / VALIDATES / ACCEPTANCE_REFERENCE`|
|coverage|覆盖范围和未覆盖项|
|link_state / superseded_by_ref|历史替代|

- 每个进入原型范围的需求必须有覆盖或显式缺口；未做原型的需求保留 NOT_REQUIRED 决策，不能因无链接而消失。
- Prototype Review 只确认指定制品版本，不等于 Requirement 或 Solution 自动通过。

## Solution：参考方案、结构与正式章节

### ReferenceSolution

|语义字段|要求|
|---|---|
|reference_solution_id|GLOBAL 或 PROJECT 参考身份|
|reference_version / document_version_refs|固定参考材料版本|
|applicability / source_project_class|适用范围与脱敏分类|
|eligibility_state|`REFERENCE_ONLY / ELIGIBLE / RESTRICTED / REVOKED`|
|evidence_refs|可定位来源|

参考方案不能自动成为项目 Solution，不能覆盖实际项目事实；其内容通过 REFERENCE_ONLY Evidence/Trace 使用。

### SolutionOutline 与 SolutionOutlineVersion

|对象|核心字段|不变量|
|---|---|---|
|SolutionOutline|outline_id、project_id、name、current_approved_version_ref|逻辑目录|
|SolutionOutlineVersion|version_no、ordered_section_refs、requirement_version_refs、reference_solution_refs、review_subject_ref、version_state|章节顺序、输入需求和参考版本固定|

- AI 融合目录先形成 Draft；冲突、缺章和来源不明必须显式标记。
- Outline 通过不代表所有 Section 正文已通过；正式输出必须固定 OutlineVersion 与各 SectionVersion。

### SolutionSection 与 SolutionSectionVersion

|对象|核心字段|不变量|
|---|---|---|
|SolutionSection|section_id、project_id、outline_ref、section_key、current_approved_version_ref|逻辑章节；key 在 Outline 内唯一|
|SolutionSectionVersion|version_no、title、content_ref、requirement_version_refs、evidence_refs、structured_spec_refs、review_subject_ref、version_state|正文、映射、证据和专项设计固定|

- 每个已批准 RequirementVersion 必须被至少一个 SolutionSectionVersion 覆盖，或具有显式排除/延期决定。
- AI 章节固定为 DRAFT，直到 Evidence、Requirement 映射和 Review 完成。
- 章节正文只保存受控内容引用；大文件/图表作为 DocumentVersion/Artifact，不塞入关系记录。

### StructuredSolutionSpec Aggregate

|语义字段|要求|
|---|---|
|structured_spec_id / project_id|专项设计身份|
|spec_type|`PROCESS_MODEL / INTERFACE_SPEC / MIGRATION_SPEC / PERMISSION_DESIGN`|
|spec_version / supersedes_ref|不可变版本与替代链|
|solution_section_version_refs|所属正式/草案章节版本|
|requirement_version_refs|覆盖的需求版本|
|structured_payload_ref / diagram_artifact_refs|结构化内容与图形制品|
|evidence_refs / assumptions / exclusions|来源与边界|
|version_state / review_subject_ref|共同状态与 Review|

专项最小约束：

- PROCESS_MODEL：Node/Edge 唯一、起止明确、无悬空边，角色/输入/输出可追溯。
- INTERFACE_SPEC：系统边界、方向、数据所有权、频率、错误/重试、鉴权和字段映射明确。
- MIGRATION_SPEC：来源、范围、清洗/映射、试迁移、对账、回退和验收明确。
- PERMISSION_DESIGN：角色、资源、动作、范围、默认拒绝和职责分离明确。

### Requirement → Solution 映射

不新增可变“RequirementSolution”双写表。以以下组合表达：

- SolutionSectionVersion.requirement_version_refs：章节内部覆盖快照。
- TraceLink `IMPLEMENTS`：RequirementVersion → SolutionSectionVersion/StructuredSolutionSpec。
- EvidenceBinding：证明方案判断的来源原文。

二者必须在送审前一致；不一致时失败关闭。

## Plan：参考计划与实施 WBS

### ReferencePlan

|语义字段|要求|
|---|---|
|reference_plan_id|GLOBAL 或 PROJECT 参考身份|
|reference_plan_version / source_document_refs|固定 Excel/CSV/文档版本|
|mapping_profile / parse_summary|字段映射和解析结果|
|eligibility_state|`REFERENCE_ONLY / ELIGIBLE / RESTRICTED / REVOKED`|

参考计划只提供模板/经验，不自动成为当前项目承诺；导入错误、缺字段或超出规则时不得进入正式 PlanVersion。

### Plan 与 PlanVersion

|对象|核心字段|不变量|
|---|---|---|
|Plan|plan_id、project_id、name、plan_state、current_approved_version_ref|逻辑计划；正式指针只指向已 Review 版本|
|PlanVersion|version_no、solution_version_refs、wbs_items、dependencies、milestones、calendar_ref、review_subject_ref、version_state|计划快照不可变；输入方案版本固定|

WbsItem 是 PlanVersion 内实体：

|语义字段|要求|
|---|---|
|wbs_item_id / parent_item_id|版本内唯一；根节点 parent 为空|
|wbs_code / name / level|编码、名称、层级 1..6|
|task_type / category|项目控制、需求交付、专项设计等受控分类|
|owner_ref / support_role_refs|责任人与协作角色|
|planned_start / planned_finish / duration|计划时间|
|actual_start / actual_finish|快照中的实际时间，可为空|
|item_state|`NOT_STARTED / IN_PROGRESS / BLOCKED / COMPLETED / CANCELLED`|
|entry_conditions / acceptance_criteria|进入条件和验收|
|requirement/solution/prototype refs|固定业务版本映射|
|evidence_refs / output_refs|完成证据和交付物|
|risk / explicit_exclusion|风险和排除|

WbsDependency：

|语义字段|要求|
|---|---|
|dependency_id|版本内唯一|
|predecessor_item_id / successor_item_id|同一 PlanVersion WBS Item|
|dependency_type|V1 仅 `FS`|
|lag|默认 0；非零必须显式单位和理由|

- WBS 层级不得超过 6；parent 必须存在且 level=parent+1。
- FS 图不得自环或成环；Milestone 不允许负 duration，日期/工期和依赖必须一致。
- 每个实施范围内的 Requirement/Solution 必须映射到 WBS Item 或显式排除/延期。
- AI 生成 WBS 只形成 Draft PlanVersion；负责人、日期、依赖、验收和 Gate 经人工确认后送审。
- 实际进度更新创建新 PlanVersion/受控进度快照，不改写已批准基线；基线与当前预测必须可比较。

Milestone 至少包含 milestone_id、name、target_date、linked_item_refs、gate_ref、acceptance_rule 和 milestone_state。Gate 只消费固定 PlanVersion 和已授权 Evidence/Review 状态。

## 端到端主链与 Trace

```text
Approved CapabilityBaselineVersion (GLOBAL)
  + Contract / Technical Agreement / PROJECT_RECORD Evidence
      ↓ REFERENCES_CAPABILITY / DERIVED_FROM
HandoverAnalysisVersion + verified ActionItems
      ↓ DERIVED_FROM
SurveyVersion → SurveyRound/Response → Approved SurveyConclusion
      ↓ DERIVED_FROM
Approved RequirementVersion
      ├─→ PrototypeVersion          (ILLUSTRATES / VALIDATES)
      └─→ SolutionSectionVersion    (IMPLEMENTS)
                    ↓ REFINES / IMPLEMENTS
             StructuredSolutionSpec
                    ↓ DERIVED_FROM
             Approved PlanVersion / WBS
                    ↓ GENERATED_FROM
             OutputArtifact / Delivery
```

### 每一阶段的最小进入条件

|阶段|正式输入|阻塞条件|
|---|---|---|
|Handover|固定项目资料 + Approved CapabilityBaselineVersion|来源无法访问、关键材料缺失未登记|
|Survey|Approved/Confirmed Handover Version + ActionItem 状态|关键 NeedConfirm 未处理且无风险接受|
|Requirement|Approved SurveyConclusion/人工正式来源|Evidence 缺失、PENDING_CONFIRMATION、冲突未处理|
|Prototype|Approved RequirementVersion + 范围决定|输入版本未批准或模板/制品越权|
|Solution|Approved RequirementVersion；必要时 Approved PrototypeVersion|需求覆盖缺口、专项设计缺关键字段|
|Plan|Approved Solution Outline/Section/Spec Version 集合|范围未覆盖、WBS 超 6 级、FS 成环|
|Output|固定 Approved Version 集合|动态当前版本、Review 未通过、Artifact 校验失败|

阶段可以并行准备 Draft，但不能把后续 Draft 描述为基于未批准输入的正式结论。

## Review、并发与变更传播

- 送审前 Owner 计算 content_fingerprint、Evidence set、Trace input set；ReviewRound 绑定该快照。
- Active ReviewRound 期间该 Version 不可替换内容；逻辑对象可创建另一 Draft，但不能篡改在审版本。
- Review 退回后产生新版本；旧版本和意见保留。
- 上游 Approved Version 被新版本替代时，下游不会自动改写。系统标记 `UPSTREAM_CHANGED`，创建影响分析待办，由 Owner 决定保持、升版或重新 Review。
- 乐观并发使用 expected_version/lock_version；冲突返回当前引用和安全差异摘要，不静默 last-write-wins。
- 正式版本指针、TraceLink、Workflow/Gate 状态和 Audit 在单一 Owner 命令/短事务中一致提交；跨模块通过 Application Port + Outbox 至少一次传播。

## 删除、归档与保留

- 逻辑对象默认归档，不物理删除已被 Version、Review、Evidence、Trace、Output、Plan 或 Audit 引用的记录。
- Draft 若从未送审、无下游引用且策略允许，可受控撤销；撤销仍保留最小 Audit，不允许复用标识冒充旧版本。
- Project Archived 后 Capability GLOBAL 数据不受影响，项目业务对象只读；恢复项目不自动恢复已撤销/过期外发授权或 Review。
- CapabilityItem WITHDRAWN、Requirement REJECTED、Prototype NOT_REQUIRED、Solution/Plan SUPERSEDED 都保留历史原因与影响。
- 正式保留期限、Legal Hold 和受控物理销毁在 DM-06/Release 冻结。

## 失败关闭规则

- PROJECT 对象缺失/越权 ProjectId、跨项目引用，或 GLOBAL 对象被项目反写。
- 使用可变“当前版本”代替 Review/Trace/输出中的固定 Version Ref。
- 模板、参考方案、AI Suggestion 被当作客户事实；实际调研记录的冲突被静默过滤。
- NeedConfirm 没有问题、影响、建议、可选方案或人工填写提示；待办关闭但无验证 Evidence。
- Requirement 分类无 Capability/Evidence 依据，PENDING_CONFIRMATION 被当作正式需求，AcceptanceCriterion 不可验证。
- Requirement/Prototype/Solution/Plan 覆盖缺口无显式排除、延期或风险接受。
- Solution 章节与 Trace 实现关系不一致；专项流程、接口、迁移或权限结构无效。
- WBS 超 6 级、FS 自环/成环、日期/工期非法、负责人/验收缺失或基于未批准方案。
- Review 版本与实际内容指纹不一致、Active Review 内容被替换，或上游变化后下游自动改写。

失败只返回安全错误码、对象/版本引用、trace_id 和可操作提示；不返回无权项目名称、客户正文、本地路径、AI 内部响应或数据库细节。

## 延后事项

- 表拆分、字段类型、唯一/外键/检查约束、搜索索引和 Alembic：Schema V1。
- CRUD、Review、影响分析、Evidence Viewer、WBS 和输出 REST DTO：API Contract V1。
- 完整行业枚举、问题类型、需求领域、WBS 类别和专项字段字典：业务规则/配置基线。
- 页面交互、待办按钮、Evidence 高亮和人工输入控件：UX/UI 设计；本模型只固定所需数据语义。
- POC-03 分类/引用质量失败：Gate 3/UAT 持续阻塞，不因 DM-05 模型通过而关闭。
- 现有 R1～R9 分析/交付文件仍是历史验证制品，不自动导入正式数据库或成为已批准客户事实。

## 与上游一致性

- 沿用 DM-01 的 65 个客户运行 Aggregate Root 与 22 个唯一 Owner，不新增跨模块共享所有权。
- 沿用 DM-02 ReviewRound 绑定不可变主题版本、Workflow 唯一拥有阶段状态。
- 沿用 DM-03 Evidence Viewer 固定版本定位、实际调研记录优先于 TEMPLATE、EvidenceBinding 与 TraceLink 分离。
- 沿用 DM-04 AI Suggestion、逐次外发授权、RAG Project 隔离、Job/Outbox 至少一次和 OutputArtifact 发布门槛。
- 保持模块化单体和 Gate 2：本文件不是物理 Schema、API Contract 或正式业务编码授权。

## DM-05 验收

- CapabilityBaseline/BaselineVersion/CapabilityItem 的 GLOBAL、Review、版本引用和项目只读边界完整：PASS。
- Handover Analysis 六类问题、Evidence 定位、人工输入提示和 ActionItem 验证关闭完整：PASS。
- Survey 定义、Round、Assignment/Response、面对面记录优先和 Conclusion 正式化完整：PASS。
- Requirement 逻辑身份/不可变版本、四类项目判断、能力匹配、来源、验收和关系完整：PASS。
- Prototype 范围决定、Template 版本、Artifact、需求覆盖和独立 Review 完整：PASS。
- Solution 参考/目录/章节/专项设计、需求覆盖和 Trace 一致性完整：PASS。
- Plan/ReferencePlan、六级 WBS、FS DAG、负责人、里程碑、基线与进度升版完整：PASS。
- Capability→Handover→Survey→Requirement→Prototype/Solution→Plan→Output 主链和 Gate 进入条件完整：PASS。
- Review 锁定、乐观并发、上游变更影响分析、归档与历史保留完整：PASS。
- AI/模板/参考资料不自动成为事实，R1～R9 历史成果不自动正式化：PASS。
- 65 个 Aggregate Root、22 个唯一 Owner 和既有 Scope 回归保持一致：PASS。
- 未定义物理 Schema/API/Migration，未提前进入正式业务编码：PASS。

## 下一步

DM-06：汇总 Data Model Candidate，统一关系、基数、生命周期、删除/保留策略和风险清单；完成后进入 Database Schema V1 候选设计。
