# SC-01：逻辑到物理 Schema 映射 V1 候选

## 状态

`CANDIDATE / SC-01_COMPLETE / SC-02_NEXT / NOT_GATE_2_FROZEN / NO_MIGRATION_YET`

本文件将 `DATA-MODEL-CANDIDATE-V1` 的 65 个客户运行 Aggregate Root 映射到 PostgreSQL 18 物理命名与表边界。这里只确定数据库/Schema、表名、Owner、Root/Owned Entity 拆分和内容存储策略；字段类型、PK/FK/CHECK、索引、分区、Migration 在 SC-02～SC-04 完成。

## 物理组织决策

### 数据库与 PostgreSQL Schema

```text
Customer Runtime PostgreSQL Database
└─ plm                         # 全部客户运行应用表
   ├─ plt_* / auth_* / prj_*  # Platform / Auth / Project
   ├─ doc_* / evd_* / ...     # 其余模块按短前缀分组
   └─ alembic_version          # Migration 版本表，最终位置由 SC-04 固化

Developer Workbench Database  # 物理独立，不属于客户 plm Schema
└─ license/plugin/release signing records
```

选择单一应用 Schema `plm`，原因：

- V1 是单服务器模块化单体，使用同一应用数据库身份；22 个 PostgreSQL Schema 不会形成真正的进程或凭据隔离。
- 单一 Schema 降低 Alembic `search_path`、跨 Schema FK、备份/恢复、离线安装和 Windows/Linux 运维复杂度。
- 模块短前缀、Repository 边界、Application Port、Code Review 和测试共同维护 Owner；不得因同处 `plm` 而跨模块直接写表。
- `public` 不承载应用表；生产环境的 CREATE/search_path 权限在 SC-02/Release 安全设计中固化。

Developer Workbench 必须是独立数据库或独立开发者部署，不允许仅用 `plm_dev` Schema 与客户数据共库。

### 模块短前缀

|Owner|Prefix|Owner|Prefix|Owner|Prefix|
|---|---|---|---|---|---|
|platform|`plt_`|auth|`auth_`|project|`prj_`|
|workflow|`wfl_`|document|`doc_`|evidence|`evd_`|
|review|`rvw_`|trace|`trc_`|audit|`aud_`|
|jobs|`job_`|ai|`ai_`|rag|`rag_`|
|capability|`cap_`|handover|`hnd_`|survey|`srv_`|
|requirement|`req_`|prototype|`prt_`|solution|`sol_`|
|plan|`pln_`|output|`out_`|plugin|`plg_`|
|license|`lic_`|||||

Prefix 只表达数据 Owner，不是对外 API、Python package 或权限角色名称。

## 命名规范

1. Schema、表、列、约束和索引全部使用 ASCII `lower_snake_case`，不依赖 quoted identifier。
2. Root/collection 表使用复数名；模块前缀始终保留，例如 `req_requirement_versions`。
3. Root PK 列使用语义名 `<root>_id`；FK 使用 `<target>_id`，不使用含义不明的通用 `id`/`ref_id`。
4. 逻辑对象与 Version 分表；Version 表至少使用 `<object>_version_id` + `<object>_id` + `version_no` 语义。
5. 关联表名称按 `<owner_prefix><left>_<right>_links/memberships/refs`；如果关联本身是 Aggregate Root，使用其正式 Root 名称。
6. 历史/Attempt/Decision 使用独立行，不采用 `column_1...column_n` 或覆盖式 current-only 结构。
7. 表名目标不超过 55 ASCII 字符，为 PostgreSQL 标识符及约束/索引后缀保留空间；SC-02 对全部生成名称做 63-byte 检查。
8. 时间、状态、Scope、ProjectId、版本和 Audit 字段命名在 SC-02 统一，不在各模块自行发明同义词。
9. 不使用 PostgreSQL/SQL 易冲突裸名称，例如 `user`、`session`、`order`、`group`、`constraint`；模块前缀与复数名必须保留。

## 拆表与内容存储规则

|策略|适用条件|SC-01 结论|
|---|---|---|
|ROOT_TABLE|Aggregate Root 身份、状态、Scope、current pointer|每个 Root 恰好一个 primary table|
|CHILD_TABLE|需要独立唯一、顺序、查询、状态、FK、版本或大量集合元素|显式 owned table；生命周期由 Root 管理|
|INLINE_COLUMNS|小型、固定、不可独立查询的值对象|SC-02 展开为列|
|JSONB_CANDIDATE|Provider/Manifest/策略快照等形状受版本化 Schema 控制、查询需求低的结构|SC-02 逐项决定；不得把 ProjectId/Scope/状态/核心 FK 藏进 JSONB|
|FILE_REF|文档正文、生成制品、超大解析/AI/图形内容|保存 DocumentVersion/FileObject/Artifact 引用，不保存绝对路径|

默认使用关系表。只有同时满足“结构版本化、无核心约束、低查询、无跨行唯一”的数据才保留 JSONB 候选；不能把 JSONB 当成逃避 Schema 设计的容器。

## 多态引用策略

### 固定目标类型

已知目标类型的关系使用直接 FK 候选，例如 DocumentVersion→Document、RequirementVersion→Requirement、PlanVersion→Plan。SC-02 必须优先提供数据库完整性和同 Project 保护。

### 跨模块多态目标

ReviewSubject、TraceLink、AuditEvent、OutboxEvent、EvidenceBinding Subject、AITask accepted target 等确需多态目标时，使用一致的 discriminated reference 列组候选：

```text
target_owner_module
target_object_type
target_object_id
target_version_id        # 需要固定版本时必填
target_project_id        # PROJECT 目标的授权快照
```

- 不建立全局 `object_registry` 表，避免形成所有模块共同写入的新 Root 和热点。
- 多态引用由调用目标 Owner Port 验证，数据库使用受控 discriminator、必填组合、Scope/ProjectId CHECK 和必要的影子引用索引保护。
- SC-02 明确每种多态引用允许的 object_type 白名单；不能接受任意字符串类型。
- 删除目标不会级联删除 Review/Trace/Audit/Event；Retention 服务在物理清理前反向检查保护引用。

## 65 个 Aggregate Root 映射

### Platform / Security

|Root ID|Aggregate Root|Primary table|Owned tables / collection|映射说明|
|---|---|---|---|---|
|PLT-01|SystemConfiguration|`plt_system_configurations`|`plt_configuration_versions`、`plt_configuration_settings`、`plt_retention_policies`、`plt_retention_holds`|Active 配置指针与不可变配置版本分离；Hold 独立可检索|
|PLT-02|SecretRecord|`plt_secret_records`|`plt_secret_versions`|密文版本独立；明文不落业务表|
|AUT-01|User|`auth_users`|`auth_password_credentials`|账户身份与凭据版本分离|
|AUT-02|Session|`auth_sessions`|无强制 child table；CSRF/失效摘要为列候选|不透明 Token 仅保存摘要|
|PRJ-01|Project|`prj_projects`|无强制 child table|不保存 current stage 副本|
|PRJ-02|ProjectMember|`prj_project_members`|无强制 child table|User/Project/Role/Department 明确列|
|PRJ-03|Department|`prj_departments`|无强制 child table|项目内编码唯一留待 SC-02|
|WFL-01|ProjectWorkflow|`wfl_project_workflows`|`wfl_stages`、`wfl_stage_checklists`、`wfl_checklist_items`|Workflow 唯一拥有 current stage|
|WFL-02|StageTransition|`wfl_stage_transitions`|`wfl_transition_gate_items`|Append-only；GateSnapshot 拆为可查询项|
|RVW-01|Review|`rvw_reviews`|无强制 child table|保存逻辑主题多态引用|
|RVW-02|ReviewRound|`rvw_review_rounds`|`rvw_review_assignments`、`rvw_review_decisions`、`rvw_subject_snapshots`|固定主题版本、指纹、Evidence/Trace 快照|
|AUD-01|AuditEvent|`aud_events`|无强制 child table；before/after 为受限 JSONB 候选|Append-only，不存正文/Secret|
|LIC-01|LicenseInstallation|`lic_installations`|`lic_installation_documents`|保存签名 License 文档引用/快照，不含私钥|
|LIC-02|LicenseValidationState|`lic_validation_states`|`lic_validation_events`|当前安全状态与不可变验证事件分离|
|LIC-03|TrustedTimeState|`lic_trusted_time_states`|`lic_trusted_time_events`|当前单调状态 + 追加检查事件|

### Document / Evidence / Trace

|Root ID|Aggregate Root|Primary table|Owned tables / collection|映射说明|
|---|---|---|---|---|
|DOC-01|Document|`doc_documents`|无强制 child table|逻辑身份与 latest/effective Version FK 候选|
|DOC-02|DocumentVersion|`doc_document_versions`|`doc_version_source_refs`|不可变版本；正文经 FileObject|
|DOC-03|FileObject|`doc_file_objects`|`doc_file_state_events`|Locator/Hash/Size/MIME 与恢复状态|
|DOC-04|ParseRecord|`doc_parse_records`|`doc_parse_result_refs`|每个 Attempt 独立 Root 行；大结果使用受控引用|
|EVD-01|Evidence|`evd_evidence_records`|`evd_locator_parts`（类型化拆表候选）|Locator 核心类型/版本为列；类型细节由 SC-02 选择列/JSONB/子表|
|EVD-02|EvidenceBinding|`evd_bindings`|无强制 child table|Evidence FK + Subject 多态 Version Ref|
|TRC-01|TraceLink|`trc_links`|无强制 child table|source/target 多态 Version Ref；历史 supersede|

### Job / AI / RAG

|Root ID|Aggregate Root|Primary table|Owned tables / collection|映射说明|
|---|---|---|---|---|
|JOB-01|Job|`job_jobs`|`job_attempts`、`job_leases`、`job_checkpoints`|Root 持当前状态；Attempt/Lease 历史独立|
|JOB-02|OutboxEvent|`job_outbox_events`|`job_event_deliveries`、`job_event_consumptions`|Outbox 至少一次；消费去重记录归 jobs Owner|
|AI-01|AIProvider|`ai_providers`|`ai_provider_config_versions`|Secret 只保存 SecretRef|
|AI-02|AIModel|`ai_models`|`ai_model_capabilities`、`ai_quality_profile_refs`|Embedding Dimension 为核心列候选|
|AI-03|PromptTemplate|`ai_prompt_templates`|`ai_prompt_versions`|Active pointer 与不可变 PromptVersion 分离|
|AI-04|AITask|`ai_tasks`|`ai_task_input_refs`、`ai_invocations`、`ai_invocation_context_refs`、`ai_egress_authorization_snapshots`|Invocation 是 Root 内 Attempt；大 payload 为受权内容引用|
|RAG-01|DocumentChunk|`rag_document_chunks`|`rag_chunk_metadata`（关系/JSONB 候选）|正文可受控存储；来源 Locator/Version 核心列化|
|RAG-02|EmbeddingIndex|`rag_embedding_indexes`|`rag_index_source_versions`、`rag_index_validation_results`|Index generation、模型/维度/Scope 固定|
|RAG-03|EmbeddingRecord|`rag_embedding_records`|无强制 child table|向量物理列在 SC-03；Index/Chunk 一致|
|RAG-04|RetrievalRun|`rag_retrieval_runs`|`rag_retrieval_candidates`、`rag_context_bundles`、`rag_context_items`、`rag_retrieval_score_parts`|候选顺序/分数可查询；Context 最小化|

### Capability / Handover / Survey

|Root ID|Aggregate Root|Primary table|Owned tables / collection|映射说明|
|---|---|---|---|---|
|CAP-01|CapabilityBaseline|`cap_baselines`|无强制 child table|GLOBAL 逻辑身份与 approved pointer|
|CAP-02|BaselineVersion|`cap_baseline_versions`|`cap_items`、`cap_item_evidence_refs`、`cap_item_document_refs`|Item 是版本内实体；稳定 item identity 字段保留|
|HND-01|HandoverAnalysis|`hnd_analyses`|无强制 child table|PROJECT 逻辑身份|
|HND-02|HandoverAnalysisVersion|`hnd_analysis_versions`|`hnd_analysis_items`、`hnd_item_evidence_refs`、`hnd_item_capability_refs`、`hnd_item_options`|NeedConfirm 的问题/提示/选项结构化|
|HND-03|ActionItem|`hnd_action_items`|`hnd_action_response_refs`、`hnd_action_evidence_refs`、`hnd_action_state_events`|Submitted/Verified/Closed 可审计|
|SRV-01|Survey|`srv_surveys`|无强制 child table|逻辑调研身份|
|SRV-02|SurveyVersion|`srv_survey_versions`|`srv_questions`、`srv_question_options`、`srv_question_source_refs`、`srv_target_departments`|问题顺序、验证、来源可查询|
|SRV-03|SurveyRound|`srv_rounds`|`srv_round_source_records`|绑定固定 SurveyVersion 与实际调研记录|
|SRV-04|SurveyAssignment|`srv_assignments`|`srv_responses`、`srv_answers`、`srv_answer_evidence_refs`|保留原答复、修正链和录入主体|
|SRV-05|SurveyConclusion|`srv_conclusions`|`srv_department_conclusions`、`srv_module_conclusions`、`srv_conclusion_evidence_refs`、`srv_conclusion_open_issues`|series/version 语义在 Root 表显式列化|

### Requirement / Prototype

|Root ID|Aggregate Root|Primary table|Owned tables / collection|映射说明|
|---|---|---|---|---|
|REQ-01|RequirementPackage|`req_packages`|`req_package_memberships`|只保存同项目 Requirement 成员关系，不级联|
|REQ-02|Requirement|`req_requirements`|无强制 child table|逻辑身份、分类导航与 approved pointer|
|REQ-03|RequirementVersion|`req_requirement_versions`|`req_sources`、`req_acceptance_criteria`、`req_capability_assessments`、`req_assumptions`、`req_exclusions`、`req_dependencies`|正式分类、能力匹配、来源和验收结构化|
|REQ-04|RequirementRelation|`req_relations`|无强制 child table|固定两端 Version；受控图关系|
|PRT-01|PrototypePackage|`prt_packages`|`prt_package_memberships`|只组织同项目 Prototype|
|PRT-02|Prototype|`prt_prototypes`|无强制 child table|支持 NOT_REQUIRED 决策字段|
|PRT-03|PrototypeVersion|`prt_prototype_versions`|`prt_version_artifact_refs`、`prt_version_requirement_refs`、`prt_interaction_specs`|制品、需求、TemplateVersion 固定|
|PRT-04|PrototypeTemplate|`prt_templates`|`prt_template_versions`、`prt_template_artifact_refs`|GLOBAL/PROJECT 创建时定 Scope|
|PRT-05|RequirementPrototypeLink|`prt_requirement_links`|无强制 child table|两端固定版本、Purpose/Coverage|

### Solution / Plan

|Root ID|Aggregate Root|Primary table|Owned tables / collection|映射说明|
|---|---|---|---|---|
|SOL-01|ReferenceSolution|`sol_reference_solutions`|`sol_reference_versions`、`sol_reference_document_refs`、`sol_reference_evidence_refs`|参考资料与项目正式方案分离|
|SOL-02|SolutionOutline|`sol_outlines`|无强制 child table|逻辑目录与 approved pointer|
|SOL-03|SolutionOutlineVersion|`sol_outline_versions`|`sol_outline_sections`、`sol_outline_requirement_refs`、`sol_outline_reference_refs`|章节顺序使用显式 ordinal|
|SOL-04|SolutionSection|`sol_sections`|无强制 child table|Outline 内 section_key 唯一候选|
|SOL-05|SolutionSectionVersion|`sol_section_versions`|`sol_section_requirement_refs`、`sol_section_evidence_refs`、`sol_section_spec_refs`|正文用受控内容引用；映射/证据结构化|
|SOL-06|StructuredSolutionSpec|`sol_structured_specs`|`sol_spec_requirement_refs`、`sol_spec_section_refs`、`sol_spec_evidence_refs`、`sol_spec_artifact_refs`|四类专项共用 Root，类型白名单；payload 为类型化表/JSONB 候选|
|PLN-01|Plan|`pln_plans`|无强制 child table|逻辑计划与 approved pointer|
|PLN-02|PlanVersion|`pln_plan_versions`|`pln_wbs_items`、`pln_wbs_dependencies`、`pln_milestones`、`pln_item_requirement_refs`、`pln_item_solution_refs`、`pln_item_evidence_refs`|最多六级、仅 FS、同版本 DAG|
|PLN-03|ReferencePlan|`pln_reference_plans`|`pln_reference_versions`、`pln_reference_document_refs`|解析映射与参考身份分离|

### Output / Plugin

|Root ID|Aggregate Root|Primary table|Owned tables / collection|映射说明|
|---|---|---|---|---|
|OUT-01|OutputRequest|`out_requests`|`out_context_snapshots`、`out_context_source_refs`、`out_context_evidence_refs`|固定源版本与模板/策略，不存动态 current ref|
|OUT-02|OutputArtifact|`out_artifacts`|`out_artifact_validation_results`|FileObject/DocumentVersion/Execution/Hash 完整后可用|
|PLG-01|PluginPackage|`plg_packages`|`plg_manifest_operations`、`plg_manifest_dependencies`、`plg_package_verifications`|Manifest 核心能力结构化；原始快照可 JSONB|
|PLG-02|PluginInstallation|`plg_installations`|`plg_enabled_operations`、`plg_runtime_validations`|同 plugin/operation 最多一个 Enabled 留待 SC-02|
|PLG-03|PluginExecution|`plg_executions`|`plg_execution_result_files`、`plg_execution_state_events`|stdio/路径不入表；结果先暂存后登记|

## Root 映射统计

|检查项|结果|
|---|---:|
|客户运行 Aggregate Root|65|
|Root primary table|65|
|唯一 Owner prefix|22|
|Developer Workbench Root|3，客户 Schema 中为 0|
|未映射 Root|0|
|重复 primary table|0|

Owned table 数量是 SC-01 候选，不等于最终表总数；SC-02 可在不改变 Root/Owner/生命周期的前提下合并低价值 child table 或拆分需要强约束的值对象，并登记映射变更。

## Scope/ProjectId 物理映射原则

|逻辑 Scope|Root table 列候选|Child table 规则|
|---|---|---|
|DEPLOYMENT|不使用 project_id；可省略 scope 或固定部署语义|继承 Root；禁止客户正文|
|GLOBAL|`scope='GLOBAL'` 或由专用 Root 固定；project_id 必为空|Child 继承，不自行覆盖|
|PROJECT|project_id 为核心非空列；必要时参与复合 FK/唯一|高频授权/跨 Root child 显式冗余 project_id 并由复合约束保护|
|GLOBAL_OR_PROJECT|scope 核心列；GLOBAL 时 project_id 空，PROJECT 时非空|同 Root 一致；创建后不可切换|

是否在所有 PROJECT child table 冗余 project_id 按以下规则决定：

- 用于独立授权查询、跨 Root FK、大规模分区/索引或清理扫描：显式保存 project_id。
- 只在单 Root 内、始终通过父表访问、无跨 Root 引用：可仅保存 parent FK。
- 冗余 project_id 必须有数据库约束防漂移，不能只靠 ORM 赋值。

## Version 与 current pointer 映射

- 逻辑表保存 `current_approved_version_id`；需要编辑导航时可另有 `latest_version_id`，两者语义不得混用。
- Version primary table 保存 parent identity、version_no、content_fingerprint、version_state、created_by/at、supersedes_version_id。
- Review 状态不复制为可独立编辑的第二真相；可保存受控投影/缓存，但必须标明来源版本并可重建。
- current pointer 与目标 Version 的 parent/Scope/Approved 状态一致性在 SC-02 选择复合 FK、约束触发器或事务内验证方案。
- 历史业务引用、Evidence、Trace、Output Context 一律指向 Version primary key，不指向 current pointer。

## 内容与敏感数据放置

|内容|物理位置候选|禁止事项|
|---|---|---|
|用户上传/生成文件正文|本地文件系统 + `doc_file_objects` Locator/Hash|数据库 bytea 大文件、绝对路径返回客户端|
|Evidence 显示摘录|`evd_evidence_records` 受限短字段或可重建缓存|把摘录当权威正文|
|AI Prompt/结果/Context|受权数据库大字段或 Document/File Ref，SC-02 决定|普通日志、Outbox/Event Payload、无期限复制|
|Embedding Vector|`rag_embedding_records` 的 pgvector 列，SC-03 决定维度/索引|跨模型复用、混合维度|
|Plugin Manifest/Provider metadata|核心字段关系化 + 原始版本快照 JSONB 候选|把入口、签名、权限白名单只藏在不可约束 JSON|
|Secret|`plt_secret_versions` 加密密文 + SecretRef|明文、普通 YAML、Job、Audit、Plugin Context|
|Session/CSRF|摘要/版本/期限列|原始 Token、localStorage 长期凭据|
|Audit before/after|脱敏摘要 JSONB 候选|文件正文、Prompt/响应、Secret、Session 标识|

## 反向引用与删除边界

- Root/Version/Document/File 的物理删除默认 `RESTRICT/NO ACTION`；不以 FK CASCADE 穿越 Aggregate 边界。
- 只允许 Root-owned、非历史、非审计且没有独立引用的 child 使用受控 CASCADE 候选；SC-02 逐表白名单。
- Package membership 删除只移除 membership 行，不删除成员 Root。
- Review/Trace/Evidence/Audit/Event 对目标使用保护引用；多态引用无法普通 FK 时由 Retention 反向索引/查询 + Application Guard 保护。
- FileObject 物理清理必须同步验证 DocumentVersion、Evidence、RAG、Artifact、Review/Trace 和 Hold，不允许数据库级联删除文件内容。

## SC-02 输入清单

1. 为 65 个 primary table 选择 PK 类型、创建/更新时间、lock_version、状态和 Scope 列。
2. 为 Version 表统一 parent FK、version_no、fingerprint、supersedes、不可变和 current pointer 约束。
3. 为 PROJECT/GLOBAL_OR_PROJECT 表定义 project_id NOT NULL/CHECK/复合 FK 规则。
4. 为固定类型关系定义 FK 与删除动作；为多态引用定义 discriminator 白名单和列组合 CHECK。
5. 为 User/Member/Workflow/Review/Secret/Index/Plugin activation 等单一有效记录定义唯一策略。
6. 为 locator、manifest、payload、snapshot 确定关系列与 JSONB 边界及 Schema 校验。
7. 为 WBS/Trace/Requirement 图定义写入期无环边界；不使用无限递归触发器替代 Application 校验。
8. 对所有表/约束/索引生成名执行 PostgreSQL 63-byte 检查。

## 风险与关闭条件

|Risk ID|风险|当前决定|关闭条件|
|---|---|---|---|
|SC1-R01|单一 Schema 被误解为允许跨模块 Repository|模块前缀 + Owner/Port 规则；不授予模块级 DB 用户假隔离|代码结构/Review 规则在基础工程验证|
|SC1-R02|多态引用缺少普通 FK|不建全局 registry；白名单 discriminator + Scope 快照 + Owner Port|SC-02/API 集成测试覆盖悬空/越权|
|SC1-R03|Owned table 过度拆分导致表数和 Join 膨胀|只对查询/唯一/状态/大量集合拆表；其余列/JSONB 候选|SC-02 字段级评审与关键查询样例|
|SC1-R04|JSONB 隐藏核心约束|ProjectId/Scope/状态/FK/排序/关键过滤禁止仅存 JSONB|SC-02 列映射扫描 0 违规|
|SC1-R05|表/约束名超过 PostgreSQL 63 bytes|短 Prefix，表名目标≤55 字符|SC-02 自动名称长度测试|
|SC1-R06|Developer Workbench 被误建到客户库|客户 Schema 映射明确为 0 个 Workbench Root|SC-04 空库清单验证|

## SC-01 验收

- 单一客户数据库、`plm` 应用 Schema、模块短前缀和 Developer Workbench 物理隔离明确：PASS。
- 22 个 Owner 均有唯一短前缀，ASCII lower_snake_case 与 55/63-byte 命名规则明确：PASS。
- 65 个 Aggregate Root 均映射唯一 primary table，未映射 0、重复 0：PASS。
- 逻辑身份、不可变 Version、current approved pointer 和历史引用的表边界明确：PASS。
- 固定 FK 与多态引用分流，不新增全局共享写 `object_registry`：PASS。
- Scope/ProjectId 在 Root/child 的物理映射和冗余条件明确：PASS。
- Root/Child/Inline/JSONB/File Ref 五种存储策略及禁止项明确：PASS。
- 文件、Evidence、AI/RAG、Secret、Session、Audit 等敏感内容放置边界明确：PASS。
- 默认 RESTRICT、Package 不级联、保护引用和 FileObject 清理边界明确：PASS。
- 六项 SC-01 风险均登记关闭条件，未提前定义类型、约束、索引或 Migration：PASS。

## 下一步

SC-02：为本映射确定 PostgreSQL 18 字段类型、PK/FK、Scope/ProjectId、版本、唯一、CHECK、不可变和乐观并发约束。
