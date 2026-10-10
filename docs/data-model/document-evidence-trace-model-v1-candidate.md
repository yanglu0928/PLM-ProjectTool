# Document / Evidence / Trace 数据模型 V1 候选

## 状态

`CANDIDATE / DM-03_COMPLETE / NOT_GATE_2_FROZEN / NOT_PHYSICAL_SCHEMA`

本文件细化 Document、DocumentVersion、FileObject、ParseRecord、Evidence、EvidenceBinding 与 TraceLink 的字段语义、关系、状态机和保留规则。它不固定 PostgreSQL 类型、物理表、索引、文件目录实现或 REST URL。

## 设计结论

1. Document 是逻辑身份；DocumentVersion 是不可变内容版本；FileObject 是受控物理内容元数据，三者分离。
2. FileObject 的数据库记录与本地文件系统不能形成单一原子事务，因此使用 STAGED/AVAILABLE/FAILED/CLEANUP_PENDING 状态和恢复审计，禁止暴露半完成版本。
3. ParseRecord 是针对不可变 DocumentVersion 的可重试运行记录，解析失败不修改文件版本。
4. Evidence 是不可变版本上的可解析定位；可选显示摘录仅用于界面提示，不是权威正文。
5. EvidenceBinding 将 Evidence 与业务 Subject Version 绑定并表达用途；不得复制正文或把参考材料自动升级为客户事实。
6. TraceLink 连接稳定 Object/Version Ref，只表达业务来源与派生关系；证据支持关系由 EvidenceBinding 唯一拥有。
7. 文件、Evidence、Trace 的读取都重新执行 Scope 和 Project Authorization；具有 ID 不代表有访问权。
8. 历史版本、有效 Evidence、Review/Trace 引用和 Audit 所需对象不得被普通删除或清理任务命中。

## Document 分类与 Scope

### Document Aggregate

|语义字段|要求|
|---|---|
|document_id|稳定逻辑文件身份|
|scope|`GLOBAL / PROJECT`；创建后不可改变|
|project_id|PROJECT 必填，GLOBAL 显式为空|
|document_category|高层受控分类|
|document_subtype|可扩展业务细分，不改变高层授权|
|title / original_display_name|规范化显示元数据，不参与物理路径|
|document_state|`ACTIVE / ARCHIVED / RESTRICTED`|
|latest_version_ref|最新已提交版本引用|
|effective_version_ref|当前业务使用版本，可为空|
|created_by / created_at|受权主体与 UTC 时间|
|lock_version|并发控制|

document_category 候选：

- `CONTRACTUAL`：合同、技术协议等约束性资料。
- `PROJECT_RECORD`：实际调研记录、会议纪要、客户提交结果等项目事实来源。
- `STANDARD_CAPABILITY`：标准产品能力、标准接口、用户/部署手册等 GLOBAL 基线。
- `REFERENCE_MATERIAL`：历史方案、参考计划等参考资料。
- `TEMPLATE`：调研表单、文档模板等结构参考。
- `GENERATED_ARTIFACT`：系统生成的 DOCX/PPTX/报告等制品。
- `OTHER`：必须补充 subtype 和用途。

分类规则：

- 实际调研记录属于 PROJECT_RECORD；调研业务表单属于 TEMPLATE。TEMPLATE 可生成问题或结构，但不能独立证明客户实际业务事实。
- STANDARD_CAPABILITY 默认 GLOBAL；项目定制能力文档若包含客户内容则必须为 PROJECT。
- GENERATED_ARTIFACT 继承生成任务的 PROJECT Scope，不因导出而成为 GLOBAL。
- document_category 影响 Evidence Eligibility，不替代 Review 或人工确认。

不变量：

- latest/effective Version 必须属于同一 Document 且 Scope 相同。
- effective_version_ref 只能指向 AVAILABLE 且未 REVOKED 的版本。
- ARCHIVED/RESTRICTED 不删除历史；RESTRICTED 仅允许明确恢复/审计/合规访问。
- Project Archived 后 Document 只读，不能创建新 Version。

## DocumentVersion 与 FileObject

### DocumentVersion Aggregate

|语义字段|要求|
|---|---|
|document_version_id / document_id|版本身份与所属逻辑 Document|
|version_no|Document 内从 1 单调增加且唯一|
|file_object_ref|恰好一个 AVAILABLE 持久 FileObject|
|content_sha256 / size / mime|与 FileObject 快照一致|
|source_metadata|上传、生成、转换或迁移来源的脱敏元数据|
|created_by / created_at|受权主体与 UTC 时间|
|availability_state|`AVAILABLE / RESTRICTED / REVOKED`|
|supersedes_version_ref|可为空，只能指向同 Document 较早版本|
|integrity_checked_at|最近完整性检查时间语义|

不变量：

- 提交后正文、Hash、MIME、Size、version_no、source_metadata 和 supersedes 引用不可修改。
- 新内容、元数据纠正或格式转换产生新 DocumentVersion，不覆盖旧版本。
- REVOKED 版本拒绝普通读取和新 Evidence 绑定，但保留历史 Evidence/Trace/Audit 可解释性。
- supersedes 链不得成环或跨 Document；version_no 与链顺序一致。
- 同一 Document 的版本提交使用 expected_version 防止并发产生重复 version_no。

### FileObject Aggregate

|语义字段|要求|
|---|---|
|file_object_id|内部不可猜测标识|
|scope / project_id|与最终 Document 一致|
|storage_class|`TEMPORARY / PERSISTENT`|
|storage_locator|Storage Adapter 受控定位，不是客户端路径|
|original_name_metadata|规范化显示值，不用于路径拼接|
|sha256 / size / detected_mime|流式校验结果|
|file_state|见状态机|
|created_at / available_at|UTC 时间|
|failure_code|脱敏失败分类，可为空|

FileObject 状态机：

```text
STAGED → AVAILABLE
STAGED → FAILED → CLEANUP_PENDING → REMOVED
AVAILABLE → RESTRICTED
TEMPORARY AVAILABLE → CLEANUP_PENDING → REMOVED
```

- 只有 PERSISTENT + AVAILABLE FileObject 能被 DocumentVersion 引用。
- PERSISTENT FileObject 一旦被 DocumentVersion、Evidence、Trace、Review、OutputArtifact 或保留策略引用，不允许普通物理删除。
- FAILED/REMOVED 不能恢复为 AVAILABLE；重新上传创建新 FileObject。
- storage_locator 必须被解析到配置的存储根内；`..`、绝对输入路径、设备名、符号链接/重解析点越界和大小写碰撞失败关闭。
- 原文件名、Hash 相同不代表同一权限。跨项目逻辑 FileObject 不共享可写 Locator；未来物理去重不得产生存在性或时序侧信道。

## 上传与提交一致性

```text
1. stream to isolated temp
2. validate size / extension / detected MIME / file signature
3. compute SHA-256 while streaming
4. create FileObject(STAGED)
5. atomic promote inside the same storage volume
6. mark FileObject(AVAILABLE)
7. create immutable DocumentVersion + update Document pointers
8. create Parse Job / Outbox / Audit
```

步骤 6～8 使用数据库事务；文件系统原子提升在事务外通过状态与恢复器协调。不得宣称文件系统与 PostgreSQL 具备分布式原子事务。

### 崩溃恢复矩阵

|检测状态|业务可见性|恢复动作|
|---|---|---|
|只有临时文件，无 FileObject|不可见|按 TTL 清理|
|FileObject=STAGED，无最终文件|不可见|标记 FAILED/CLEANUP_PENDING 并审计|
|最终文件存在，FileObject=STAGED|不可见|校验 Hash 后继续提交或隔离清理|
|FileObject=AVAILABLE，无 DocumentVersion|不可见|恢复未完成命令或转 CLEANUP_PENDING|
|DocumentVersion 已提交，文件缺失/Hash 不符|失败关闭|标记完整性事件、限制读取、人工恢复；不得自动伪造文件|
|DocumentVersion/FileObject 完整，Parse Job 缺失|文件可见、解析未完成|幂等补建 Parse Job|

任何恢复动作必须以 file_object_id/document_version_id 和 idempotency_key 去重，并写 Audit。

## ParseRecord 与结构化结果

### ParseRecord Aggregate

|语义字段|要求|
|---|---|
|parse_record_id|单次解析逻辑任务身份|
|document_version_ref|只指向 AVAILABLE 不可变版本|
|parser_profile / parser_version|解析器组合与版本|
|job_ref|对应持久化 Job|
|parse_state|`PENDING / RUNNING / SUCCEEDED / FAILED / CANCELLED`|
|attempt_no|同 profile/version 下单调增加|
|result_ref / result_sha256|成功时指向结构化结果与校验值|
|started_at / completed_at|UTC 运行时间|
|error_code / retryable|脱敏错误分类|

不变量：

- `(document_version_ref, parser_profile, parser_version, attempt_no)` 唯一语义，重试创建新 Attempt/记录而不覆盖历史。
- SUCCEEDED 必须具有 result_ref/result_sha256；FAILED/CANCELLED 不得被 Evidence/RAG 当作成功结果。
- Parser/OCR 不修改 DocumentVersion 或 FileObject；修复输入产生新 Version，修复解析器产生新 parser_version/ParseRecord。
- 解析结果必须保留 page/section/paragraph/table/sheet/slide 等来源定位，供 EvidenceLocator 使用。
- PaddleOCR 是扫描件主链；未达门槛的 Tesseract 只能作为辅助结果，关键字段不能仅凭辅助链自动正式化。

结构化结果的物理存储方式在 Schema V1 决定；无论存数据库还是受控文件，都必须受 DocumentService 授权且不公开绝对路径。

## Evidence 与定位

### Evidence Aggregate

|语义字段|要求|
|---|---|
|evidence_id|稳定不可变证据身份|
|scope / project_id|与来源 DocumentVersion 一致|
|document_version_ref|必填且不可变|
|locator|Typed EvidenceLocator|
|content_fingerprint|定位内容的规范化摘要，用于检测漂移|
|display_label|简短可读位置，如“第 12 页 / 3.2 节”|
|display_excerpt|可选、受限长度、脱敏的界面预览；非权威正文|
|eligibility_state|`CANDIDATE / ELIGIBLE / INELIGIBLE / REVOKED`|
|eligibility_reason|策略与人工资格结论|
|created_by / created_at|来源主体与 UTC 时间|

### Typed EvidenceLocator

|locator_type|最小定位语义|
|---|---|
|DOCUMENT|整个不可变版本|
|PAGE|page_no，可带 bounding box|
|TEXT_RANGE|page/section + start/end offset + normalized fingerprint|
|SECTION|section_path / heading anchor|
|PARAGRAPH|paragraph index / stable anchor|
|TABLE_CELL|table anchor + row/column|
|SHEET_RANGE|sheet identity + cell range|
|SLIDE_SHAPE|slide number + shape identity/bounds|
|STRUCTURED_NODE|ParseResult node id + source locator|

定位字段以源格式支持程度为准；不允许用无法复现的模型摘要代替来源定位。

不变量：

- Evidence 必须能由 EvidenceService 在当前 DocumentVersion 上重新解析定位；解析失败时不返回错误正文或物理路径。
- Evidence 的权威内容始终来自 DocumentVersion + Locator；display_excerpt 只用于列表和人工判断，可重新生成。
- DocumentVersion REVOKED 后 Evidence 自动不可用于新正式化，但历史 Binding/Review/Audit 保留。
- TEMPLATE 只能作为结构/问题参考，不能独立成为客户现状或结论的 ELIGIBLE Evidence。
- 对调研事实，ACTUAL PROJECT_RECORD/实际调研记录优先于业务表单模板；冲突时标记 NeedConfirm，不自动用模板覆盖实际记录。
- AI 只能提出 Evidence Candidate；ELIGIBLE/INELIGIBLE 由策略和受权人工确认。

### Evidence Viewer Contract

```text
evidence_id
 → authorize subject + evidence scope
 → resolve document_version_ref
 → validate locator + content_fingerprint
 → return viewer descriptor (document metadata + typed locator + short preview)
 → UI opens the authorized document viewer at the exact location
```

- Viewer Descriptor 不含本地绝对路径、静态目录 URL 或未授权全文。
- 定位按钮必须绑定 evidence_id/document_version_id，而不是绑定可能变化的“当前文件”。
- 原格式无法精确高亮时，至少打开固定版本和页/节，并明确定位精度；不得伪造精确跳转。

## EvidenceBinding

### EvidenceBinding Aggregate

|语义字段|要求|
|---|---|
|evidence_binding_id|不可变绑定身份|
|scope / project_id|由 Subject Scope 决定|
|evidence_ref|不可变 Evidence|
|subject_version_ref|不可变业务版本|
|binding_purpose|`SUPPORTS / CONTRADICTS / DERIVED_FROM / REFERENCE_ONLY`|
|binding_state|`ACTIVE / SUPERSEDED / REVOKED`|
|bound_by / bound_at|人工或受控系统主体与 UTC 时间|
|superseded_by_ref|替代绑定，可为空|

Scope 规则：

- PROJECT Evidence 只能绑定同一 Project 的 Subject Version。
- GLOBAL Evidence 可绑定 GLOBAL Subject，或以 `REFERENCE_ONLY / SUPPORTS` 明确绑定 PROJECT Subject。
- PROJECT Evidence 不得绑定 GLOBAL Subject，也不得跨项目绑定。
- EvidenceBinding 不复制 Evidence 正文；相同 Evidence/Subject/Purpose 的 Active Binding 必须幂等。

事实规则：

- SUPPORTS 只表示该证据支持指定版本的某项结论，不代表系统自动批准结论。
- CONTRADICTS 不得被 Context Builder 静默过滤；Review/AI 上下文需显式展示冲突。
- REFERENCE_ONLY 尤其适用于模板、历史方案和参考计划，不能被计为客户事实证据。
- 撤销/替代 Binding 不删除旧记录；历史 Review 仍能解释当时证据集合。

## TraceLink

### TraceLink Aggregate

|语义字段|要求|
|---|---|
|trace_link_id|不可变关系身份|
|scope / project_id|按源/目标 Scope 规则确定|
|source_version_ref / target_version_ref|稳定对象或版本引用；正式链优先 Version Ref|
|relation_type|受控业务关系|
|link_state|`ACTIVE / SUPERSEDED / REVOKED`|
|created_by / created_at / trace_id|责任主体、UTC 时间与调用链|
|superseded_by_ref|替代关系，可为空|

核心 relation_type：

- `DERIVED_FROM`：目标由源分析/整理而来。
- `REFINES`：目标细化源对象。
- `IMPLEMENTS`：目标实现源需求/方案。
- `VALIDATES`：目标作为验收/验证对象。
- `GENERATED_FROM`：制品由指定版本集合生成。
- `REFERENCES_CAPABILITY`：PROJECT 对象引用 GLOBAL CapabilityVersion。
- `SUPERSEDES`：新版本/关系明确替代旧对象或关系。

Evidence 对结论的支持/反驳由 EvidenceBinding 表达，不重复创建语义相同的 TraceLink。

Scope 与图约束：

- 同一 PROJECT 内允许；GLOBAL→GLOBAL 允许。
- GLOBAL Capability/Template/Reference → PROJECT 只允许明确的 REFERENCES/DERIVED_FROM 类关系，结果 Scope 仍为 PROJECT。
- PROJECT→GLOBAL 写关系默认禁止；PROJECT A ↔ PROJECT B 全部禁止。
- source 与 target 不能相同；SUPERSEDES 和 DERIVED_FROM 的受控子图不得成环。
- 完全相同 source/target/relation 的 Active Link 唯一；更正通过 supersede，不覆盖。
- 查询 Trace Graph 时逐节点/边授权；不能因起点可访问而泄露无权节点标题、存在性或正文。

## 关系与基数

|关系|基数|约束|
|---|---|---|
|Document → DocumentVersion|1 : 1..N|version_no 单调；历史不覆盖|
|DocumentVersion → FileObject|1 : 1|只引用 PERSISTENT + AVAILABLE|
|FileObject → DocumentVersion|1 : 0..1（V1 逻辑）|不做跨 Document 逻辑复用；物理去重不改变此关系|
|DocumentVersion → ParseRecord|1 : 0..N|按 parser/profile/version 保留尝试历史|
|DocumentVersion → Evidence|1 : 0..N|Locator 必须落在该版本|
|Evidence → EvidenceBinding|1 : 0..N|绑定不同 Subject Version/Purpose|
|SubjectVersion → EvidenceBinding|1 : 0..N|Review 时冻结证据集合快照|
|Object/Version → TraceLink|1 : 0..N|可作为 source 或 target；按 Scope 授权|
|TraceLink → replacement TraceLink|1 : 0..1|只能指向语义上替代自己的新 Link|

## 版本、归档与保留

### 逻辑版本模式

```text
Document (logical identity)
  ├─ latest_version_ref ───────→ newest committed DocumentVersion
  └─ effective_version_ref ────→ version currently used by business

DocumentVersion N ──supersedes──→ DocumentVersion N-1
```

- “当前版本”只由 DocumentService 解析；Evidence、Review、Trace 和业务对象必须保存显式 Version Ref。
- latest 与 effective 可以不同，例如新版本尚未完成解析/Review；调用方必须声明用途。
- 归档 Document 不删除 Version。恢复/反归档若后续允许，必须是受控命令并审计。

### 保留与物理清理

以下任一条件存在时，FileObject/DocumentVersion 不得物理清理：

- 被 Evidence、EvidenceBinding、TraceLink、ReviewSubject、RAG Chunk/Index、AI InputVersion、OutputArtifact 或正式业务版本引用。
- 处于 Audit、Legal Hold、已批准交付或 Release/升级回滚保留范围。
- Hash/完整性事件尚未处理。

只有 TEMPORARY 或失败且零正式引用的 FileObject 可由清理 Job 进入 CLEANUP_PENDING/REMOVED。正式保留期、Legal Hold 和管理员物理清理流程在 DM-06/Release 冻结。

## 失败关闭规则

- 缺失/越权 ProjectId、GLOBAL 权限不明确、Document 与 Version/FileObject Scope 不一致。
- 文件大小/类型/签名/Hash 不符、StorageLocator 越界、已提交文件缺失或 Hash 漂移。
- DocumentVersion 非 AVAILABLE、REVOKED、Evidence Locator 无法复现或 content_fingerprint 不匹配。
- ParseRecord 非 SUCCEEDED 却被当作结构化事实；辅助 OCR 关键字段未经主链/人工确认。
- EvidenceBinding 跨项目、PROJECT→GLOBAL、模板被当作客户事实或冲突证据被隐去。
- TraceLink 自环、禁止方向、跨项目、受控关系成环或无权节点泄露。
- 清理 Job 命中任何正式/历史引用或保留状态。

失败记录只包含安全错误码、对象引用、trace_id 和脱敏原因；不返回物理路径、文件正文、Parser traceback 或无权对象存在性。

## 延后事项

- 文件表/版本表拆分、JSON/结构化结果字段、PostgreSQL 类型和索引：Schema V1。
- 上传、下载、Viewer、Evidence 和 Trace REST 路径/DTO：API Contract V1。
- 单文件大小、允许 MIME、临时 TTL、摘录长度和完整性巡检周期：基础工程/部署配置。
- 物理 Blob 去重：默认不做；未来需证明不会破坏 Project 隔离并走架构/安全评审。
- Evidence relation/source 分类的完整业务矩阵：DM-05 与业务规则共同补齐。
- Legal Hold、正式保留期限与受控物理销毁：DM-06/Release。

## 与上游一致性

- 保持本地文件系统正文 + PostgreSQL 元数据，不引入对象存储。
- 保持 DocumentService/EvidenceService/TraceService 唯一入口，不允许静态目录或跨模块表访问。
- 保持 ProjectId 隔离、GLOBAL 显式授权和版本不可覆盖。
- 保持实际调研记录优先、表单仅参考的用户业务规则。
- 保持 AI 建议态与强制人工确认；Evidence Candidate 不自动成为正式证据。

## DM-03 验收

- Document、DocumentVersion、FileObject 职责、1:N:1 关系和不可变边界完整：PASS。
- STAGED→AVAILABLE 提交链、六类崩溃状态和恢复动作完整：PASS。
- ParseRecord 的版本绑定、重试历史、主辅 OCR 与成功条件完整：PASS。
- EvidenceLocator 覆盖文档、页、文本、章节、段落、表格、Sheet、Slide 和结构节点：PASS。
- Evidence Viewer 能按受权固定版本定位，不保存路径或大段正文副本：PASS。
- EvidenceBinding 的 Scope、用途、冲突和模板参考规则完整：PASS。
- TraceLink 关系、Scope、去重、无环、supersede 和逐节点授权完整：PASS。
- 版本保留、清理保护与失败关闭完整，未定义物理 Schema/API/Migration：PASS。

## 下一步

DM-04：AI/RAG/Job/Plugin/Output 数据模型，冻结 Prompt/Invocation、Index/Chunk、Job/Lease、Plugin 与 OutputArtifact 状态和引用约束。
