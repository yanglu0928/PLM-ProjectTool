# PLM 项目实施辅助工具 DB Schema Candidate V1

## 状态

`DB-SCHEMA-CANDIDATE-V1 / SC-01～SC-05_PASS / GATE_2_APPROVED / DESIGN_FROZEN / NO_PRODUCTION_MIGRATION / NO_BUSINESS_CODE`

本文件是 SC-01～SC-04 的单一汇总，统一 PostgreSQL 18 + pgvector 的物理组织、65 个 Aggregate Root 映射、字段 Profile、完整性约束、索引与关键查询、Migration/恢复边界、未关闭风险及 API Contract 输入。它已于 2026-09-23 在 Gate 2 冻结为 DB Schema V1 设计基线，冻结内容固定为提交 `64cdf09`；候选标识为保持历史 Trace 不重命名。它仍不是已部署的生产 Schema，SC-04 仍只是验证性 Migration。

## 候选标识与规范来源

|项目|值|
|---|---|
|Candidate ID|`DB-SCHEMA-CANDIDATE-V1`|
|Target Database|PostgreSQL 18 + pgvector|
|Application Schema|`plm`|
|Migration Tool|Alembic + SQLAlchemy 2.x|
|Root Count|65|
|Owner Module Count|22|
|Critical Query Count|20|
|Gate|Gate 2 `APPROVED`（2026-09-23）|

本文件统一结论优先；下列文件提供受控明细，未被本文件明确改变的内容继续有效：

1. `sc-01-logical-physical-map-v1-candidate.md`：Root/owned table、Owner、内容放置和删除边界。
2. `sc-02-field-types-constraints-v1-candidate.md`：类型、Profile、Scope/ProjectId、唯一、FK、CHECK 和写保护。
3. `sc-03-index-query-plan-v1-candidate.md`：索引 Profile、29 个物理唯一键、20 个 Query ID 和查询模板。
4. `sc-04-migration-recovery-validation.md`：验证性 Migration、Windows 11 实测证据和已知限制。
5. `validation/sc-04-database-schema/schema_manifest.py`：65 个 Root 与 20 个 Query ID 的机器可读清单。

如果明细文件之间存在表述差异，执行优先级为：用户最新明确变更 > 本候选统一结论 > 已冻结 ADR/Data Model > SC-01～SC-04 后续阶段结论 > 较早阶段假设。不得用验证性最小列覆盖正式业务字段设计。

## 物理架构与边界

- 客户运行数据使用单一 PostgreSQL 数据库和 `plm` Schema；`public` 不承载应用表。
- 22 个模块以短前缀表达数据 Owner；同处一个 Schema 不代表允许跨模块 Repository 直接写表。
- Developer Workbench 的 License/Plugin/Release 签名记录使用独立数据库或独立开发者部署，客户 `plm` Schema 中为 0 个 Workbench Root。
- 文件正文、Plugin 工作区和生成制品位于受控本地文件系统；数据库保存相对 Locator、Hash、大小、MIME、状态和引用。
- 业务 PK 使用 `uuid DEFAULT uuidv7()`；时间使用 UTC `timestamptz(6)`；计划日历使用 `date`。
- 状态和受控类型使用 `text + named CHECK`，不使用 PostgreSQL ENUM；V1 不创建 PostgreSQL DOMAIN。
- V1 不依赖 RLS。ProjectAuthorizationService 是主授权边界，显式 `project_id`、复合 FK/唯一约束和权限测试提供数据库防漂移。
- 跨 Aggregate 删除默认 `NO ACTION`，不使用跨聚合 CASCADE；Retention Service 在物理清理前检查 Hold、保护引用、活动 Job/Lease、Outbox 和文件状态。
- V1 不使用按 Project 动态分区、每项目 HNSW、Runtime DDL、Redis、消息队列或独立向量库。

## 65 个 Root 物理清单

|Root ID|Primary table|Primary key|Profile|
|---|---|---|---|
|PLT-01|`plt_system_configurations`|`system_configuration_id`|M-DEP|
|PLT-02|`plt_secret_records`|`secret_record_id`|SEC-DEP|
|AUT-01|`auth_users`|`user_id`|M-DEP|
|AUT-02|`auth_sessions`|`session_id`|R-DEP|
|PRJ-01|`prj_projects`|`project_id`|M-DEP|
|PRJ-02|`prj_project_members`|`project_member_id`|M-PRJ|
|PRJ-03|`prj_departments`|`department_id`|M-PRJ|
|WFL-01|`wfl_project_workflows`|`workflow_id`|M-PRJ|
|WFL-02|`wfl_stage_transitions`|`stage_transition_id`|A-PRJ|
|RVW-01|`rvw_reviews`|`review_id`|M-SCP|
|RVW-02|`rvw_review_rounds`|`review_round_id`|A-SCP|
|TRC-01|`trc_links`|`trace_link_id`|A-SCP|
|AUD-01|`aud_events`|`audit_event_id`|A-DEP|
|LIC-01|`lic_installations`|`license_installation_id`|SEC-DEP|
|LIC-02|`lic_validation_states`|`license_validation_state_id`|SEC-DEP|
|LIC-03|`lic_trusted_time_states`|`trusted_time_state_id`|SEC-DEP|
|DOC-01|`doc_documents`|`document_id`|M-SCP|
|DOC-02|`doc_document_versions`|`document_version_id`|V-SCP|
|DOC-03|`doc_file_objects`|`file_object_id`|M-SCP|
|DOC-04|`doc_parse_records`|`parse_record_id`|R-SCP|
|EVD-01|`evd_evidence_records`|`evidence_id`|M-SCP|
|EVD-02|`evd_bindings`|`evidence_binding_id`|A-SCP|
|JOB-01|`job_jobs`|`job_id`|R-SCP|
|JOB-02|`job_outbox_events`|`outbox_event_id`|A-SCP|
|AI-01|`ai_providers`|`ai_provider_id`|M-DEP|
|AI-02|`ai_models`|`ai_model_id`|M-DEP|
|AI-03|`ai_prompt_templates`|`prompt_template_id`|M-DEP|
|AI-04|`ai_tasks`|`ai_task_id`|R-SCP|
|RAG-01|`rag_document_chunks`|`chunk_id`|M-SCP|
|RAG-02|`rag_embedding_indexes`|`embedding_index_id`|M-SCP|
|RAG-03|`rag_embedding_records`|`embedding_record_id`|R-SCP|
|RAG-04|`rag_retrieval_runs`|`retrieval_run_id`|R-SCP|
|CAP-01|`cap_baselines`|`baseline_id`|M-GLB|
|CAP-02|`cap_baseline_versions`|`baseline_version_id`|V-GLB|
|HND-01|`hnd_analyses`|`handover_analysis_id`|M-PRJ|
|HND-02|`hnd_analysis_versions`|`handover_analysis_version_id`|V-PRJ|
|HND-03|`hnd_action_items`|`action_item_id`|M-PRJ|
|SRV-01|`srv_surveys`|`survey_id`|M-PRJ|
|SRV-02|`srv_survey_versions`|`survey_version_id`|V-PRJ|
|SRV-03|`srv_rounds`|`survey_round_id`|M-PRJ|
|SRV-04|`srv_assignments`|`survey_assignment_id`|M-PRJ|
|SRV-05|`srv_conclusions`|`survey_conclusion_id`|V-PRJ|
|REQ-01|`req_packages`|`requirement_package_id`|M-PRJ|
|REQ-02|`req_requirements`|`requirement_id`|M-PRJ|
|REQ-03|`req_requirement_versions`|`requirement_version_id`|V-PRJ|
|REQ-04|`req_relations`|`requirement_relation_id`|A-PRJ|
|PRT-01|`prt_packages`|`prototype_package_id`|M-PRJ|
|PRT-02|`prt_prototypes`|`prototype_id`|M-PRJ|
|PRT-03|`prt_prototype_versions`|`prototype_version_id`|V-PRJ|
|PRT-04|`prt_templates`|`prototype_template_id`|M-SCP|
|PRT-05|`prt_requirement_links`|`requirement_prototype_link_id`|A-PRJ|
|SOL-01|`sol_reference_solutions`|`reference_solution_id`|M-SCP|
|SOL-02|`sol_outlines`|`solution_outline_id`|M-PRJ|
|SOL-03|`sol_outline_versions`|`solution_outline_version_id`|V-PRJ|
|SOL-04|`sol_sections`|`solution_section_id`|M-PRJ|
|SOL-05|`sol_section_versions`|`solution_section_version_id`|V-PRJ|
|SOL-06|`sol_structured_specs`|`structured_solution_spec_id`|V-PRJ|
|PLN-01|`pln_plans`|`plan_id`|M-PRJ|
|PLN-02|`pln_plan_versions`|`plan_version_id`|V-PRJ|
|PLN-03|`pln_reference_plans`|`reference_plan_id`|M-SCP|
|OUT-01|`out_requests`|`output_request_id`|R-PRJ|
|OUT-02|`out_artifacts`|`output_artifact_id`|M-PRJ|
|PLG-01|`plg_packages`|`plugin_package_id`|SEC-DEP|
|PLG-02|`plg_installations`|`plugin_installation_id`|M-DEP|
|PLG-03|`plg_executions`|`plugin_execution_id`|R-PRJ|

每个 Root 恰好一个 primary table。Owned table 的候选清单继续以 SC-01 为规范明细；Gate 2 后按模块生成正式 ORM/Migration 时，只有需要独立查询、唯一、顺序、状态、引用或大集合的值才拆表。SC-04 仅实现 5 个代表性 owned table，不代表其余 owned table 已完成生产 DDL。

## 字段 Profile 与类型契约

|Profile|用途|强制语义|
|---|---|---|
|M-DEP / M-GLB / M-PRJ / M-SCP|可变逻辑身份|状态、created/updated、actor、`lock_version`、Retention；按 Scope 增加 Project 约束|
|V-GLB / V-PRJ / V-SCP|不可变版本|parent/series、`version_no`、fingerprint、supersedes、creator/time；送审后内容只读|
|A-DEP / A-PRJ / A-SCP|追加式事实|created/actor/trace；无通用 updated/lock；更正通过 replacement/supersede/revoke|
|R-DEP / R-PRJ / R-SCP|可重试运行记录|state、attempt/correlation、started/completed、error/retry、lock/fencing、Retention|
|SEC-DEP|签名或安全状态|签名/Hash/credential version、验证时间、Audit 引用；失败不能用通用更新伪装成功|

统一基础类型：ID/FK=`uuid`，时间=`timestamptz(6)`，计划日期=`date`，乐观锁/fencing=`bigint`，文件大小/Token=`bigint`，Hash=`bytea` 并检查长度，快照=`jsonb` 并检查类型/版本，分数=`double precision` 且应用拒绝 NaN/Infinity，向量仅位于 RAG Embedding 记录并与 Index dimension 一致。

## Scope、授权与引用约束

- PROJECT Root：`project_id NOT NULL`，FK 到 `prj_projects`，并提供 `(root_id, project_id)` 复合唯一供跨表复合 FK 使用。
- GLOBAL_OR_PROJECT Root：`scope IN ('GLOBAL','PROJECT')`；GLOBAL 必须 `project_id IS NULL`，PROJECT 必须非空；Scope 创建后不可切换。
- 高频授权、跨 Root 引用、独立清理的 child 显式保存 `project_id`，并以复合 FK 防止跨项目漂移。
- 固定目标关系使用普通 FK；Review/Evidence/Trace/Audit/Event/AI accepted target 等多态引用使用受控 owner/type/id/version/project 列组和白名单。
- 不建立全局共享写 `object_registry`。多态目标存在性、状态和权限由目标 Owner Port 验证，Retention 通过双向反查保护目标。
- 无权、无资源和跨项目访问在外部 API 使用相同不泄露语义；uuidv7 不能被当作授权凭据。

## 版本、并发与删除契约

- identity 的 `current_approved_version_id` 与可选 `latest_version_id` 语义分离；正式历史引用只指向固定 Version ID。
- Version 通过 parent/Project 复合 FK 防串用，`(parent_id, version_no)` 唯一；Approved/current 状态由 Owner Command + 必要的约束触发器验证。
- Mutable Root 更新必须携带 `expected_version` 并原子增加 `lock_version`；影响 0 行映射为统一 Not Found/Forbidden/Conflict 语义，不泄露资源存在性。
- Version 内容和 owned child 在 IN_REVIEW/APPROVED 后禁止普通修改；Append-only 表禁止普通 UPDATE/DELETE。
- 图关系必须同 Project/Version，Requirement/Trace/WBS 写入前验证无环；WBS 层级 1..6，依赖类型仅 FS。
- 物理清理必须满足到期、无 Active Hold、无保护引用、无活动 Job/Lease、无未完成 Outbox、文件状态可清理六类前置；跨聚合 FK 不级联。

## 安全字段契约

- Password 只保存自描述 hash；禁止明文密码列。
- Session/CSRF 只保存 digest、credential version、期限与撤销状态；禁止原始 Token。
- Secret 只保存加密 payload、算法/nonce/tag 和 SecretRef；主密钥与明文不进入业务库。
- License 保存签名文档/公钥引用和机器指纹 Hash；Ed25519 私钥只在开发者工作台。
- FileObject 使用受控相对 Locator、SHA-256、大小和 MIME；API 不返回服务器绝对路径。
- AI/Plugin/Audit/Outbox/普通日志不得复制 Secret、完整客户正文、Prompt/响应或 Session 标识。
- Migration Owner、Runtime Role、Maintenance/Recovery Role 分离；Runtime Role 不得 DDL、修改 Alembic 版本、禁用触发器或更改 `search_path`。

## 唯一、索引与查询契约

- SC-02 的 28 组唯一语义映射为 29 个物理唯一键；regular unique 复用其索引，条件唯一使用常量 partial predicate。
- 引用侧 FK 必须有完整列组左前缀 B-tree，除非以容量证据显式豁免。
- PROJECT 列表使用 `project_id` 前缀和 `(sort_time DESC, root_id DESC)` keyset；不以大 Offset 作为正式主路径。
- Job/Outbox 使用短事务、稳定排序、`FOR UPDATE SKIP LOCKED`、Lease fencing 和幂等唯一键；只承诺至少一次处理。
- Audit/Review/Evidence/Trace 提供项目、对象、source/target 双向索引；索引不能绕过授权。
- 中文 FTS 使用 Application 生成的受控 Token `search_body`、stored `tsvector` 和 GIN；不假设 PostgreSQL `simple` 自动中文分词。
- 向量使用按受支持维度由 Migration 创建的 HNSW 表达式索引。查询强制 Scope/Project/EmbeddingIndex；候选不足时只在同授权范围扩大扫描或精确回退。
- Index Model、dimension、Chunk Profile 或 normalization 不兼容变化必须新建 EmbeddingIndex 并全量重建；`vector` 超过 2,000 维默认不兼容，替代方案需质量 PoC 和 Gate 变更。

### 20 个关键 Query ID

|领域|Query IDs|
|---|---|
|Auth/Project/Workflow|Q-AUTH-01、Q-PRJ-01、Q-PRJ-02、Q-WFL-01|
|Version/Review/Document/Evidence/Trace/Audit|Q-VER-01、Q-RVW-01、Q-DOC-01、Q-EVD-01、Q-TRC-01、Q-AUD-01|
|Job/Outbox/Retention|Q-JOB-01、Q-JOB-02、Q-OUT-01、Q-RET-01|
|RAG|Q-RAG-01、Q-RAG-02|
|Graph/Plugin/Output|Q-REQ-01、Q-WBS-01、Q-PLG-01、Q-OUTPUT-01|

每个 Query ID 的过滤、排序、索引 Profile 和候选 SQL 以 SC-03 为规范明细。API Contract 必须将这些查询映射到受权 Application Port，不得直接暴露数据库查询能力。

## Migration 与恢复契约

1. 所有生产 Schema 变更只通过 Alembic；`plm.alembic_version` 位于应用 Schema。
2. 每次正式数据库变更必须同时包含 ORM、Migration、up/down、空库、有数据升级、约束/索引漂移和备份恢复验证。
3. Migration revision 一经进入发行基线不得原地改写；变更通过新 revision。
4. 状态 CHECK/partial predicate/Repository 固定状态集合必须来自同一受控常量源，并在 Schema introspection 中比较。
5. 正式 Migration 必须逐表生成明确 trigger/constraint，不使用接收任意 SQL 的通用动态触发器。
6. 批量索引/Embedding generation 先构建并验证新 generation，再原子切换 Active pointer；旧 generation 按 Retention 保留。
7. `pg_dump -Fc`/`pg_restore`、文件元数据和本地文件系统恢复必须在 Release 流程形成一致性演练；不能只恢复数据库而忽略文件正文。
8. `validation/sc-04-database-schema` 是 `VALIDATION_ONLY` 机制证据。其 70 表/5 个代表 child、32 维向量和两级 revision 不得直接复制为生产基线。

## SC-04 验证证据

|项目|Windows 11 结果|结论边界|
|---|---|---|
|Manifest|65 Root、20 Query、217 标识符 PASS|Root/Profile/命名机制|
|SQLAlchemy metadata|70 表 PASS|65 Root + 5 代表 child，不是全量生产表|
|Alembic|空库及有数据 up/down PASS|验证 revision，不是生产 revision|
|约束负例|10/10 被数据库拒绝|代表性 Scope/FK/unique/vector/append-only|
|计划|Job、Audit、GIN、HNSW 物理探针 PASS|小强过滤集合正确走 `EXACT_FILTERED_FALLBACK`|
|并发|20/20 Worker 唯一领取|未完成正式崩溃/饥饿长期负载|
|Retention/Hold|候选发现与阻断 PASS|未覆盖 65 Root 全量文件清理链|
|恢复|65 Root + 测试 Document 恢复 PASS|未操作客户文件正文|
|敏感扫描|禁止列名/Secret-like 值 0|需在正式 Migration 持续执行|

Windows Server 2025 继承 POC-02 的 PostgreSQL/pgvector/Alembic 可行性证据，本轮 SC-04 未重跑。Debian 13 按用户批准方案跳过，作为 Release 前明确兼容性约束，不得写成已实机验证。

## 统一未关闭风险

|Risk ID|风险|状态|关闭位置|
|---|---|---|---|
|DB-R01|单一 Schema 被误用为跨模块直写|CONTROLLED_OPEN|基础工程依赖测试、代码审查|
|DB-R02|多态引用无法使用普通目标 FK|CONTROLLED_OPEN|API Owner Port、悬空/跨项目/Retention 集成测试|
|DB-R03|非关键 Root 仅有 Profile 最小列，owned table 未形成全量生产 DDL|CONTROLLED_OPEN|Gate 2 后逐模块 ORM/Migration 任务|
|DB-R04|无 RLS 时 Repository 漏写 Project 过滤|CONTROLLED_OPEN|API Permission 矩阵、查询 lint、跨项目负测|
|DB-R05|Approved pointer、Version child 锁定只完成代表性验证|CONTROLLED_OPEN|正式 Migration 绕过 ORM 负测|
|DB-R06|Requirement/Trace/WBS 图成环或越 Scope|CONTROLLED_OPEN|Application 写入守卫、图属性测试|
|DB-R07|中文分词、tsquery 安全和真实 Recall 尚未在正式 API 数据上验证|CONTROLLED_OPEN|RAG 集成/Golden Dataset|
|DB-R08|正式 Embedding 维度、多项目偏斜、HNSW P95/build/memory 未验证|CONTROLLED_OPEN|Gate 3 性能与质量验证|
|DB-R09|Job/Outbox 崩溃回收、饥饿和旧 Worker 发布未跑长期负载|CONTROLLED_OPEN|Platform Core 并发/故障注入|
|DB-R10|65 Root 反向引用、文件正文和 Retention 清理顺序未全链演练|CONTROLLED_OPEN|文件/Retention 集成与 Release 恢复演练|
|DB-R11|正式索引大小、写放大、bloat 与 BRIN/分区阈值缺少容量证据|CONTROLLED_OPEN|性能环境；无证据不新增索引/分区|
|DB-R12|SC-04 未在 Server 重跑，Debian 未实机验证|RELEASE_CONSTRAINT|Server 回归；Debian 按批准方案登记 Release 风险|
|DB-R13|验证性 Alembic 不是正式生产 revision|CONTROLLED_OPEN|Gate 2 后正式 ORM/Migration review 与漂移测试|
|DB-R14|资源授权、错误语义、分页、DTO 和幂等头的冻结缺口|CLOSED_AT_GATE_2|`API-CONTRACT-CANDIDATE-V1`、API-05 Contract Lint|

这些风险不构成 Schema 候选内部冲突，但不得在关闭前宣称相应生产能力已验证。任何风险若需要修改 Scope/Owner、核心安全/License 机制、技术栈或新增基础设施，按 L3 Change Request 处理。

## API Contract V1 输入

API Contract V1 必须把以下数据库不变量提升为外部契约，不得要求客户端理解表名或内部 FK：

1. 所有 PROJECT 资源由路径/上下文明确 `project_id`；服务端从授权上下文验证，不信任 DTO 中重复的 ProjectId。
2. 版本化资源区分 identity、draft/latest 和 approved version；正式引用使用不可变 `version_id`，不得以“当前版本”动态替代。
3. Mutable Command 携带 `expected_version`；可重试 Command 携带 `idempotency_key`；所有写操作携带/返回 `trace_id`。
4. 列表使用不透明 keyset cursor、稳定排序和受控 page size；不暴露数据库 Offset 或内部执行计划。
5. 多态引用 DTO 使用 API 白名单的 `object_type` 与固定 `version_id`，服务端解析 Owner；不向客户端暴露 `owner_module` 实现细节。
6. 文件 API 返回 File/Document/Evidence 标识和授权下载能力，不返回 `storage_locator` 或服务器绝对路径。
7. AI/RAG 外发授权、Provider/Model/Prompt/Index generation 必须形成不可变快照；外发失败关闭，不复用其他轮次授权。
8. Job API 返回 JobId 和状态投影；Worker Lease/fencing、Outbox 和内部重试字段不直接开放修改。
9. Review/Approve/Reject、Archive、Retention/Cleanup、Plugin Enable/Execute 使用专用 Command；不得用通用 PATCH 绕过状态机。
10. Not Found/Forbidden/跨项目使用不泄露存在性的统一响应；Conflict 区分乐观锁、唯一冲突、状态冲突和幂等 payload 冲突。
11. 成功响应统一包含 `data` 与 `trace_id`；错误包含 `error.code`、`error.message` 与 `trace_id`，不返回 SQLSTATE、表名或 traceback。
12. SSE 只发布授权状态事件/进度摘要，不携带客户正文、Prompt/响应、Secret 或数据库内部字段。
13. 权限测试必须覆盖 Role × API × Project、固定版本读取、GLOBAL→PROJECT 引用和无权对象枚举。
14. API 实现必须通过所属 Application Port/Repository；禁止 Controller、跨模块 Service 或 Plugin 直接访问非 Owner 表。

## Gate 2 后正式实现要求

- 以模块为单位细化所有 Root/owned table 的业务列、状态白名单和约束，不把 SC-04 generic Profile 表直接转为生产表。
- 每个 WBS 只提交对应模块的 ORM、Alembic、Repository 和测试；不得一次生成全库后跳过业务评审。
- 用机器 manifest 校验 65 Root、Owner、Profile、Query ID、标识符、禁止字段和 Migration/ORM 漂移。
- 每项 Schema 变更执行空库、有数据 up/down、直接 SQL 负例、权限/跨项目测试和备份恢复影响评估。
- 正式性能结论只能来自代表性数据与环境；小表 Seq Scan、强过滤精确回退不自动判失败。
- 所有正式成果保留版本并通过 TraceLink 反向追溯；AI 建议经人工确认后才成为业务事实。

## SC-05 验收

- 单一候选标识、规范来源、冲突优先级和 Gate 边界明确：PASS。
- 22 个 Owner、65 个 Root primary table、PK 与 Profile 完整且无重复：PASS。
- Root/owned/JSONB/File Ref 和 Developer Workbench 隔离边界统一：PASS。
- PostgreSQL 类型、Scope/ProjectId、Version、并发、FK、删除和安全字段契约统一：PASS。
- 28 组唯一语义到 29 个物理唯一键、通用索引 Profile 和 20 个 Query ID 纳入候选：PASS。
- Job/Outbox、Audit/Trace/Evidence、Retention、中文 FTS 和 HNSW 查询边界统一：PASS。
- 验证性 Migration 与正式生产 ORM/Migration 边界明确：PASS。
- SC-04 Windows 11 证据及 Server/Debian 结论边界如实保留：PASS。
- 14 项统一风险具有当前控制、状态和关闭位置：PASS。
- API Contract V1 的身份、版本、授权、并发、分页、错误、Job、文件和 AI/RAG 输入明确：PASS。
- 未引入新技术栈、基础设施、Scope 或 Breaking API：PASS。
- Gate 2 批准前未创建正式业务 ORM/API/Migration，也未提前开始正式业务编码：PASS。

## 结论与下一步

`DB-SCHEMA-CANDIDATE-V1` 已在 2026-09-23 Gate 2 冻结为 DB Schema V1 正式设计基线。下一阶段按 Phase 1 WBS 逐模块生成生产 ORM 与 Alembic Migration，并执行空库、有数据 up/down、权限、漂移和恢复验证；不得把 SC-04 验证性 Profile 表直接发布为生产 Schema。冻结 Schema 的破坏性变化必须走 L3 Schema/API Change Request。
