# AI / RAG / Job / Plugin / Output 数据模型 V1 候选

## 状态

`CANDIDATE / DM-04_COMPLETE / NOT_GATE_2_FROZEN / NOT_PHYSICAL_SCHEMA`

本文件细化 AIProvider、AIModel、PromptTemplate/AITask、DocumentChunk/EmbeddingIndex/RetrievalRun、Job/Outbox、PluginPackage/Execution 与 OutputRequest/Artifact 的字段语义、关系、状态机和失败关闭规则。它不固定 PostgreSQL 类型、表名、索引、REST URL、厂商 SDK 或 Worker 批量参数。

## 设计结论

1. 业务模块只能创建 AITask，由统一 AIService 选择 AIModel、解析 PromptVersion、读取 SecretRef 并创建 AIInvocation；业务对象不保存厂商分支或 API Key。
2. PromptVersion、输入版本、RAG Context、Provider/Model 和输出 Schema 必须在每次 Invocation 上形成不可变快照；同一 AITask 的重试创建新 Invocation，不覆盖旧尝试。
3. AI 结果永久标记为 `SUGGESTION / NOT_FORMAL_FACT`；Schema 通过、模型成功或高置信度都不能直接形成正式业务事实。
4. PROJECT RAG 的 Chunk、Index、Embedding、RetrievalRun 和 Context 必须保持同一 ProjectId；GLOBAL 内容只能按明确策略受控加入项目 Context。
5. Embedding Model、Provider、Dimension、ChunkProfile 或语义不兼容配置变化时必须创建新 Index 并全量重建；禁止把旧向量改标签后继续使用。
6. Job/Outbox 只承诺至少一次；幂等键、租约 fencing token、Attempt 历史和阶段检查点共同防止重复正式写入与过期 Worker 提交。
7. PluginPackage 是开发者签名的不可变包，PluginInstallation 是部署激活状态，PluginExecution 是单次隔离运行；独立进程是故障边界，不宣称是任意代码安全沙箱。
8. OutputRequest 固定输入版本与 OutputContextSnapshot；OutputArtifact 只有在插件输出校验、Hash、DocumentVersion 登记完成后才可发布，失败和重试不覆盖既有制品。

## AI Provider、Model 与 Prompt Registry

### AIProvider Aggregate

|语义字段|要求|
|---|---|
|ai_provider_id|部署内稳定身份|
|provider_kind|`OPENAI_COMPATIBLE / ANTHROPIC_MESSAGES / GEMINI_NATIVE / CUSTOM`|
|display_name|非敏感显示名|
|endpoint_policy_ref|受控端点、区域和 TLS 策略引用|
|secret_ref|SecretRecord/Active SecretVersion 引用，不含明文|
|provider_state|`CONFIGURED / ACTIVE / SUSPENDED / RETIRED`|
|data_region / egress_class|外发区域与数据处理分类|
|capability_flags|chat、structured_output、embedding、rerank 等声明|
|config_version / lock_version|配置版本和并发控制|

不变量：

- ACTIVE 必须通过配置、Secret 可用性和最小连通性检查；连通通过不代表业务质量通过。
- AITask 不直接引用 SecretVersion；Invocation 记录脱敏 `secret_version_ref` 以便追溯，但任何结果、Event、Job 和日志不复制 Secret。
- RETIRED Provider 不接收新调用；历史 Invocation 仍可解析。
- Provider Endpoint、地区或外发类别改变产生新配置版本，并重新评估数据外发授权；不能静默沿用旧授权。

### AIModel Aggregate

|语义字段|要求|
|---|---|
|ai_model_id / provider_ref|稳定模型身份与 Provider|
|provider_model_key|Adapter 内部使用的受控模型标识|
|model_kind|`CHAT / EMBEDDING / RERANK`|
|capabilities|结构化输出、上下文窗口等受控声明|
|embedding_dimension|EMBEDDING 必填，其他为空|
|model_revision|已知时记录不可变修订；未知时明确 `PROVIDER_MANAGED`|
|model_state|`AVAILABLE / SUSPENDED / RETIRED`|
|quality_profile_ref|独立验证结果/适用任务引用，可为空|

- Provider 别名指向的实际模型若无法锁定修订，Invocation 必须记录 Provider 返回的可用版本信息，并保留“可能漂移”风险。
- AVAILABLE 只表示可被路由，不表示 POC-03 分类/引用质量已通过；任务类型仍受 quality profile 和人工确认约束。
- EMBEDDING 的 Provider、Model、Revision 或 Dimension 变化均视为新模型语义，不能复用既有 EmbeddingRecord。

### PromptTemplate 与 PromptVersion

|语义字段|要求|
|---|---|
|prompt_template_id|逻辑模板身份|
|task_type|受控业务任务类型|
|scope|默认 DEPLOYMENT；项目内容不得写入全局模板|
|template_state|`DRAFT / ACTIVE / RETIRED`|
|prompt_version|Template 内单调唯一的不可变版本|
|system/user template hash|规范化模板指纹；正文按受权业务数据保存，不写普通日志|
|output_schema_ref / schema_version|结构化输出合同|
|rag_policy_ref / provider_policy_ref|检索和路由策略版本|
|created_by / created_at|责任主体与 UTC 时间|

- ACTIVE Template 恰好指向一个不可变 PromptVersion；切换版本不改写历史 Invocation。
- PromptVersion 不允许包含真实 API Key、客户资料固定副本、Golden 答案或绕过 Evidence/Review 的指令。
- Output Schema 变化创建新 schema_version；结构不兼容时不得用旧 Invocation 结果填充新业务 Draft。

## AITask、AIInvocation 与建议态

### AITask Aggregate

|语义字段|要求|
|---|---|
|ai_task_id|业务可追踪的 AI 任务身份|
|scope / project_id|GLOBAL 或 PROJECT；PROJECT 必填|
|task_type|与 PromptTemplate/策略兼容|
|requested_by / requested_at|原始人工或受控系统主体|
|input_version_refs|不可变业务/文档版本集合|
|input_fingerprint|规范化最小输入摘要|
|context_policy_ref|检索、证据和最小化策略版本|
|egress_authorization_snapshot|外发批准引用、Provider/地区、允许数据类别、批准主体/时间/有效范围|
|task_state|`QUEUED / RUNNING / SUCCEEDED / FAILED / CANCEL_REQUESTED / CANCELLED`|
|current_invocation_ref|最近一次有效尝试，可为空|
|suggestion_state|`NONE / AVAILABLE / ACCEPTED_TO_DRAFT / REJECTED / SUPERSEDED`|
|accepted_domain_version_ref|人工接受后由业务 Owner 创建的 Draft Version 引用，可为空|
|job_ref / trace_id|异步执行与全链追踪|

不变量：

- PROJECT Task 的所有输入、Retrieval Context 和输出读取均重新授权同一 project_id。
- 客户资料发送到外部 Provider 前，必须存在覆盖本次 Provider、地区、用途和最小数据类别的有效外发授权快照；授权缺失、过期或范围不符时失败关闭。
- `ACCEPTED_TO_DRAFT` 只记录人工接受动作和目标 Draft Version；不能直接把 Suggestion 改名为正式业务对象。
- 接受时业务 Owner 重新校验输入版本、Evidence、Review Lock 和 expected_version；输入已过期则要求重新生成或显式处理差异。

### AIInvocation（AITask 内不可变 Attempt）

|语义字段|要求|
|---|---|
|ai_invocation_id / attempt_no|Task 内唯一、单调|
|provider_ref / model_ref / model_revision_observed|实际路由结果|
|prompt_version_ref / output_schema_ref|不可变 Prompt 与 Schema|
|input_version_refs / input_hash|实际发送输入的版本和指纹|
|retrieval_run_ref / context_bundle_fingerprint|可为空；实际最小 Context 快照|
|request_payload_fingerprint|外发载荷摘要，不是普通日志正文|
|invocation_state|`PENDING / RUNNING / SUCCEEDED / FAILED / CANCELLED`|
|schema_validation_state|`NOT_APPLICABLE / PENDING / VALID / INVALID`|
|suggestion_payload_ref / response_fingerprint|受权结果与摘要|
|usage / latency / provider_request_ref|Token、耗时和脱敏外部请求标识|
|error_code / retryable|脱敏错误分类|
|started_at / completed_at|UTC 时间|

- SUCCEEDED 且要求结构化输出时，schema_validation_state 必须为 VALID；INVALID 不能产生可接受 Suggestion。
- 重试必须沿用或显式记录新的策略版本。若 Prompt、Model、Input 或 Context 变化，结果不得伪装为同一次确定性重放。
- Provider 超时后的远端结果未知时标记明确错误；可重试调用使用 idempotency 能力（若 Provider 支持）和本地结果去重，但不承诺外部“精确一次”。
- 完整请求/响应是受权业务数据，不进入 Application/Integration Log；是否保留及期限由任务策略和 DM-06 确定。

### 建议正式化链

```text
AITask SUCCEEDED
 → AIInvocation schema VALID
 → Suggestion AVAILABLE / NOT_FORMAL_FACT
 → 人工查看 Evidence、冲突与输入版本
 → 显式 Accept 或 Reject
 → 业务 Owner 创建新的 Domain Draft Version
 → ReviewService 审核指定 Draft Version
 → 业务 Owner 更新正式版本引用
```

任何阶段都不得让 AIService 直接写正式 Requirement、Solution、Plan、Capability 或调研结论。

## RAG Chunk、Index、Embedding 与 Retrieval

### DocumentChunk Aggregate

|语义字段|要求|
|---|---|
|chunk_id|稳定 Chunk 身份|
|scope / project_id|继承 DocumentVersion|
|document_version_ref / parse_record_ref|不可变来源|
|chunk_profile / chunk_profile_version|切分策略与版本|
|chunk_ordinal / locator|版本内顺序与 Typed EvidenceLocator|
|normalized_text_ref / text_fingerprint|受权正文引用与摘要|
|metadata_snapshot|来源类型、标题层级、语言等白名单元数据|
|chunk_state|`ACTIVE / RESTRICTED / REVOKED`|

- Chunk 必须能反向定位 DocumentVersion 和 EvidenceLocator；模型摘要不能替代来源正文。
- 同一 DocumentVersion + ParseRecord + ChunkProfile 的成功构建结果必须幂等；策略改变创建新 Chunk generation，不覆盖旧 Chunk。
- TEMPLATE/REFERENCE 与 PROJECT_RECORD 的来源类型保留到检索元数据，不能在 Context 中伪装成同等客户事实。

### EmbeddingIndex Aggregate

|语义字段|要求|
|---|---|
|embedding_index_id|索引 generation 身份|
|scope / project_id|GLOBAL 或单一 PROJECT|
|index_purpose|业务用途/语料域|
|embedding_model_ref / dimension|不可变绑定|
|chunk_profile_version / source_snapshot_ref|切分版本与固定来源集合|
|build_egress_authorization_snapshot|使用外部 Embedding 时，固定批准引用、Provider/地区、数据类别和有效范围|
|index_version|同 scope/purpose 下单调版本|
|index_state|`PLANNED / BUILDING / READY / ACTIVE / FAILED / RETIRED`|
|build_job_ref / build_fingerprint|构建任务与输入摘要|
|record_count / validation_summary|构建校验统计|
|activated_by / activated_at|受权切换记录|

状态机：

```text
PLANNED → BUILDING → READY → ACTIVE → RETIRED
                   ↘ FAILED
```

- `(scope, project_id, index_purpose)` 最多一个 ACTIVE Index；激活在同一事务中切换旧 Index 为 RETIRED 或非活动历史状态。
- ACTIVE 前必须验证来源 Scope、模型/维度、Chunk/Embedding 数量、缺失率和最小查询冒烟；质量门槛失败不能激活。
- 外部 Embedding 构建的每次调用都必须被 build_egress_authorization_snapshot 覆盖；历史批准不得自动扩大到新 Provider、地区、语料或重建批次。
- 模型、Dimension 或 ChunkProfile 不兼容变化必须新建 Index 并全量重建；禁止原地修改向量列含义。
- PROJECT Index 不包含 GLOBAL Chunk。检索时可分别查询受权 GLOBAL 与 PROJECT Index，再由策略合并，不能把两种 Scope 混成一个无归属 Index。

### EmbeddingRecord

|语义字段|要求|
|---|---|
|embedding_record_id|不可变记录身份|
|index_ref / chunk_ref|同 Scope 且固定版本|
|model_ref / dimension|必须与 Index 一致|
|vector_fingerprint|向量摘要与完整性检查|
|embedding_state|`AVAILABLE / FAILED / REVOKED`|
|provider_request_ref / created_at|脱敏调用标识与 UTC 时间|
|egress_authorization_ref|外部 Embedding 调用所使用的授权快照引用，可为空仅限无外发实现|

- `(index_ref, chunk_ref)` 最多一个 AVAILABLE Record；重试结果以幂等规则收敛，失败尝试保留在 Job/Invocation 历史。
- 不允许跨 Index 复制 EmbeddingRecord；即使模型名称相同，也必须验证精确版本、维度和策略。

### RetrievalRun 与 ContextBundle

|语义字段|要求|
|---|---|
|retrieval_run_id|单次受权检索身份|
|scope / project_id / actor_ref|GLOBAL 或 PROJECT；PROJECT 必填并记录请求主体|
|query_fingerprint|规范化查询摘要；原文按受权策略保存|
|global_index_ref / project_index_ref|实际使用的激活 Index，可为空但必须符合策略|
|retrieval_policy_ref / rerank_model_ref|Hybrid、权重、TopK、过滤和重排版本|
|egress_authorization_snapshot|外部 Query Embedding/Reranker 使用的批准引用和最小载荷范围|
|candidate_snapshot|ChunkRef、DocumentVersionRef、Locator、分数分解与排序|
|retrieval_state|`RUNNING / SUCCEEDED / FAILED / CANCELLED`|
|quality_flags|空结果、低分、冲突、来源类型等|
|created_at / completed_at / trace_id|时间与追踪|

ContextBundle 是 RetrievalRun 下的不可变最小上下文快照，包含已授权 Chunk/Evidence 引用、截取范围、排序和 token budget；不包含 Golden 标签、人工答案列、无权全文或其他项目存在性。

- GLOBAL RetrievalRun 只允许明确的全局权限和 GLOBAL Index；PROJECT 查询先验证 Project，候选生成、Rerank、Context Builder 和 AIService 每层均保持 Project 过滤。
- Query Embedding 或 Reranker 需要外发时，授权必须覆盖实际 Provider、地区、查询和最小候选正文；既往 PoC/复验授权不得被当作未来调用的长期授权。
- GLOBAL 候选只能以明确允许的来源类型进入 Context；PROJECT_RECORD 与 TEMPLATE/REFERENCE 必须保留来源标识和不同证据权重。
- Reranker 失败时是否退回未重排结果由版本化策略决定并显式标记；不能把降级结果冒充完整主链结果。
- POC-03 的 98% Top-5、48% 分类和 74% 引用结果保持质量约束；数据模型通过不解除 Gate 3/UAT 的分类/引用失败项。

## Job、Attempt、Lease 与 Outbox

### Job Aggregate

|语义字段|要求|
|---|---|
|job_id|持久任务身份|
|owner_module / job_type|唯一任务 Owner 与受控类型|
|scope / project_id|GLOBAL、PROJECT 或 DEPLOYMENT；按类型固定|
|actor_snapshot|原 actor、受控 SystemActor、授权目的|
|trace_id / correlation_ref|请求与业务链追踪|
|payload_refs / policy_version_refs|只含最小对象/版本/策略引用|
|idempotency_key|Owner + Scope + JobType 内受控唯一|
|job_state|见状态机|
|retry_policy_snapshot|上限、退避、抖动和可重试分类|
|cancel_requested_by / reason|协作取消信息，可为空|
|checkpoint_ref|已验证阶段检查点，可为空|
|created_at / available_at / completed_at|UTC 时间|

状态机：

```text
PENDING → RUNNING → SUCCEEDED
             ├──→ RETRY_WAIT → RUNNING
             ├──→ FAILED
             └──→ CANCEL_REQUESTED → CANCELLED
PENDING / RETRY_WAIT → CANCEL_REQUESTED → CANCELLED
```

- SUCCEEDED、FAILED、CANCELLED 为终态；管理员重试创建新 Job 或显式 Retry Generation，不复活终态历史。
- 越权、签名、Schema、Project/Scope、Secret 配置和不可恢复输入错误不可盲目重试。
- Job Payload 禁止文件正文、Prompt 全文、Cookie、Token、Secret 明文、插件 stdio 原文和客户资料副本。
- Archived Project 不接收新业务 Job；已运行 Job 在安全检查点取消或按明确维护策略收敛。

### JobAttempt 与 JobLease

|对象|核心字段|不变量|
|---|---|---|
|JobAttempt|attempt_no、worker_ref、started/completed、result_ref、error_code|每次领取创建/推进独立尝试；历史不覆盖|
|JobLease|lease_owner、lease_expires_at、heartbeat_at、fencing_token|同 Job 同时最多一个有效租约；token 单调|

- Worker 领取 Job 时原子验证状态与 available_at，并取得新的 fencing_token。
- 心跳只能由当前 owner/token 延长；租约过期可回收，但旧 Worker 的 checkpoint、结果发布和完成命令必须因 token 过期被拒绝。
- 外部调用结束后先重新验证租约和取消状态，再进入幂等发布；不能因调用已付费就绕过 fencing。
- 取消不伪造回滚：已发布的不可变 DocumentVersion、Audit 或外部副作用保持记录，并标注取消发生的阶段。

### OutboxEvent Aggregate

|语义字段|要求|
|---|---|
|event_id / event_type|稳定事件身份与受控类型|
|owner_module / scope / project_id|事件 Owner 与授权范围|
|aggregate_ref / aggregate_version|发生事件的对象与版本|
|payload_refs|最小 ID、版本、状态和分类|
|idempotency_key / trace_id|消费者去重与追踪|
|delivery_state|`PENDING / DELIVERING / DELIVERED / RETRY_WAIT / DEAD`|
|attempt_count / available_at|有界重试调度|

- OutboxEvent 与产生它的业务状态在同一 PostgreSQL 事务提交；文件或外部系统结果通过先验证后登记的业务命令进入该事务。
- Event 至少一次交付；每个消费者使用 `(event_id, consumer_id)` 或等价 Inbox/消费记录去重。
- DEAD 不等于业务事务回滚；必须可见、可审计并支持受控管理员重新投递。
- Outbox 不携带正文、Prompt、Secret 或客户字段副本，也不能绕过目标 Application Port 直接写表。

## Plugin Package、Installation 与 Execution

### PluginPackage Aggregate

|语义字段|要求|
|---|---|
|plugin_package_id / plugin_id / plugin_version|不可变包与逻辑插件版本|
|package_hash|完整包 SHA-256|
|manifest_snapshot|名称、入口、操作、OS/架构、依赖、Plugin API 范围|
|signature / signer_key_ref|开发者签名与受信公钥引用|
|compatibility_policy_ref|宿主/Python/OS 兼容规则|
|package_state|`IMPORTED / VERIFIED / REJECTED / REVOKED`|
|verified_at / verification_summary|验证时间与脱敏结果|

- 只有 VERIFIED 且未 REVOKED 包可安装；签名、Hash、Manifest、入口越界、API 或 OS 不兼容均失败关闭。
- Package 内容和 Manifest 提交后不可修改；升级导入新 plugin_version/package_id。
- 签名私钥只在 Developer Workbench，不进入客户运行时、仓库、数据库或包。

### PluginInstallation Aggregate

|语义字段|要求|
|---|---|
|plugin_installation_id / package_ref|部署安装身份和精确包|
|installation_state|`INSTALLED / ENABLED / DISABLED / INCOMPATIBLE / RETIRED`|
|validated_runtime_snapshot|Python、OS、架构和依赖检查结果|
|enabled_operations|Manifest 子集，不可扩大声明权限|
|installed/enabled_by_at|责任主体与 UTC 时间|

- 同一 plugin_id 每个操作最多一个 ENABLED Installation；版本切换是受审计的原子激活，不覆盖旧安装历史。
- 运行环境变化后兼容性失效必须停止新 Execution；已有制品不因此删除。
- V1 仅允许开发者签名包，不开放客户 SDK、任意第三方插件或插件市场。

### PluginExecution Aggregate

|语义字段|要求|
|---|---|
|plugin_execution_id|单次运行身份|
|scope / project_id|继承 OutputRequest|
|installation_ref / operation|精确插件版本和声明操作|
|output_context_ref / context_fingerprint|最小不可变输入|
|job_ref / attempt_no / idempotency_key|异步、尝试与去重|
|execution_state|`PENDING / RUNNING / SUCCEEDED / FAILED / CANCELLED`|
|result_manifest_ref / result_fingerprint|暂存结果清单和摘要|
|error_code / retryable|`PLUGIN_*` 脱敏错误|
|started_at / completed_at / trace_id|时间与追踪|

- 子进程只获得白名单环境、单次工作目录、最小 OutputContext 和 JSON-RPC stdio；无数据库连接、AI Key、License 私钥或宿主完整环境。
- timeout、crash、invalid JSON、协议版本和结果越界失败关闭；宿主回收进程树，其他 Job/FastAPI 不受影响。
- SUCCEEDED 只表示插件产生了协议合法的暂存结果，不等于 OutputArtifact 已发布；OutputService 仍须校验类型、大小、Hash 和登记 DocumentVersion。
- stdio 原文、绝对工作路径和 traceback 不写普通日志或返回浏览器。

## OutputRequest、Context 与 Artifact

### OutputRequest Aggregate

|语义字段|要求|
|---|---|
|output_request_id|一次输出意图身份|
|project_id / requested_by|项目与受权主体|
|output_type / template_version_ref|制品类型与固定模板|
|source_version_refs|Requirement/Solution/Plan 等不可变输入|
|output_policy_ref / plugin_operation|输出规则与受控操作|
|context_snapshot_ref / context_fingerprint|不可变最小上下文|
|request_state|`REQUESTED / QUEUED / GENERATING / VALIDATING / SUCCEEDED / FAILED / CANCEL_REQUESTED / CANCELLED`|
|job_ref / current_execution_ref|运行引用|
|idempotency_key / trace_id|重复提交收敛与追踪|
|requested_at / completed_at|UTC 时间|

OutputContextSnapshot 只包含已授权源版本、章节顺序、样式/模板参数、必要 Evidence/Trace 引用和输出策略；不含 ORM 对象、绝对路径、Secret、无权资料或“当前版本”动态指针。

- 请求创建时固定所有 source_version_refs；源对象后续升版不会静默改变在途输出。
- 同一项目、输出类型、输入指纹、模板和策略的幂等请求返回既有进行中/成功结果；显式“重新生成”创建新 generation。
- 取消是协作式；已发布 Artifact 不删除，未发布暂存结果按清理策略处理。

### OutputArtifact Aggregate

|语义字段|要求|
|---|---|
|output_artifact_id / output_request_ref|制品和来源请求|
|project_id|与 Request 一致|
|artifact_kind / media_type|受控类型|
|document_version_ref|已登记 GENERATED_ARTIFACT DocumentVersion|
|plugin_execution_ref|产生暂存结果的精确执行|
|artifact_sha256 / size|发布内容完整性|
|artifact_state|`VALIDATING / AVAILABLE / RESTRICTED / REVOKED`|
|validation_summary|格式、结构、Hash 和必要内容检查|
|created_at / published_at|UTC 时间|

- AVAILABLE 必须具有一致的 FileObject、DocumentVersion、Hash、PluginExecution 和 OutputRequest；任一缺失都不可见。
- OutputArtifact 不改变源 Requirement/Solution/Plan 的正式状态，也不把 AI Suggestion 自动正式化。
- 重新生成产生新的 OutputArtifact 和 DocumentVersion；旧制品按 Trace/Review/交付记录保留。
- 下载/预览重新执行 Project Authorization、Artifact State 和 DocumentService 授权，不返回本地路径。

## 端到端关系与基数

|关系|基数|约束|
|---|---|---|
|AIProvider → AIModel|1 : 0..N|Model 只属于一个 Provider|
|PromptTemplate → PromptVersion|1 : 1..N|版本不可变，最多一个 Active|
|AITask → AIInvocation|1 : 0..N|Attempt 单调；历史不覆盖|
|AITask → Domain Draft Version|1 : 0..1|仅人工接受后由业务 Owner 创建|
|DocumentVersion → DocumentChunk|1 : 0..N|按 Parse/Chunk generation 保留|
|EmbeddingIndex → EmbeddingRecord|1 : 0..N|每个 Chunk 最多一个 Available Record|
|RetrievalRun → ContextBundle|1 : 0..N|每个策略构建不可变最小 Context|
|Job → JobAttempt / JobLease|1 : 0..N / 0..N|同时最多一个有效 Lease|
|Aggregate Version → OutboxEvent|1 : 0..N|与业务事务同提交|
|PluginPackage → PluginInstallation|1 : 0..N|跨部署/历史安装保留|
|OutputRequest → PluginExecution|1 : 0..N|重试/重新生成不覆盖|
|OutputRequest → OutputArtifact|1 : 0..N|只有校验后 Available|

## 关键运行链

### RAG + AI

```text
DocumentVersion / ParseRecord
 → DocumentChunk generation
 → new EmbeddingIndex BUILDING
 → EmbeddingRecord complete + validation
 → Index READY → authorized activation
 → RetrievalRun (GLOBAL + same PROJECT)
 → immutable ContextBundle
 → AITask / AIInvocation
 → schema-valid Suggestion / NOT_FORMAL_FACT
 → human acceptance → Domain Draft → Review
```

### Output + Plugin

```text
OutputRequest + fixed OutputContextSnapshot
 → PostgreSQL Job + Outbox + Audit
 → Worker lease/fencing
 → PluginExecution in isolated subprocess
 → validate staged result
 → FileObject + immutable DocumentVersion
 → OutputArtifact AVAILABLE
 → TraceLink GENERATED_FROM + OutputGenerated Event
```

任何失败都保留 Job/Invocation/Execution 诊断状态，但未校验中间结果不得被业务引用。

## 保留、清理与审计

- PromptVersion、AIInvocation、RetrievalRun、Index activation、Job terminal history、Outbox DEAD/DELIVERED、PluginPackage/Installation/Execution 和 OutputArtifact 都保留足够历史以解释正式版本、Review、交付和故障。
- AI 完整输入/输出、Chunk 正文和 Context 属于受权业务数据，不是普通日志；具体保留期和受控销毁在 DM-06 定义。
- RETIRED Index 的向量只有在零正式引用、零 Review/AI/质量复现保留且策略允许时才可物理清理；清理不删除源 DocumentVersion/Chunk 追溯。
- Plugin 临时工作区和失败输出只有在进程已终止、无活动 Lease、无已发布 Artifact 引用且保留策略允许时清理。
- 强制 Audit 点包括 Provider/Secret 配置变化、Prompt 激活、AI/RAG 调用、Index 激活、管理员 Job 重试、Plugin 安装/启停/失败和 Artifact 发布/撤销。

## 失败关闭规则

- AI Provider/Model/Prompt/Schema/Secret 不可用，AI/Embedding/Reranker 外发授权缺失、过期或载荷超出批准范围。
- AI InputVersion、Evidence、Context 或 ProjectId 越权/过期；结构化输出 Schema INVALID。
- RAG 跨项目、Index/Chunk/Model/Dimension 不一致、构建不完整、质量检查失败或未激活 Index 被当作生产索引。
- Retrieval/Reranker 降级未按策略标记，Golden 标签/人工答案或无权正文进入 Context。
- Job 授权快照缺失、租约过期、fencing_token 不匹配、终态复活、不可重试错误盲目重试或重复发布。
- Outbox 绕过 Application Port、Payload 含正文/Secret，或 DEAD 事件被静默视为已处理。
- Plugin 签名/Hash/Manifest/API/OS/入口不合法，子进程超时/crash/协议错误或请求越权环境能力。
- Output 输入使用动态“当前版本”、插件成功但制品未校验登记、Hash 不一致或 Artifact/Document Scope 不一致。

失败只返回安全错误码、对象引用、trace_id 和 retryable；不返回 Secret、完整 AI 请求/响应、客户正文、向量、插件 stdio、绝对路径或内部 traceback。

## 延后事项

- JSON/关系表拆分、pgvector 类型、全文检索配置、唯一/部分索引和租约领取 SQL：Schema V1。
- AI/RAG/Job/Plugin/Output REST DTO、SSE 事件和错误码清单：API Contract V1。
- Token/成本限额、超时、租约、心跳、批量、退避、Chunk 大小和 TopK 数值：基础工程与性能/质量验证。
- AI 输入输出、向量、Job/Outbox 和 Plugin 工作区的具体保留期：DM-06/Release。
- POC-03 分类/引用质量修复：Gate 3/UAT 持续阻塞项，不因 DM-04 通过而关闭。
- 多节点 Worker、消息队列、本地模型、独立向量库、第三方插件市场和强沙箱：不在 V1 Scope。

## 与上游一致性

- 保持模块化单体、PostgreSQL 18 + pgvector、本地文件系统和独立 Worker，不引入 Redis/消息队列。
- 保持统一 AIService/RetrievalService、业务模块禁用厂商 SDK 和直接 pgvector SQL。
- 保持 ProjectId 隔离、外发逐次授权和最小必要载荷。
- 保持 Plugin 独立 Python 子进程、JSON-RPC stdio、开发者签名和最小环境。
- 保持 AI Suggestion 与正式业务事实分离，以及 POC-03 质量例外/人工确认约束。
- 保持 Windows 11、Windows Server 2025、Debian 13 为正式目标；不把 Debian 暂缓验证描述为兼容通过。

## DM-04 验收

- AIProvider/Model/PromptVersion 的路由、Secret、版本漂移和质量适用边界完整：PASS。
- AITask/AIInvocation 及 Embedding/Reranker 的输入快照、逐次外发授权、重试、Schema 与建议正式化链完整：PASS。
- Chunk、EmbeddingIndex/Record 的 Scope、模型/维度绑定、新索引全量重建和激活状态完整：PASS。
- RetrievalRun/ContextBundle 的 Project 隔离、来源类型、Rerank 降级和最小 Context 完整：PASS。
- Job/Attempt/Lease 的至少一次、幂等、fencing、重试、取消和终态边界完整：PASS。
- Outbox 同事务、消费者去重、DEAD 可见性和最小 Payload 完整：PASS。
- PluginPackage/Installation/Execution 的签名、兼容、版本激活、子进程隔离和失败关闭完整：PASS。
- OutputRequest/Context/Artifact 的固定输入、重新生成、校验登记和版本保留完整：PASS。
- 两条端到端运行链、保留/清理、审计和失败关闭完整：PASS。
- 未引入消息队列、独立向量库、本地模型、第三方市场或物理 Schema/API/Migration：PASS。

## 下一步

DM-05：Capability、Handover、Survey、Requirement、Prototype、Solution、Plan 实施业务域数据模型。
