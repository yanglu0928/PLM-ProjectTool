# API-04：实施业务主链 Contract V1 候选

## 状态

`CANDIDATE / API-04_COMPLETE / API-05_NEXT / NOT_GATE_2_FROZEN / NO_FASTAPI_IMPLEMENTATION / NO_EXTERNAL_CALLS`

本文件在 API-01 公共协议、API-02 Review/Evidence/Trace 能力和 API-03 AI/Job/Output 能力之上，定义 Capability、Handover、Survey、Requirement、Prototype、Solution 与 Plan 的 `/api/v1` 资源、不可变版本、状态命令、权限、错误、Audit 和 Contract 测试。它不创建 FastAPI、Pydantic、ORM、Migration、前端页面或客户项目中的正式业务事实。

## 范围与 Root 覆盖

|Owner|Root IDs|数量|API 边界|
|---|---|---:|---|
|capability|CAP-01、CAP-02|2|GLOBAL 标准能力逻辑身份、不可变版本与能力项|
|handover|HND-01、HND-02、HND-03|3|项目交接分析版本、证据定位与待办闭环|
|survey|SRV-01、SRV-02、SRV-03、SRV-04、SRV-05|5|调研定义、执行轮次、答复历史和结论版本|
|requirement|REQ-01、REQ-02、REQ-03、REQ-04|4|需求包、需求版本、能力匹配、验收和关系|
|prototype|PRT-01、PRT-02、PRT-03、PRT-04、PRT-05|5|原型包、版本、模板与需求覆盖|
|solution|SOL-01、SOL-02、SOL-03、SOL-04、SOL-05、SOL-06|6|参考方案、目录、章节和结构化专项设计|
|plan|PLN-01、PLN-02、PLN-03|3|参考计划、实施计划版本、WBS、依赖和里程碑|

合计 7 个 Owner、28 个 Root。Version 内容、ReviewSubjectSnapshot、Response 历史、关系历史和正式指针历史不得通过通用 PATCH/DELETE 覆盖；所有正式关系引用固定 VersionRef，不接受 `latest/current` 动态引用。

## 控制标记与共同业务协议

|标记|含义|
|---|---|
|`S`|有效 Server Session|
|`L`|有效 License|
|`C`|状态改变请求必须通过 CSRF|
|`I`|必须提供 `Idempotency-Key`|
|`M`|必须提供 `If-Match`|
|`A`|必须写 Audit|

所有 PROJECT 操作另行强制 ProjectId、成员状态、Role、资源归属、引用两端归属和对象状态检查；表中不重复写 Project 控制。GLOBAL 写操作仅允许具备明确权限的 DeploymentAdmin，项目成员只能读取被当前项目正式引用且策略允许的 GLOBAL 版本。

### 不可变版本与 Review 编排

- Identity 的名称、描述等受控元数据可 PATCH；版本正文、Evidence 集、Trace 输入和 Review 快照创建后不可 PATCH。
- `.../versions` 创建新 Draft 时必须给出 `base_version_ref` 或显式 `initial=true`；基于 Returned/Approved 版本修订产生新的 `version_id/version_no`。
- `:submit-review` 是业务 Owner 的原子编排命令：先完成来源、Evidence、覆盖、指纹和状态校验，再通过 ReviewService 创建/启动绑定固定版本的 ReviewRound。它不绕过 API-02 Review 权限与决策规则。
- ReviewCompleted 后，业务 Owner 在短事务内把指定版本标记为 APPROVED、更新 identity 的 `current_approved_version_ref`、生成 Trace/Audit/Outbox；ReviewService 不直接写业务表。
- ReviewReturned 后原版本保持 RETURNED；修改必须新建版本和 ReviewRound。Active Review 期间版本内容和 owned child 只读。
- 上游批准版本被替代不会自动改写下游；系统产生 `UPSTREAM_CHANGED` 影响项，用户选择保持、升版或重新送审。

### AI、Evidence、Trace 与参考资料

- AI 工作仍通过 API-03 `AI_TASK_CREATE`；接受 Suggestion 只能调用白名单目标 Owner Port 并创建 Draft，返回值继续标记来源 `NOT_FORMAL_FACT`。
- Handover、SurveyConclusion、Requirement、Solution 和 Plan 的正式版本必须使用 API-02 EvidenceRef/TraceLink；列表不得复制大段原文，定位按钮使用受权 Evidence Viewer。
- 实际客户调研记录、会议纪要和原始答复优先于 TEMPLATE。模板只能提供问题结构，不得自动生成 Answer、Conclusion 或客户事实。
- ReferenceSolution、ReferencePlan 和历史制品只保持 `REFERENCE_ONLY/ELIGIBLE` 参考身份，不因导入或 AI 使用自动成为当前项目承诺。
- 跨项目引用一律拒绝；受控 GLOBAL→PROJECT 引用必须固定 GLOBAL version/item，并按节点重新授权。

## Capability：GLOBAL 标准能力

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|CAP_BASELINE_LIST|GET `/api/v1/global/capability-baselines`|DeploymentAdmin；受权项目成员只读|S,L|Baseline page|
|CAP_BASELINE_CREATE|POST `/api/v1/global/capability-baselines`|DeploymentAdmin|S,L,C,I,A|201 Baseline identity + ETag|
|CAP_BASELINE_GET|GET `/api/v1/global/capability-baselines/{baseline_id}`|受权主体|S,L|BaselineView + ETag|
|CAP_BASELINE_PATCH|PATCH `/api/v1/global/capability-baselines/{baseline_id}`|DeploymentAdmin|S,L,C,M,A|200 metadata + ETag|
|CAP_BASELINE_ARCHIVE|POST `/api/v1/global/capability-baselines/{baseline_id}:archive`|DeploymentAdmin|S,L,C,I,M,A|200 ARCHIVED；不撤销历史引用|
|CAP_VERSION_LIST|GET `/api/v1/global/capability-baselines/{baseline_id}/versions`|受权主体|S,L|immutable version page|
|CAP_VERSION_CREATE|POST `/api/v1/global/capability-baselines/{baseline_id}/versions`|DeploymentAdmin|S,L,C,I,M,A|201 DRAFT BaselineVersion|
|CAP_VERSION_GET|GET `/api/v1/global/capability-baselines/{baseline_id}/versions/{baseline_version_id}`|受权主体|S,L|固定 Version + source refs|
|CAP_VERSION_ITEM_LIST|GET `/api/v1/global/capability-baselines/{baseline_id}/versions/{baseline_version_id}/items`|受权主体|S,L|CapabilityItem page|
|CAP_VERSION_VALIDATE|POST `/api/v1/global/capability-baselines/{baseline_id}/versions/{baseline_version_id}:validate`|DeploymentAdmin|S,L,C,I,A|200 validation report；不改变正式状态|
|CAP_VERSION_SUBMIT_REVIEW|POST `/api/v1/global/capability-baselines/{baseline_id}/versions/{baseline_version_id}:submit-review`|DeploymentAdmin|S,L,C,I,A|201 ReviewRef + RoundRef|
|CAP_VERSION_RESTRICT|POST `/api/v1/global/capability-baselines/{baseline_id}/versions/{baseline_version_id}:restrict`|DeploymentAdmin|S,L,C,I,A|200 RESTRICTED + reason|

- 只有 APPROVED BaselineVersion 可用于正式能力匹配；项目引用固定 `baseline_version_id + capability_item_id`。
- `CapabilityItemInput` 必须包含稳定 item id/code、分类、边界、前置条件和至少一个合格 GLOBAL EvidenceRef；WITHDRAWN item 保留历史。
- AI 抽取能力项只能先创建 Suggestion 或 Draft；不能自动通过 Review、激活基线或改写既有项目结论。

## Handover：交接分析与 ActionItem

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|HND_ANALYSIS_LIST|GET `/api/v1/projects/{project_id}/handover-analyses`|Project member|S,L|Analysis page|
|HND_ANALYSIS_CREATE|POST `/api/v1/projects/{project_id}/handover-analyses`|ProjectManager、ImplementationMember|S,L,C,I,A|201 Analysis identity + ETag|
|HND_ANALYSIS_GET|GET `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}`|Project member|S,L|AnalysisView + ETag|
|HND_ANALYSIS_PATCH|PATCH `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}`|ProjectManager、ImplementationMember|S,L,C,M,A|200 metadata + ETag|
|HND_ANALYSIS_ARCHIVE|POST `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}:archive`|ProjectManager|S,L,C,I,M,A|200 ARCHIVED|
|HND_VERSION_LIST|GET `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions`|Project member|S,L|immutable version page|
|HND_VERSION_CREATE|POST `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions`|ProjectManager、ImplementationMember|S,L,C,I,M,A|201 DRAFT AnalysisVersion|
|HND_VERSION_GET|GET `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions/{analysis_version_id}`|Project member|S,L|固定 sources/items/capability baseline|
|HND_VERSION_ITEM_LIST|GET `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions/{analysis_version_id}/items`|Project member|S,L|AnalysisItem page + EvidenceRef|
|HND_VERSION_VALIDATE|POST `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions/{analysis_version_id}:validate`|ProjectManager、ImplementationMember|S,L,C,I,A|200 source/issue/completeness report|
|HND_VERSION_SUBMIT_REVIEW|POST `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions/{analysis_version_id}:submit-review`|ProjectManager|S,L,C,I,A|201 ReviewRef + RoundRef|
|HND_ACTION_LIST|GET `/api/v1/projects/{project_id}/handover-action-items`|Project member|S,L|ActionItem page|
|HND_ACTION_CREATE|POST `/api/v1/projects/{project_id}/handover-action-items`|ProjectManager、ImplementationMember|S,L,C,I,A|201 OPEN ActionItem + ETag|
|HND_ACTION_GET|GET `/api/v1/projects/{project_id}/handover-action-items/{action_item_id}`|Project member|S,L|ActionItemView + ETag|
|HND_ACTION_PATCH|PATCH `/api/v1/projects/{project_id}/handover-action-items/{action_item_id}`|ProjectManager、ImplementationMember、assigned owner|S,L,C,M,A|200 allowed metadata + ETag|
|HND_ACTION_START|POST `/api/v1/projects/{project_id}/handover-action-items/{action_item_id}:start`|assigned owner、ProjectManager|S,L,C,I,M,A|200 IN_PROGRESS|
|HND_ACTION_SUBMIT|POST `/api/v1/projects/{project_id}/handover-action-items/{action_item_id}:submit`|assigned owner、ImplementationMember|S,L,C,I,M,A|200 SUBMITTED + response refs|
|HND_ACTION_VERIFY|POST `/api/v1/projects/{project_id}/handover-action-items/{action_item_id}:verify`|ProjectManager、受权 CustomerManager|S,L,C,I,M,A|200 VERIFIED|
|HND_ACTION_CLOSE|POST `/api/v1/projects/{project_id}/handover-action-items/{action_item_id}:close`|ProjectManager|S,L,C,I,M,A|200 CLOSED + resolution trace|
|HND_ACTION_CANCEL|POST `/api/v1/projects/{project_id}/handover-action-items/{action_item_id}:cancel`|ProjectManager|S,L,C,I,M,A|200 CANCELLED + reason|

- AnalysisItem 类型固定为 GAP/MISSING/CONFLICT/RISK/SCOPE/NEED_CONFIRM；NEED_CONFIRM 必须含明确问题、影响、选项、建议和人工输入规格。
- 每项至少一个 EvidenceRef；资料缺失使用显式 flag 并创建 ActionItem，不能用空白输入框代替提示。
- AI 不能把 Item 标成 CONFIRMED/RESOLVED，也不能创建正式 ActionItem。ActionItem 的人工创建来源必须保存 actor/reason。
- SUBMITTED 不等于 CLOSED；VERIFY 校验 requested input、Evidence 和后续影响，CLOSE 必须引用验证结果与 resolution trace。

## Survey：定义、执行、答复与结论

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|SURVEY_LIST|GET `/api/v1/projects/{project_id}/surveys`|Project member|S,L|Survey page|
|SURVEY_CREATE|POST `/api/v1/projects/{project_id}/surveys`|ProjectManager、ImplementationMember|S,L,C,I,A|201 Survey identity + ETag|
|SURVEY_GET|GET `/api/v1/projects/{project_id}/surveys/{survey_id}`|Project member|S,L|SurveyView + ETag|
|SURVEY_PATCH|PATCH `/api/v1/projects/{project_id}/surveys/{survey_id}`|ProjectManager、ImplementationMember|S,L,C,M,A|200 metadata + ETag|
|SURVEY_ARCHIVE|POST `/api/v1/projects/{project_id}/surveys/{survey_id}:archive`|ProjectManager|S,L,C,I,M,A|200 ARCHIVED|
|SURVEY_VERSION_LIST|GET `/api/v1/projects/{project_id}/surveys/{survey_id}/versions`|Project member|S,L|immutable definition page|
|SURVEY_VERSION_CREATE|POST `/api/v1/projects/{project_id}/surveys/{survey_id}/versions`|ProjectManager、ImplementationMember|S,L,C,I,M,A|201 DRAFT SurveyVersion|
|SURVEY_VERSION_GET|GET `/api/v1/projects/{project_id}/surveys/{survey_id}/versions/{survey_version_id}`|Project member|S,L|固定 questions/source/department refs|
|SURVEY_VERSION_VALIDATE|POST `/api/v1/projects/{project_id}/surveys/{survey_id}/versions/{survey_version_id}:validate`|ProjectManager、ImplementationMember|S,L,C,I,A|200 question/condition/source report|
|SURVEY_VERSION_SUBMIT_REVIEW|POST `/api/v1/projects/{project_id}/surveys/{survey_id}/versions/{survey_version_id}:submit-review`|ProjectManager|S,L,C,I,A|201 ReviewRef + RoundRef|
|SURVEY_ROUND_LIST|GET `/api/v1/projects/{project_id}/survey-rounds`|Project member|S,L|Round page|
|SURVEY_ROUND_CREATE|POST `/api/v1/projects/{project_id}/survey-rounds`|ProjectManager、ImplementationMember|S,L,C,I,A|201 PLANNED Round + ETag|
|SURVEY_ROUND_GET|GET `/api/v1/projects/{project_id}/survey-rounds/{round_id}`|Project member|S,L|RoundView + ETag|
|SURVEY_ROUND_PATCH|PATCH `/api/v1/projects/{project_id}/survey-rounds/{round_id}`|ProjectManager、ImplementationMember|S,L,C,M,A|200 PLANNED schedule metadata|
|SURVEY_ROUND_OPEN|POST `/api/v1/projects/{project_id}/survey-rounds/{round_id}:open`|ProjectManager|S,L,C,I,M,A|200 OPEN|
|SURVEY_ROUND_CLOSE|POST `/api/v1/projects/{project_id}/survey-rounds/{round_id}:close`|ProjectManager|S,L,C,I,M,A|200 CLOSED + completeness report|
|SURVEY_ROUND_CANCEL|POST `/api/v1/projects/{project_id}/survey-rounds/{round_id}:cancel`|ProjectManager|S,L,C,I,M,A|200 CANCELLED + reason|
|SURVEY_ASSIGNMENT_LIST|GET `/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments`|受权 Project member|S,L|Assignment page|
|SURVEY_ASSIGNMENT_CREATE|POST `/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments`|ProjectManager、ImplementationMember|S,L,C,I,M,A|201 ASSIGNED + ETag|
|SURVEY_ASSIGNMENT_GET|GET `/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{assignment_id}`|assignee、项目管理角色|S,L|Assignment/response projection + ETag|
|SURVEY_RESPONSE_RECORD|POST `/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{assignment_id}/responses`|assignee、受权 ImplementationMember|S,L,C,I,M,A|201 append-only Response/CorrectionRef|
|SURVEY_ASSIGNMENT_SUBMIT|POST `/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{assignment_id}:submit`|assignee、受权录入人|S,L,C,I,M,A|200 SUBMITTED|
|SURVEY_ASSIGNMENT_VALIDATE|POST `/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{assignment_id}:validate`|ProjectManager、ImplementationMember|S,L,C,I,M,A|200 VALIDATED|
|SURVEY_ASSIGNMENT_RETURN|POST `/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{assignment_id}:return`|ProjectManager、ImplementationMember|S,L,C,I,M,A|200 RETURNED + comment|
|SURVEY_CONCLUSION_LIST|GET `/api/v1/projects/{project_id}/survey-conclusions`|Project member|S,L|Conclusion version page|
|SURVEY_CONCLUSION_CREATE|POST `/api/v1/projects/{project_id}/survey-conclusions`|ProjectManager、ImplementationMember|S,L,C,I,A|201 DRAFT ConclusionVersion|
|SURVEY_CONCLUSION_GET|GET `/api/v1/projects/{project_id}/survey-conclusions/{conclusion_id}`|Project member|S,L|固定 round/evidence/open issue refs|
|SURVEY_CONCLUSION_VALIDATE|POST `/api/v1/projects/{project_id}/survey-conclusions/{conclusion_id}:validate`|ProjectManager、ImplementationMember|S,L,C,I,A|200 source/conflict/completeness report|
|SURVEY_CONCLUSION_SUBMIT_REVIEW|POST `/api/v1/projects/{project_id}/survey-conclusions/{conclusion_id}:submit-review`|ProjectManager|S,L,C,I,A|201 ReviewRef + RoundRef|

- Round 只能绑定 APPROVED SurveyVersion；CLOSED 后拒绝新 Response。问题条件、必填和 ValidationRule 按固定版本计算。
- 面对面记录由受权 ImplementationMember 录入时，`response_source=FACILITATED_RECORD`，并强制保存记录人和原始 PROJECT_RECORD Evidence；不能伪装为客户自填。
- 每次更正追加 `correction_of_ref`，不覆盖原答复。TEMPLATE 不能作为回答来源，也不能单独满足 EvidenceRequired。
- Conclusion 只可引用 VALIDATED Response/合格 PROJECT_RECORD；存在关键冲突或缺失时失败关闭，除非固定版本中有显式范围排除或受权风险接受。

## Requirement：需求、能力判断与关系

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|REQ_PACKAGE_LIST|GET `/api/v1/projects/{project_id}/requirement-packages`|Project member|S,L|Package page|
|REQ_PACKAGE_CREATE|POST `/api/v1/projects/{project_id}/requirement-packages`|ProjectManager、ImplementationMember|S,L,C,I,A|201 Package + ETag|
|REQ_PACKAGE_GET|GET `/api/v1/projects/{project_id}/requirement-packages/{package_id}`|Project member|S,L|PackageView + ETag|
|REQ_PACKAGE_PATCH|PATCH `/api/v1/projects/{project_id}/requirement-packages/{package_id}`|ProjectManager、ImplementationMember|S,L,C,M,A|200 metadata + ETag|
|REQ_PACKAGE_ADD|POST `/api/v1/projects/{project_id}/requirement-packages/{package_id}:add-requirements`|ProjectManager、ImplementationMember|S,L,C,I,M,A|200 member refs + ETag|
|REQ_PACKAGE_REMOVE|POST `/api/v1/projects/{project_id}/requirement-packages/{package_id}:remove-requirements`|ProjectManager、ImplementationMember|S,L,C,I,M,A|200 member refs；不删除 Requirement|
|REQ_LIST|GET `/api/v1/projects/{project_id}/requirements`|Project member|S,L|Requirement page|
|REQ_CREATE|POST `/api/v1/projects/{project_id}/requirements`|ProjectManager、ImplementationMember|S,L,C,I,A|201 Requirement identity + ETag|
|REQ_GET|GET `/api/v1/projects/{project_id}/requirements/{requirement_id}`|Project member|S,L|RequirementView + ETag|
|REQ_PATCH|PATCH `/api/v1/projects/{project_id}/requirements/{requirement_id}`|ProjectManager、ImplementationMember|S,L,C,M,A|200 metadata + ETag|
|REQ_DEFER|POST `/api/v1/projects/{project_id}/requirements/{requirement_id}:defer`|ProjectManager、CustomerManager|S,L,C,I,M,A|200 DEFERRED + decision refs|
|REQ_REJECT|POST `/api/v1/projects/{project_id}/requirements/{requirement_id}:reject`|ProjectManager、CustomerManager|S,L,C,I,M,A|200 REJECTED + decision refs|
|REQ_ARCHIVE|POST `/api/v1/projects/{project_id}/requirements/{requirement_id}:archive`|ProjectManager|S,L,C,I,M,A|200 ARCHIVED|
|REQ_VERSION_LIST|GET `/api/v1/projects/{project_id}/requirements/{requirement_id}/versions`|Project member|S,L|immutable version page|
|REQ_VERSION_CREATE|POST `/api/v1/projects/{project_id}/requirements/{requirement_id}/versions`|ProjectManager、ImplementationMember|S,L,C,I,M,A|201 DRAFT RequirementVersion|
|REQ_VERSION_GET|GET `/api/v1/projects/{project_id}/requirements/{requirement_id}/versions/{requirement_version_id}`|Project member|S,L|固定 sources/classification/criteria|
|REQ_VERSION_VALIDATE|POST `/api/v1/projects/{project_id}/requirements/{requirement_id}/versions/{requirement_version_id}:validate`|ProjectManager、ImplementationMember|S,L,C,I,A|200 evidence/capability/criteria report|
|REQ_VERSION_SUBMIT_REVIEW|POST `/api/v1/projects/{project_id}/requirements/{requirement_id}/versions/{requirement_version_id}:submit-review`|ProjectManager|S,L,C,I,A|201 ReviewRef + RoundRef|
|REQ_RELATION_LIST|GET `/api/v1/projects/{project_id}/requirement-relations`|Project member|S,L|Relation page|
|REQ_RELATION_CREATE|POST `/api/v1/projects/{project_id}/requirement-relations`|ProjectManager、ImplementationMember|S,L,C,I,A|201 ACTIVE immutable relation|
|REQ_RELATION_REVOKE|POST `/api/v1/projects/{project_id}/requirement-relations/{relation_id}:revoke`|ProjectManager、ImplementationMember|S,L,C,I,A|200 REVOKED|
|REQ_RELATION_SUPERSEDE|POST `/api/v1/projects/{project_id}/requirement-relations/{relation_id}:supersede`|ProjectManager、ImplementationMember|S,L,C,I,A|201 replacement relation|

- Classification 固定为 STANDARD_FUNCTION/NONSTANDARD_FUNCTION/DIFFERENCE/PENDING_CONFIRMATION；不得用 AI confidence 直接映射分类。
- STANDARD_FUNCTION 至少一个人工 CONFIRMED DIRECT CapabilityAssessment；NONSTANDARD_FUNCTION/DIFFERENCE 必须记录 fit gap、解决方向、Evidence 和排除；PENDING_CONFIRMATION 不得送审为正式实施承诺。
- AcceptanceCriterion 必须包含可观察结果、验证方式、数据/环境和 Evidence 要求。来源只能使用 Approved SurveyConclusion、已确认 Handover、人工作出的正式决定或合格 Evidence。
- Relation 两端必须是同项目固定 RequirementVersion；DEPENDS_ON/PARENT_OF 禁止自环和非法环，DUPLICATES/CONFLICTS_WITH 使用规范化端点顺序。

## Prototype：原型范围、模板与需求覆盖

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|PRT_PACKAGE_LIST|GET `/api/v1/projects/{project_id}/prototype-packages`|Project member|S,L|Package page|
|PRT_PACKAGE_CREATE|POST `/api/v1/projects/{project_id}/prototype-packages`|ProjectManager、ImplementationMember|S,L,C,I,A|201 Package + ETag|
|PRT_PACKAGE_GET|GET `/api/v1/projects/{project_id}/prototype-packages/{package_id}`|Project member|S,L|PackageView + ETag|
|PRT_PACKAGE_PATCH|PATCH `/api/v1/projects/{project_id}/prototype-packages/{package_id}`|ProjectManager、ImplementationMember|S,L,C,M,A|200 metadata + ETag|
|PRT_PACKAGE_SET_MEMBERS|POST `/api/v1/projects/{project_id}/prototype-packages/{package_id}:set-members`|ProjectManager、ImplementationMember|S,L,C,I,M,A|200 same-project members|
|PRT_LIST|GET `/api/v1/projects/{project_id}/prototypes`|Project member|S,L|Prototype page|
|PRT_CREATE|POST `/api/v1/projects/{project_id}/prototypes`|ProjectManager、ImplementationMember|S,L,C,I,A|201 Prototype identity + ETag|
|PRT_GET|GET `/api/v1/projects/{project_id}/prototypes/{prototype_id}`|Project member|S,L|PrototypeView + ETag|
|PRT_PATCH|PATCH `/api/v1/projects/{project_id}/prototypes/{prototype_id}`|ProjectManager、ImplementationMember|S,L,C,M,A|200 metadata + ETag|
|PRT_MARK_NOT_REQUIRED|POST `/api/v1/projects/{project_id}/prototypes/{prototype_id}:mark-not-required`|ProjectManager、CustomerManager|S,L,C,I,M,A|200 NOT_REQUIRED + scope decision|
|PRT_ARCHIVE|POST `/api/v1/projects/{project_id}/prototypes/{prototype_id}:archive`|ProjectManager|S,L,C,I,M,A|200 ARCHIVED|
|PRT_VERSION_LIST|GET `/api/v1/projects/{project_id}/prototypes/{prototype_id}/versions`|Project member|S,L|immutable version page|
|PRT_VERSION_CREATE|POST `/api/v1/projects/{project_id}/prototypes/{prototype_id}/versions`|ProjectManager、ImplementationMember|S,L,C,I,M,A|201 DRAFT PrototypeVersion|
|PRT_VERSION_GET|GET `/api/v1/projects/{project_id}/prototypes/{prototype_id}/versions/{prototype_version_id}`|Project member|S,L|固定 artifact/interaction/requirement refs|
|PRT_VERSION_VALIDATE|POST `/api/v1/projects/{project_id}/prototypes/{prototype_id}/versions/{prototype_version_id}:validate`|ProjectManager、ImplementationMember|S,L,C,I,A|200 artifact/coverage/security report|
|PRT_VERSION_SUBMIT_REVIEW|POST `/api/v1/projects/{project_id}/prototypes/{prototype_id}/versions/{prototype_version_id}:submit-review`|ProjectManager|S,L,C,I,A|201 ReviewRef + RoundRef|
|PRT_TEMPLATE_LIST|GET `/api/v1/projects/{project_id}/prototype-templates`|Project member|S,L|PROJECT + allowed GLOBAL template page|
|PRT_TEMPLATE_GLOBAL_LIST|GET `/api/v1/global/prototype-templates`|DeploymentAdmin；受权项目成员只读|S,L|GLOBAL template page|
|PRT_TEMPLATE_CREATE|POST `/api/v1/projects/{project_id}/prototype-templates`|ProjectManager、ImplementationMember|S,L,C,I,A|201 PROJECT Template + ETag|
|PRT_TEMPLATE_GLOBAL_CREATE|POST `/api/v1/global/prototype-templates`|DeploymentAdmin|S,L,C,I,A|201 GLOBAL Template + ETag|
|PRT_TEMPLATE_REVISE|POST `/api/v1/projects/{project_id}/prototype-templates/{template_id}:revise`|ProjectManager、ImplementationMember|S,L,C,I,M,A|201 new immutable template version|
|PRT_TEMPLATE_GLOBAL_REVISE|POST `/api/v1/global/prototype-templates/{template_id}:revise`|DeploymentAdmin|S,L,C,I,M,A|201 new immutable template version|
|PRT_LINK_LIST|GET `/api/v1/projects/{project_id}/prototype-requirement-links`|Project member|S,L|coverage relation page|
|PRT_LINK_CREATE|POST `/api/v1/projects/{project_id}/prototype-requirement-links`|ProjectManager、ImplementationMember|S,L,C,I,A|201 ACTIVE immutable link|
|PRT_LINK_REVOKE|POST `/api/v1/projects/{project_id}/prototype-requirement-links/{link_id}:revoke`|ProjectManager、ImplementationMember|S,L,C,I,A|200 REVOKED|
|PRT_LINK_SUPERSEDE|POST `/api/v1/projects/{project_id}/prototype-requirement-links/{link_id}:supersede`|ProjectManager、ImplementationMember|S,L,C,I,A|201 replacement link|

- PrototypeVersion 只引用 Approved RequirementVersion 和固定 TemplateVersion/ArtifactRef；AI 生成制品仍为 Draft，不执行任意代码，不引入原型执行沙箱。
- NOT_REQUIRED 必须列出受影响 RequirementVersion、理由、范围决定和确认/Review 引用；不能用无原型链接静默表示不需要。
- Link 两端同项目且固定版本，purpose 仅 ILLUSTRATES/VALIDATES/ACCEPTANCE_REFERENCE；Review 原型不自动批准 Requirement 或 Solution。

## Solution：参考、目录、章节与专项设计

`{solution_scope}` 在 OpenAPI 中展开为 `/api/v1/projects/{project_id}` 和 `/api/v1/global` 两套白名单路径；客户端不能提交自由 scope 字符串。GLOBAL ReferenceSolution 只允许 DeploymentAdmin 写。

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|SOL_REFERENCE_LIST|GET `{solution_scope}/reference-solutions`|受权主体|S,L|ReferenceSolution page|
|SOL_REFERENCE_CREATE|POST `{solution_scope}/reference-solutions`|项目 PM/IM；GLOBAL DeploymentAdmin|S,L,C,I,A|201 REFERENCE_ONLY + ETag|
|SOL_REFERENCE_GET|GET `{solution_scope}/reference-solutions/{reference_solution_id}`|受权主体|S,L|固定 reference/source refs + ETag|
|SOL_REFERENCE_REVISE|POST `{solution_scope}/reference-solutions/{reference_solution_id}:revise`|项目 PM/IM；GLOBAL DeploymentAdmin|S,L,C,I,M,A|201 new reference version|
|SOL_REFERENCE_SET_ELIGIBILITY|POST `{solution_scope}/reference-solutions/{reference_solution_id}:set-eligibility`|项目 ProjectManager；GLOBAL DeploymentAdmin|S,L,C,I,M,A|200 eligibility + reason|
|SOL_OUTLINE_LIST|GET `/api/v1/projects/{project_id}/solution-outlines`|Project member|S,L|Outline page|
|SOL_OUTLINE_CREATE|POST `/api/v1/projects/{project_id}/solution-outlines`|ProjectManager、ImplementationMember|S,L,C,I,A|201 Outline identity + ETag|
|SOL_OUTLINE_GET|GET `/api/v1/projects/{project_id}/solution-outlines/{outline_id}`|Project member|S,L|OutlineView + ETag|
|SOL_OUTLINE_PATCH|PATCH `/api/v1/projects/{project_id}/solution-outlines/{outline_id}`|ProjectManager、ImplementationMember|S,L,C,M,A|200 metadata + ETag|
|SOL_OUTLINE_ARCHIVE|POST `/api/v1/projects/{project_id}/solution-outlines/{outline_id}:archive`|ProjectManager|S,L,C,I,M,A|200 ARCHIVED|
|SOL_OUTLINE_VERSION_LIST|GET `/api/v1/projects/{project_id}/solution-outlines/{outline_id}/versions`|Project member|S,L|immutable outline version page|
|SOL_OUTLINE_VERSION_CREATE|POST `/api/v1/projects/{project_id}/solution-outlines/{outline_id}/versions`|ProjectManager、ImplementationMember|S,L,C,I,M,A|201 DRAFT OutlineVersion|
|SOL_OUTLINE_VERSION_GET|GET `/api/v1/projects/{project_id}/solution-outlines/{outline_id}/versions/{outline_version_id}`|Project member|S,L|固定 order/requirement/reference refs|
|SOL_OUTLINE_VERSION_VALIDATE|POST `/api/v1/projects/{project_id}/solution-outlines/{outline_id}/versions/{outline_version_id}:validate`|ProjectManager、ImplementationMember|S,L,C,I,A|200 order/source/coverage report|
|SOL_OUTLINE_VERSION_SUBMIT_REVIEW|POST `/api/v1/projects/{project_id}/solution-outlines/{outline_id}/versions/{outline_version_id}:submit-review`|ProjectManager|S,L,C,I,A|201 ReviewRef + RoundRef|
|SOL_SECTION_LIST|GET `/api/v1/projects/{project_id}/solution-sections`|Project member|S,L|Section page|
|SOL_SECTION_CREATE|POST `/api/v1/projects/{project_id}/solution-sections`|ProjectManager、ImplementationMember|S,L,C,I,A|201 Section identity + ETag|
|SOL_SECTION_GET|GET `/api/v1/projects/{project_id}/solution-sections/{section_id}`|Project member|S,L|SectionView + ETag|
|SOL_SECTION_PATCH|PATCH `/api/v1/projects/{project_id}/solution-sections/{section_id}`|ProjectManager、ImplementationMember|S,L,C,M,A|200 metadata + ETag|
|SOL_SECTION_ARCHIVE|POST `/api/v1/projects/{project_id}/solution-sections/{section_id}:archive`|ProjectManager|S,L,C,I,M,A|200 ARCHIVED|
|SOL_SECTION_VERSION_LIST|GET `/api/v1/projects/{project_id}/solution-sections/{section_id}/versions`|Project member|S,L|immutable section version page|
|SOL_SECTION_VERSION_CREATE|POST `/api/v1/projects/{project_id}/solution-sections/{section_id}/versions`|ProjectManager、ImplementationMember|S,L,C,I,M,A|201 DRAFT SectionVersion|
|SOL_SECTION_VERSION_GET|GET `/api/v1/projects/{project_id}/solution-sections/{section_id}/versions/{section_version_id}`|Project member|S,L|固定 content/evidence/requirement refs|
|SOL_SECTION_VERSION_VALIDATE|POST `/api/v1/projects/{project_id}/solution-sections/{section_id}/versions/{section_version_id}:validate`|ProjectManager、ImplementationMember|S,L,C,I,A|200 evidence/trace/spec report|
|SOL_SECTION_VERSION_SUBMIT_REVIEW|POST `/api/v1/projects/{project_id}/solution-sections/{section_id}/versions/{section_version_id}:submit-review`|ProjectManager|S,L,C,I,A|201 ReviewRef + RoundRef|
|SOL_SPEC_LIST|GET `/api/v1/projects/{project_id}/structured-solution-specs`|Project member|S,L|Spec version page|
|SOL_SPEC_CREATE|POST `/api/v1/projects/{project_id}/structured-solution-specs`|ProjectManager、ImplementationMember|S,L,C,I,A|201 DRAFT StructuredSpec|
|SOL_SPEC_GET|GET `/api/v1/projects/{project_id}/structured-solution-specs/{spec_id}`|Project member|S,L|固定 typed payload/ref set|
|SOL_SPEC_REVISE|POST `/api/v1/projects/{project_id}/structured-solution-specs/{spec_id}:revise`|ProjectManager、ImplementationMember|S,L,C,I,A|201 replacement DRAFT version|
|SOL_SPEC_VALIDATE|POST `/api/v1/projects/{project_id}/structured-solution-specs/{spec_id}:validate`|ProjectManager、ImplementationMember|S,L,C,I,A|200 type-specific validation report|
|SOL_SPEC_SUBMIT_REVIEW|POST `/api/v1/projects/{project_id}/structured-solution-specs/{spec_id}:submit-review`|ProjectManager|S,L,C,I,A|201 ReviewRef + RoundRef|
|SOL_COVERAGE_GET|GET `/api/v1/projects/{project_id}/solution-coverage`|Project member|S,L|approved requirement → section/spec coverage report|

- ReferenceSolution 不自动成为项目方案；只有固定引用、适用性、脱敏级别和 Eligibility 均合格时才可作为 REFERENCE_ONLY 来源。
- Outline Review 不等于 Section Review。正式输出固定一个 Approved OutlineVersion 及其明确列出的 Approved SectionVersion/StructuredSpecVersion。
- Section 的 requirement snapshot 与 TraceLink `IMPLEMENTS` 必须一致；每个 Approved RequirementVersion 必须被覆盖或具有显式排除/延期决定。
- PROCESS_MODEL/INTERFACE_SPEC/MIGRATION_SPEC/PERMISSION_DESIGN 分别执行类型化 Schema 与业务校验；正文、图形和大附件只保存受控 DocumentVersion/ArtifactRef。

## Plan：参考计划、实施计划与 WBS

`{plan_scope}` 同样只在 OpenAPI 中展开为 PROJECT 与 GLOBAL 白名单路径；ReferencePlan 不是当前项目承诺。

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|PLAN_REFERENCE_LIST|GET `{plan_scope}/reference-plans`|受权主体|S,L|ReferencePlan page|
|PLAN_REFERENCE_CREATE|POST `{plan_scope}/reference-plans`|项目 PM/IM；GLOBAL DeploymentAdmin|S,L,C,I,A|201 REFERENCE_ONLY + ETag|
|PLAN_REFERENCE_GET|GET `{plan_scope}/reference-plans/{reference_plan_id}`|受权主体|S,L|fixed source/mapping/parse summary + ETag|
|PLAN_REFERENCE_REVISE|POST `{plan_scope}/reference-plans/{reference_plan_id}:revise`|项目 PM/IM；GLOBAL DeploymentAdmin|S,L,C,I,M,A|201 new reference version|
|PLAN_REFERENCE_SET_ELIGIBILITY|POST `{plan_scope}/reference-plans/{reference_plan_id}:set-eligibility`|项目 ProjectManager；GLOBAL DeploymentAdmin|S,L,C,I,M,A|200 eligibility + reason|
|PLAN_LIST|GET `/api/v1/projects/{project_id}/plans`|Project member|S,L|Plan page|
|PLAN_CREATE|POST `/api/v1/projects/{project_id}/plans`|ProjectManager、ImplementationMember|S,L,C,I,A|201 Plan identity + ETag|
|PLAN_GET|GET `/api/v1/projects/{project_id}/plans/{plan_id}`|Project member|S,L|PlanView + ETag|
|PLAN_PATCH|PATCH `/api/v1/projects/{project_id}/plans/{plan_id}`|ProjectManager、ImplementationMember|S,L,C,M,A|200 metadata + ETag|
|PLAN_ARCHIVE|POST `/api/v1/projects/{project_id}/plans/{plan_id}:archive`|ProjectManager|S,L,C,I,M,A|200 ARCHIVED|
|PLAN_VERSION_LIST|GET `/api/v1/projects/{project_id}/plans/{plan_id}/versions`|Project member|S,L|immutable version page|
|PLAN_VERSION_CREATE|POST `/api/v1/projects/{project_id}/plans/{plan_id}/versions`|ProjectManager、ImplementationMember|S,L,C,I,M,A|201 DRAFT PlanVersion|
|PLAN_VERSION_GET|GET `/api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}`|Project member|S,L|固定 solution/WBS/dependency/milestone refs|
|PLAN_VERSION_WBS_LIST|GET `/api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}/wbs-items`|Project member|S,L|WBS item page|
|PLAN_VERSION_VALIDATE|POST `/api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}:validate`|ProjectManager、ImplementationMember|S,L,C,I,A|200 hierarchy/DAG/date/coverage report|
|PLAN_VERSION_COMPARE|GET `/api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}/comparison?other_version_id={other_version_id}`|Project member|S,L|与指定固定版本的安全差异摘要|
|PLAN_VERSION_SUBMIT_REVIEW|POST `/api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}:submit-review`|ProjectManager|S,L,C,I,A|201 ReviewRef + RoundRef|

- PlanVersion 输入必须是 Approved Solution Outline/Section/StructuredSpec 的固定集合；参考计划仅作模板，不自动填充负责人、日期、依赖或承诺。
- WBS level 仅 1..6，parent 必须存在且 `level=parent+1`；Dependency V1 仅 FS，禁止自环/成环，lag 非零必须含单位和理由。
- 每个范围内 Requirement/Solution 必须映射到 WBS Item 或显式排除/延期；负责人、进入条件、AcceptanceCriteria 和交付 Evidence 规则缺失时不得送审。
- 进度更新创建新 PlanVersion/受控快照；Approved baseline 不覆盖，比较端点只接受两个固定版本且逐节点授权。

## DTO 目录

### 通用业务 DTO

|DTO|最小字段/约束|
|---|---|
|BusinessIdentityView|resource_id、project/global scope、name、state、current_approved_version_ref、lock_version、created/updated metadata|
|ImmutableVersionRef|resource_type、resource_id、version_id、version_no、content_fingerprint；禁止 current/latest|
|VersionCreateRequest|base_version_ref 或 initial、完整内容快照、EvidenceRef、Trace input refs、client_reason|
|ReviewSubmissionRequest|reviewer_ids、policy_ref、due_at、submission_note；subject version 从路径固定|
|ValidationReport|valid、blocking_issues、warnings、coverage_summary、checked_at；不改变状态|
|SourceDecisionRef|decision_type、reason、impact、EvidenceRef/ReviewRef；用于排除、延期、风险接受和 NOT_REQUIRED|
|UpstreamChangeView|changed_version_ref、affected_version_refs、impact_state、recommended_action；不自动改写下游|

### Capability、Handover 与 Survey

|DTO|最小字段/约束|
|---|---|
|CapabilityItemInput|stable_item_id/code、domain/module/feature、name/description、boundary、prerequisites、interface/document/evidence refs、item_state|
|HandoverAnalysisVersionInput|fixed source_document_version_refs、approved capability_baseline_version_ref、AnalysisItemInput[]、ai_task_refs|
|AnalysisItemInput|type、title、statement、impact/severity/priority、evidence/conflict refs、recommendation/options；NEED_CONFIRM 另含 question/input spec|
|ActionItemInput|source item 或 explicit human source、type、title、requested_input_spec、owner、due_at、priority|
|SurveyVersionInput|QuestionInput[]、source refs、target department refs；条件引用只能指向同版本较早问题|
|SurveyResponseInput|question_ref、typed value/raw answer、response_source、evidence_refs、correction_of_ref；服务器记录 actor/time|
|SurveyConclusionInput|round_refs、department/module conclusions、evidence/conflict/open issue refs、ai_task_refs|

### Requirement、Prototype、Solution 与 Plan

|DTO|最小字段/约束|
|---|---|
|RequirementVersionInput|statement/rationale、domain/priority/risk、classification、CapabilityAssessment[]、sources、AcceptanceCriterion[]、assumptions/exclusions/dependencies|
|CapabilityAssessmentInput|fixed baseline/item refs、DIRECT/PARTIAL/NONE/UNKNOWN、fit_gap、constraints、双方 evidence、confirmation_state|
|PrototypeVersionInput|artifact refs、interaction spec ref、approved requirement version refs、fixed template version ref、coverage summary|
|PrototypeNotRequiredRequest|affected requirement version refs、reason、impact、decision/review refs|
|SolutionOutlineVersionInput|ordered stable section refs、approved requirement refs、eligible reference refs、missing/conflict declarations|
|SolutionSectionVersionInput|content ref、approved requirement refs、evidence refs、structured spec refs、assumptions/exclusions|
|StructuredSolutionSpecInput|spec_type、typed payload ref、diagram refs、section/requirement refs、evidence、assumptions/exclusions|
|PlanVersionInput|approved solution version refs、WbsItemInput[]、FS DependencyInput[]、MilestoneInput[]、calendar_ref、exclusions|
|WbsItemInput|stable item/parent ids、code/name/level、category、owner/support roles、dates/duration/state、entry/acceptance、fixed business refs、evidence/output refs、risk/exclusion|

禁止请求/响应字段：数据库表/列名、内部 FK、绝对路径、Storage Locator、AI Provider Secret/原始 Prompt、Plugin stdio/PID、Job Lease/fencing、Review 内部锁记录、任意 SQL/filter/order 表达式。列表使用 API-01 keyset cursor；响应可新增可选字段，请求未知字段默认拒绝。

## 权限矩阵摘要

|资源族|DeploymentAdmin|ProjectManager|ImplementationMember|CustomerManager|CustomerMember|SystemActor|
|---|---|---|---|---|---|---|
|GLOBAL Capability/Template/Reference 写|允许明确管理操作|只读项目正式引用|只读项目正式引用|只读项目正式引用|最小只读|仅授权 Job 快照|
|Handover Draft/Action|仅作为项目成员|全链管理/验证/关闭|创建修订、执行待办|确认/验证受权项|读取/处理分配项|仅固定命令|
|Survey 定义/Round|仅作为项目成员|创建、开放、关闭、Review|创建、录入、校验|组织、答复、Review|本人答复/Review|仅固定命令|
|Requirement|仅作为项目成员|全链、状态决定、Review|创建/修订/关系|业务确认、Review、延期/拒绝|受权读取/Review|仅固定命令|
|Prototype/Solution|仅作为项目成员|全链、范围决定、Review|创建/修订/校验|Review/范围确认|受权读取/Review|仅固定命令|
|Plan|仅作为项目成员|全链、基线 Review|创建/修订/校验|Review/里程碑确认|受权读取|仅固定命令|

- DeploymentAdmin 不因全局角色自动获得项目正文访问权；必须成为项目成员并按项目角色访问。
- CustomerMember 只看到被分配的 Survey/Review 和显式授权的项目读面，不获得工作区批量枚举或写 Draft 权限。
- SystemActor 必须携带原 actor/project/operation 授权快照，只能调用指定 Owner Port；不能创建新授权、扩大引用集合或代替人工 Review。

## SSE Event Contract

API-02/03 项目 SSE 增加以下白名单 `event_type`；payload 仍只含 event_id、resource/version ref、state、progress、trace_id 和必要分类，不含正文、回答、客户名称、AI 内容或文件路径。

|event_type|触发|最小资源状态|
|---|---|---|
|`handover.analysis.reviewed`|AnalysisVersion Review 完成/退回|analysis/version/review state|
|`handover.action.changed`|ActionItem 状态迁移|action_item/state|
|`survey.round.changed`|Round 开放/关闭/取消|round/state|
|`survey.assignment.changed`|Assignment 提交/校验/退回|assignment/state|
|`survey.conclusion.reviewed`|Conclusion Review 完成/退回|conclusion/version state|
|`requirement.version.reviewed`|RequirementVersion Review 完成/退回|requirement/version state|
|`prototype.version.reviewed`|PrototypeVersion Review 完成/退回|prototype/version state|
|`solution.version.reviewed`|Outline/Section/Spec Review 完成/退回|typed version state|
|`plan.version.reviewed`|PlanVersion Review 完成/退回|plan/version state|
|`business.upstream-changed`|上游 Approved Version 被替代|affected resource + impact state|

每次事件发送前重新授权；撤权/归档后断流。`Last-Event-ID` 仅在受限恢复窗口内生效，超窗重新 GET 当前资源。

## 错误码目录

|HTTP|错误码|语义|
|---:|---|---|
|409|`BUSINESS_VERSION_IMMUTABLE`|版本内容或 owned child 不可修改|
|422|`BUSINESS_VERSION_BASE_REQUIRED`|非初始版本缺少固定 base version|
|409|`BUSINESS_VERSION_BASE_MISMATCH`|base version 不属于目标 identity/Scope|
|409|`BUSINESS_REVIEW_ACTIVE`|版本正处于 Active Review|
|422|`BUSINESS_REVIEW_NOT_ELIGIBLE`|来源、Evidence、覆盖或状态不满足送审|
|409|`BUSINESS_UPSTREAM_CHANGED`|上游已替代且影响尚未处理|
|422|`BUSINESS_FIXED_VERSION_REQUIRED`|使用 current/latest 或非固定引用|
|409|`BUSINESS_PROJECT_REFERENCE_MISMATCH`|引用跨项目或 Scope 不允许|
|422|`CAPABILITY_EVIDENCE_REQUIRED`|能力项缺少合格 GLOBAL Evidence|
|409|`CAPABILITY_BASELINE_NOT_APPROVED`|项目正式引用的基线未批准|
|409|`CAPABILITY_ITEM_NOT_AVAILABLE`|能力项已撤销、受限或不在固定版本|
|409|`CAPABILITY_ARCHIVE_REFERENCED`|归档动作与保护引用/状态冲突|
|422|`HANDOVER_SOURCE_REQUIRED`|分析缺少固定来源或资格不合格|
|422|`HANDOVER_ITEM_INCOMPLETE`|问题项缺少 Evidence/资料缺失声明|
|422|`HANDOVER_CONFIRMATION_PROMPT_REQUIRED`|NEED_CONFIRM 缺问题、影响、选项、建议或输入规格|
|409|`HANDOVER_ACTION_STATE_INVALID`|待办状态迁移非法|
|422|`HANDOVER_ACTION_EVIDENCE_REQUIRED`|提交、验证或关闭缺少所需 Evidence|
|422|`HANDOVER_ACTION_RESOLUTION_REQUIRED`|关闭缺验证结果或 resolution trace|
|409|`SURVEY_VERSION_NOT_APPROVED`|Round 绑定的 SurveyVersion 未批准|
|409|`SURVEY_ROUND_CLOSED`|关闭/取消轮次仍提交答复|
|422|`SURVEY_QUESTION_CONDITION_INVALID`|问题条件循环、越界或引用未来问题|
|422|`SURVEY_RESPONSE_INVALID`|回答类型/ValidationRule 不满足|
|422|`SURVEY_RECORD_EVIDENCE_REQUIRED`|面对面录入缺 PROJECT_RECORD Evidence|
|409|`SURVEY_ASSIGNMENT_STATE_INVALID`|Assignment 状态迁移非法|
|422|`SURVEY_REQUIRED_RESPONSE_MISSING`|必答问题未满足|
|422|`SURVEY_CONCLUSION_SOURCE_INVALID`|结论来源非 VALIDATED/不合格|
|409|`SURVEY_CONFLICT_UNRESOLVED`|关键冲突/缺失未处理|
|422|`REQUIREMENT_SOURCE_REQUIRED`|需求缺少正式来源/Evidence|
|422|`REQUIREMENT_CLASSIFICATION_INVALID`|分类与能力评估不一致|
|422|`REQUIREMENT_PENDING_NOT_FORMAL`|待确认需求试图进入正式承诺|
|422|`REQUIREMENT_ACCEPTANCE_INVALID`|验收标准不可观察/不可验证|
|409|`REQUIREMENT_RELATION_SELF`|关系自环|
|409|`REQUIREMENT_RELATION_CYCLE`|DEPENDS_ON/PARENT_OF 产生非法环|
|409|`REQUIREMENT_RELATION_DUPLICATE`|Active 关系重复|
|422|`PROTOTYPE_REQUIREMENT_NOT_APPROVED`|原型引用未批准需求|
|422|`PROTOTYPE_ARTIFACT_INVALID`|制品缺失、受限或完整性失败|
|422|`PROTOTYPE_COVERAGE_INCOMPLETE`|需求覆盖缺口未解释|
|422|`PROTOTYPE_NOT_REQUIRED_DECISION_MISSING`|NOT_REQUIRED 缺范围决定/影响|
|409|`PROTOTYPE_LINK_INVALID`|链接跨项目、非固定版本或 purpose 非法|
|422|`SOLUTION_REFERENCE_INELIGIBLE`|参考方案不合格或受限|
|422|`SOLUTION_OUTLINE_INVALID`|目录顺序、章节或来源无效|
|422|`SOLUTION_CONTENT_REQUIRED`|章节缺受控正文引用|
|422|`SOLUTION_EVIDENCE_REQUIRED`|章节/专项缺 Evidence|
|409|`SOLUTION_TRACE_MISMATCH`|章节需求快照与 IMPLEMENTS Trace 不一致|
|422|`SOLUTION_COVERAGE_INCOMPLETE`|批准需求未覆盖且无排除/延期|
|422|`SOLUTION_SPEC_SCHEMA_INVALID`|专项设计不满足类型 Schema|
|422|`PLAN_REFERENCE_INELIGIBLE`|参考计划不合格或解析失败|
|422|`PLAN_SOLUTION_NOT_APPROVED`|计划输入方案版本未批准|
|422|`PLAN_WBS_LEVEL_INVALID`|WBS 层级不在 1..6 或 parent/level 不一致|
|409|`PLAN_WBS_DEPENDENCY_CYCLE`|FS 依赖自环或成环|
|422|`PLAN_WBS_DATE_INVALID`|日期、工期、lag 或里程碑不一致|
|422|`PLAN_WBS_OWNER_REQUIRED`|实施项缺负责人/角色|
|422|`PLAN_WBS_ACCEPTANCE_REQUIRED`|实施项缺进入条件/验收|
|422|`PLAN_COVERAGE_INCOMPLETE`|需求/方案未映射且无排除/延期|

本目录叠加 API-01 通用错误、API-02 Review/Evidence/Trace 错误及 API-03 AI/Job/Output 错误；同一语义不得创建不同 message 变体作为新机器码。

## 强制 Audit 动作

- GLOBAL Capability/Template/Reference 的创建、修订、资格、限制和归档。
- 所有业务 Identity 创建/元数据修改/归档，Version 创建、验证、送审和 Review 结果消费。
- ActionItem 分配、提交、验证、关闭、取消及受控字段修改。
- Survey Round 开闭、Assignment 分配、Response 录入/更正、提交/校验/退回。
- Requirement 延期/拒绝/归档、Package 成员变化和 Relation create/revoke/supersede。
- Prototype NOT_REQUIRED、模板修订、覆盖 Link 变化和 Artifact 完整性失败。
- Solution Reference eligibility、目录/章节/专项版本、覆盖/Trace 不一致。
- ReferencePlan eligibility、PlanVersion 验证/送审、WBS/Dependency/Gate 校验失败。
- 跨项目、动态版本、AI 自动正式化、模板冒充事实、Review 锁绕过和权限失败尝试。

Audit 只保存安全摘要、对象/固定版本引用、actor、动作、结果、reason code 和 trace_id；不得保存完整客户正文、回答、Secret、本地路径或 AI 原始响应。

## Contract 测试矩阵

|测试族|必须覆盖|
|---|---|
|Root/Operation lint|7 Owner、28 Root 恰好覆盖；Operation ID/错误码唯一；无通用 DELETE|
|Common security|Session、License、CSRF、ProjectId/归属双检、跨项目 404、ETag、幂等、Audit|
|Version/Review|不可变 Version、固定 ref、base version、Active Review 锁、Return 后升版、Owner 消费 Review 结果|
|Evidence/Trace|固定 DocumentVersion 定位、逐节点授权、CONTRADICTS 保留、Trace snapshot 一致|
|Capability|仅 Approved baseline 可正式匹配、GLOBAL 项目只读、Item Evidence/withdraw 历史|
|Handover|六类 Item、NEED_CONFIRM 提示完整、AI 不关闭问题、ActionItem Submitted≠Closed|
|Survey|实际记录优先、模板不造事实、Response 追加更正、Round close、冲突结论失败关闭|
|Requirement|四分类规则、DIRECT 人工确认、PENDING 阻断、AcceptanceCriterion、关系 DAG|
|Prototype|Approved Requirement 输入、Artifact 校验、NOT_REQUIRED 决策、固定版本覆盖链接|
|Solution|Reference-only、Outline/Section 独立 Review、typed Spec、coverage 与 Trace 一致|
|Plan|Approved Solution 输入、六级树、FS DAG、日期/负责人/验收、全范围映射|
|AI/Upstream|Suggestion accept 仅建 Draft；上游替代只建影响项，不自动改写/批准下游|
|SSE/Leakage|逐事件授权、撤权断流、Last-Event-ID 窗口、正文/回答/路径/内部字段 0 泄露|

## 风险与关闭条件

|Risk ID|风险|当前控制|关闭位置|
|---|---|---|---|
|API4-R01|版本端点被误实现为可变文档|无 Version PATCH/DELETE；修订创建新 Version|API/Repository contract tests|
|API4-R02|Owner `:submit-review` 绕过统一 Review|明确为 ReviewService 编排，沿用 API-02 权限/锁/决策|Review 集成测试|
|API4-R03|Review 通过但 Owner 指针更新失败|Owner 短事务 + Outbox 幂等消费|故障注入与恢复测试|
|API4-R04|实际调研记录被模板/AI 覆盖|来源优先级、Evidence、模板不得造 Answer|Survey 行为测试/UAT|
|API4-R05|AI Suggestion 被误标成正式事实|仅 accept-to-draft；正式化需 Review|AI→Owner 集成测试|
|API4-R06|GLOBAL 资料导致项目数据泄露/反写|GLOBAL→PROJECT 白名单固定引用、逐节点授权|权限/跨 Scope 负测|
|API4-R07|NeedConfirm/待办再次退化为空表格|问题/影响/选项/建议/input spec 强制 Schema|Handover API/UI Contract 测试|
|API4-R08|需求分类与能力匹配不一致|分类不变量、项目与标准双方 Evidence|Requirement 规则测试|
|API4-R09|原型制品执行不受信代码|只保存 Artifact/Draft，不引入执行沙箱|Prototype 安全测试|
|API4-R10|方案章节快照与 Trace 双写漂移|送审前一致性检查，失败关闭|Solution integration test|
|API4-R11|WBS 循环/层级/日期错误形成承诺|六级、FS DAG、日期/工期/覆盖校验|Plan property/integration tests|
|API4-R12|上游升版静默改变下游交付|只创建影响项，人工选择升版/重审|端到端变更传播测试|
|API4-R13|SSE/列表泄露客户回答或无权节点|白名单最小投影、每次授权、无权 404|Permission/leakage tests|
|API4-R14|POC-03 分类/引用质量被设计通过掩盖|保留 Gate 3/UAT 阻塞与人工 Evidence Review|新独立留出集/对应 Gate|

## API-04 验收

- 7 个 Owner、28 个 Root 均有明确资源或受控嵌套边界：PASS。
- Identity、不可变 Version、Owner Review 编排和正式指针更新语义一致：PASS。
- Capability GLOBAL 权限、固定批准版本、能力项 Evidence 与项目只读边界明确：PASS。
- Handover 六类问题、定位原文、人工输入提示和 ActionItem 验证关闭明确：PASS。
- Survey 定义、轮次、追加答复、更正、面对面记录优先和结论正式化明确：PASS。
- Requirement 四分类、能力匹配、正式来源、验收标准和关系 DAG 明确：PASS。
- Prototype 范围决定、模板版本、制品校验、NOT_REQUIRED 与需求覆盖明确：PASS。
- Solution 参考/目录/章节/专项设计、独立 Review、覆盖和 Trace 一致性明确：PASS。
- Plan 参考、固定方案输入、六级 WBS、FS DAG、日期、负责人、验收和覆盖明确：PASS。
- AI Suggestion 只创建 Draft；模板/参考资料不自动成为客户事实或项目承诺：PASS。
- Role × Operation × Project、错误码、Audit、SSE 和 Contract 测试矩阵明确：PASS。
- 所有状态写操作具备 CSRF；可重试创建/命令具备幂等；可变 Root 修改具备 If-Match：PASS。
- 14 项风险均有控制与关闭位置，POC-03 质量阻塞未被改写：PASS。
- 未执行真实外部调用，未创建 FastAPI/Pydantic/ORM/Migration/前端或正式业务事实：PASS。

## 下一步

API-05：汇总 API-01～API-04 为 `API-CONTRACT-CANDIDATE-V1`，生成统一资源/Operation/DTO/枚举/权限/错误/SSE 目录和机器一致性检查，提交 Gate 2 正式确认。
