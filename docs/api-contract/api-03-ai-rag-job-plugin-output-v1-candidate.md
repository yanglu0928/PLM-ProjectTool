# API-03：AI、RAG、Job、Plugin 与 Output Contract V1 候选

## 状态

`CANDIDATE / API-03_COMPLETE / API-04_NEXT / NOT_GATE_2_FROZEN / NO_FASTAPI_IMPLEMENTATION / NO_EXTERNAL_CALLS`

本文件在 API-01 公共协议上，冻结 AI、RAG、Job、Plugin 与 Output 的异步提交、逐次外发授权、状态、取消、结果、SSE、权限、错误和审计契约。它不连接任何 Provider，不执行客户数据外发，不创建 FastAPI、Pydantic、Worker、Plugin Host、ORM 或 Migration。

## 范围与 Root 覆盖

|Owner|Root IDs|数量|API 边界|
|---|---|---:|---|
|ai|AI-01、AI-02、AI-03、AI-04|4|Provider/Model/Prompt 管理，AITask/Invocation/Suggestion|
|rag|RAG-01、RAG-02、RAG-03、RAG-04|4|Chunk/Embedding 内部，Index 与 RetrievalRun|
|jobs|JOB-01、JOB-02|2|Job 读/取消/受控重试，Outbox 运维面|
|plugin|PLG-01、PLG-02、PLG-03|3|签名 Package、Installation、Execution 投影|
|output|OUT-01、OUT-02|2|固定输入 OutputRequest 与已发布 Artifact|

合计 5 个 Owner、15 个 Root。DocumentChunk、EmbeddingRecord、JobLease/Attempt、Outbox delivery、Plugin 工作区和 OutputContextSnapshot 不提供通用 CRUD；只能由所属 Application Port、Worker 或受控运维命令驱动。

## 控制标记

|标记|含义|
|---|---|
|`S`|有效 Server Session|
|`L`|有效 License|
|`C`|状态改变请求必须通过 CSRF|
|`I`|必须提供 `Idempotency-Key`|
|`M`|必须提供 `If-Match`|
|`E`|必须绑定本轮有效 Egress Authorization；不代表自动外发|
|`A`|必须写 Audit|

所有 PROJECT 操作另行强制 ProjectId、成员状态、Role、资源归属和对象状态检查。业务模块只能通过 AIService、RetrievalService、PluginService、JobService 和 OutputService；不得提交 Provider SDK 参数、pgvector SQL、Plugin 入口路径或数据库内部字段。

## 数据外发授权 Contract

既往 PoC/复验授权、其他任务授权或 Provider 配置授权不得复用于新一轮客户数据外发。每个逻辑外发操作必须先形成预览，再由具备 `AI_EGRESS_APPROVER` 权限的人显式授权。

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|EGRESS_PREVIEW_CREATE|POST `/api/v1/projects/{project_id}/egress-previews`|ProjectManager、ImplementationMember、CustomerManager|S,L,C,I,A|201 EgressPreview；不执行外发|
|EGRESS_PREVIEW_GET|GET `/api/v1/projects/{project_id}/egress-previews/{preview_id}`|同项目受权成员|S,L|预览摘要，不含超出权限的正文|
|EGRESS_AUTHORIZE|POST `/api/v1/projects/{project_id}/egress-previews/{preview_id}:authorize`|ProjectManager、CustomerManager，且满足部署策略|S,L,C,I,M,A|201 一次逻辑操作 AuthorizationRef|
|EGRESS_REVOKE|POST `/api/v1/projects/{project_id}/egress-authorizations/{authorization_id}:revoke`|原批准者、ProjectManager、CustomerManager|S,L,C,I,M,A|200 revoked；不能撤回已发送数据|

`EgressPreview` 必须列出：purpose、task/index/retrieval type、Provider/Model/region、数据类别、不可变 source refs、最小正文/查询范围、预计记录数/字节/Token 上限、payload fingerprint、允许重试边界、expires_at 和风险提示。

`EgressAuthorization` 必须固定：preview fingerprint、批准主体/角色/时间、Provider 配置版本、Model/region、用途、允许数据类别、source version refs、最大载荷、有效期和授权状态。规则：

- 只覆盖一个 AITask、一次 RetrievalRun 或一个有界 Index build/rebuild generation；同一 Job 的相同 payload 有界重试可复用该快照。
- Provider、region、purpose、source version、payload fingerprint 或最大载荷变化必须重新预览和授权。
- 授权只允许缩小，不能由 Worker/AI 自动扩大。授权过期或撤销后，未开始/下一批外发失败关闭。
- Preview/Authorization 不保存 API Key，不向浏览器返回完整客户正文；用户通过受权 Evidence/Document Viewer 检查来源。
- GLOBAL 无客户数据操作由 DeploymentAdmin 按全局策略授权；PROJECT 数据不得借用 GLOBAL 授权。

## AI Provider、Model 与 Prompt 管理

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|AI_PROVIDER_LIST|GET `/api/v1/admin/ai/providers`|DeploymentAdmin|S,L|Provider metadata page|
|AI_PROVIDER_GET|GET `/api/v1/admin/ai/providers/{provider_id}`|DeploymentAdmin|S,L|ProviderView + ETag|
|AI_PROVIDER_CREATE|POST `/api/v1/admin/ai/providers`|DeploymentAdmin|S,L,C,I,A|201 ProviderView；只接收 SecretRef|
|AI_PROVIDER_PATCH|PATCH `/api/v1/admin/ai/providers/{provider_id}`|DeploymentAdmin|S,L,C,M,A|200 config version + ETag|
|AI_PROVIDER_TEST|POST `/api/v1/admin/ai/providers/{provider_id}:test`|DeploymentAdmin|S,L,C,I,M,A|202 JobRef；只发送固定无客户数据探针|
|AI_PROVIDER_ACTIVATE|POST `/api/v1/admin/ai/providers/{provider_id}:activate`|DeploymentAdmin|S,L,C,I,M,A|200 ACTIVE|
|AI_PROVIDER_SUSPEND|POST `/api/v1/admin/ai/providers/{provider_id}:suspend`|DeploymentAdmin|S,L,C,I,M,A|200 SUSPENDED|
|AI_PROVIDER_RETIRE|POST `/api/v1/admin/ai/providers/{provider_id}:retire`|DeploymentAdmin|S,L,C,I,M,A|200 RETIRED|
|AI_MODEL_LIST|GET `/api/v1/admin/ai/models`|DeploymentAdmin|S,L|Model metadata page|
|AI_MODEL_GET|GET `/api/v1/admin/ai/models/{model_id}`|DeploymentAdmin|S,L|ModelView + ETag|
|AI_MODEL_CREATE|POST `/api/v1/admin/ai/models`|DeploymentAdmin|S,L,C,I,A|201 ModelView|
|AI_MODEL_PATCH|PATCH `/api/v1/admin/ai/models/{model_id}`|DeploymentAdmin|S,L,C,M,A|200 mutable routing metadata；不可原地改语义|
|AI_MODEL_SET_STATE|POST `/api/v1/admin/ai/models/{model_id}:set-state`|DeploymentAdmin|S,L,C,I,M,A|200 AVAILABLE/SUSPENDED/RETIRED|
|AI_PROMPT_LIST|GET `/api/v1/admin/ai/prompt-templates`|DeploymentAdmin|S,L|Template metadata page|
|AI_PROMPT_GET|GET `/api/v1/admin/ai/prompt-templates/{prompt_template_id}`|DeploymentAdmin|S,L|Template/active version + ETag|
|AI_PROMPT_CREATE|POST `/api/v1/admin/ai/prompt-templates`|DeploymentAdmin|S,L,C,I,A|201 PromptTemplateView|
|AI_PROMPT_CREATE_VERSION|POST `/api/v1/admin/ai/prompt-templates/{prompt_template_id}/versions`|DeploymentAdmin|S,L,C,I,M,A|201 immutable PromptVersion|
|AI_PROMPT_ACTIVATE_VERSION|POST `/api/v1/admin/ai/prompt-templates/{prompt_template_id}/versions/{version_no}:activate`|DeploymentAdmin|S,L,C,I,M,A|200 active version|
|AI_PROMPT_RETIRE|POST `/api/v1/admin/ai/prompt-templates/{prompt_template_id}:retire`|DeploymentAdmin|S,L,C,I,M,A|200 RETIRED|

- Provider DTO 只返回 endpoint policy/region/egress class、capabilities、SecretRef 脱敏标识和 config version；不返回 API Key、Secret 密文或 Adapter 内部异常。
- Provider Test 只允许固定、无客户数据、无业务 Prompt 的探针；连通成功不等于质量通过。
- Model 的 provider/model key/revision/kind/dimension 构成语义身份。Embedding dimension、Provider、revision 或模型语义变化创建新 Model/Index，不允许 PATCH 冒充兼容更新。
- PromptVersion 不可变，不能包含 API Key、固定客户资料、Golden 答案或绕过 Evidence/Review 的指令。Output Schema 不兼容变化创建新 schema version。

## AITask、Invocation 与 Suggestion

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|AI_TASK_LIST|GET `/api/v1/projects/{project_id}/ai-tasks`|ProjectManager、ImplementationMember、CustomerManager|S,L|仅授权 Task page|
|AI_TASK_CREATE|POST `/api/v1/projects/{project_id}/ai-tasks`|ProjectManager、ImplementationMember|S,L,C,I,E,A|202 AITaskRef + JobRef|
|AI_TASK_GET|GET `/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}`|受权创建者/项目管理角色|S,L|Task state、policy/version refs、JobRef|
|AI_TASK_INVOCATION_LIST|GET `/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}/invocations`|受权创建者/项目管理角色|S,L|Attempt page，响应正文最小化|
|AI_TASK_SUGGESTION_GET|GET `/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}/suggestion`|受权主体|S,L|SuggestionView + Evidence refs；标记 NOT_FORMAL_FACT|
|AI_TASK_CANCEL|POST `/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}:cancel`|创建者、ProjectManager|S,L,C,I,M,A|200 CANCEL_REQUESTED/terminal state|
|AI_TASK_RETRY|POST `/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}:retry`|创建者、ProjectManager|S,L,C,I,M,E,A|202 新 Job/Invocation attempt|
|AI_SUGGESTION_ACCEPT|POST `/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}/suggestion:accept-to-draft`|ProjectManager、ImplementationMember|S,L,C,I,M,A|201 Domain Draft VersionRef|
|AI_SUGGESTION_REJECT|POST `/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}/suggestion:reject`|ProjectManager、ImplementationMember、CustomerManager|S,L,C,I,M,A|200 REJECTED|

`AI_TASK_CREATE` 只接受受控 `task_type`、input version refs、prompt policy ref、output schema ref、RAG/context policy ref、EgressAuthorizationRef 和最小业务参数。客户端不能指定 API Key、SDK 类型、原始 system prompt、任意 endpoint 或绕过 ModelRouter 的 Provider 分支。

- 所有 input refs 必须不可变、属于同一 Project 且提交时重新授权；动态 current/latest ref 被拒绝。
- Retry 如果实际 payload、Provider/config、Model/revision、Prompt、Context 或 source version 变化，必须使用新的 EgressAuthorization；不能伪装为确定性重放。
- Suggestion 只有 SUCCEEDED + schema VALID 才可读取/接受，且永远返回 `fact_status=NOT_FORMAL_FACT`、input/prompt/model/context versions、quality flags 和 Evidence refs。
- Accept-to-draft 重新校验输入版本、Review Lock、目标 Owner、expected version 和权限；由目标业务 Owner 创建新 Draft。AIService 不直接写正式 Requirement/Solution/Plan 等表。
- Accept-to-draft 的 `If-Match` 保护 AITask/Suggestion 状态；请求另携带目标 identity 的 `target_expected_version`，由目标 Owner Port 做第二次乐观并发检查。API-04 必须把目标类型和该版本字段收敛为白名单 DTO。
- POC-03 的 98% 检索、48% 分类和 74% 引用结论保持原样；分类/引用建议必须人工检查 Evidence 并进入 Review，不能自动批准。

## RAG Index、Retrieval 与 Context

### Index 管理

实际 OpenAPI 展开 `/api/v1/global/rag/indexes` 和 `/api/v1/projects/{project_id}/rag/indexes`；下表 `{scope_base}` 不是自由输入。

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|RAG_INDEX_LIST|GET `{scope_base}/rag/indexes`|GLOBAL DeploymentAdmin；PROJECT PM/IM|S,L|Index page|
|RAG_INDEX_GET|GET `{scope_base}/rag/indexes/{embedding_index_id}`|受权主体|S,L|IndexView + ETag|
|RAG_INDEX_CREATE|POST `{scope_base}/rag/indexes`|GLOBAL DeploymentAdmin；PROJECT ProjectManager|S,L,C,I,A|201 PLANNED Index|
|RAG_INDEX_BUILD|POST `{scope_base}/rag/indexes/{embedding_index_id}:build`|GLOBAL DeploymentAdmin；PROJECT ProjectManager|S,L,C,I,M,E,A|202 build JobRef|
|RAG_INDEX_REBUILD|POST `{scope_base}/rag/indexes/{embedding_index_id}:rebuild`|GLOBAL DeploymentAdmin；PROJECT ProjectManager|S,L,C,I,M,E,A|202 新 generation IndexRef + JobRef|
|RAG_INDEX_ACTIVATE|POST `{scope_base}/rag/indexes/{embedding_index_id}:activate`|GLOBAL DeploymentAdmin；PROJECT ProjectManager|S,L,C,I,M,A|200 ACTIVE，原子切换旧 generation|
|RAG_INDEX_RETIRE|POST `{scope_base}/rag/indexes/{embedding_index_id}:retire`|GLOBAL DeploymentAdmin；PROJECT ProjectManager|S,L,C,I,M,A|200 RETIRED|
|RAG_INDEX_VALIDATION_GET|GET `{scope_base}/rag/indexes/{embedding_index_id}/validation`|受权主体|S,L|count/missing/quality/plan summary|

- Create 固定 scope/project、purpose、Embedding Model/version/dimension、Chunk Profile/version 和 source snapshot；任何不兼容变化必须新建 generation。
- Build/Rebuild 使用外部 Embedding 时必须 E；无外发实现仅在明确本地/无外发 Provider policy 下可省略，并记录 authorization=`NOT_APPLICABLE`，不能据此引入本地大模型。
- ACTIVE 前必须 READY、来源/Scope/维度一致、记录完整、质量/查询冒烟通过。PROJECT Index 不含 GLOBAL Chunk；检索分别查询后受控合并。
- Chunk 和 EmbeddingRecord 无公共创建/修改端点。Runtime Role 不允许按请求动态建 HNSW/DDL。

### RetrievalRun

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|RAG_RETRIEVAL_CREATE|POST `/api/v1/projects/{project_id}/retrieval-runs`|ProjectManager、ImplementationMember、CustomerManager|S,L,C,I,E,A|202 RetrievalRunRef + JobRef|
|RAG_RETRIEVAL_GET|GET `/api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}`|创建者/受权项目角色|S,L|state、policy/index refs、quality flags|
|RAG_RETRIEVAL_RESULT_GET|GET `/api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}/result`|创建者/受权项目角色|S,L|候选/Evidence refs、分数分解、最小 snippets|
|RAG_CONTEXT_GET|GET `/api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}/context`|创建者/受权调用链|S,L|最小 ContextBundleView，不含 Golden/人工答案|
|RAG_RETRIEVAL_CANCEL|POST `/api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}:cancel`|创建者、ProjectManager|S,L,C,I,M,A|200 CANCEL_REQUESTED/terminal state|

- 请求包含 query、top_k、metadata filter、retrieval/rerank policy refs 和授权 GLOBAL/PROJECT index refs；ProjectId 仅来自路径。
- Query Embedding 或 Reranker 需要外发时 E 必填，且授权必须覆盖 query 与发送的最小候选正文；纯数据库精确/FTS 检索可 `egress=NOT_APPLICABLE`。
- metadata filter 只接受 document category、source type、version/date 和业务白名单字段，不接收 SQL/JSONPath/任意字段名。
- GLOBAL 与 PROJECT 候选分别授权检索；模板/参考/实际项目记录保留来源类型和权重。Reranker 降级必须按策略显式返回 `degraded=true`。
- 授权过滤后候选不足时，只能在同 Project/Index 扩大扫描或精确回退；不得移除 ProjectId 或混入其他项目/旧 generation。
- Result/Context 不包含 Golden 标签、人工答案、无权全文、向量或其他项目存在性。

## Job 与 Outbox 运维面

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|JOB_PROJECT_LIST|GET `/api/v1/projects/{project_id}/jobs`|ProjectManager、ImplementationMember；其他角色仅自身可见|S,L|JobSummary page|
|JOB_PROJECT_GET|GET `/api/v1/projects/{project_id}/jobs/{job_id}`|受权创建者/项目角色|S,L|JobView、安全进度/错误|
|JOB_PROJECT_CANCEL|POST `/api/v1/projects/{project_id}/jobs/{job_id}:cancel`|创建者、ProjectManager|S,L,C,I,M,A|200 CANCEL_REQUESTED/terminal state|
|JOB_PROJECT_RETRY|POST `/api/v1/projects/{project_id}/jobs/{job_id}:retry`|ProjectManager、受权创建者|S,L,C,I,M,A|202 新 JobRef；不复活终态|
|JOB_ADMIN_LIST|GET `/api/v1/admin/jobs`|DeploymentAdmin|S,L|DEPLOYMENT/GLOBAL Job page；项目 Job 不自动可见|
|JOB_ADMIN_GET|GET `/api/v1/admin/jobs/{job_id}`|DeploymentAdmin|S,L|受权部署 Job detail|
|JOB_ADMIN_RETRY|POST `/api/v1/admin/jobs/{job_id}:retry`|DeploymentAdmin|S,L,C,I,M,A|202 新 JobRef|
|OUTBOX_ADMIN_LIST|GET `/api/v1/admin/outbox-events`|DeploymentAdmin|S,L|仅 metadata/state，正文/客户 payload 不返回|
|OUTBOX_ADMIN_GET|GET `/api/v1/admin/outbox-events/{event_id}`|DeploymentAdmin|S,L|安全 event refs/attempt summary|
|OUTBOX_ADMIN_REDELIVER|POST `/api/v1/admin/outbox-events/{event_id}:redeliver`|DeploymentAdmin|S,L,C,I,M,A|202 新 delivery attempt；仅 DEAD/可重试|

- JobView 返回 job_id/type/owner/scope/state、safe progress/checkpoint label、attempt count、retryable、safe error code、timestamps 和 result ref；不返回 payload、Lease owner/expiry、fencing token、Secret、Prompt、文件路径或 traceback。
- Project Job 始终按 resource/actor snapshot 再授权。DeploymentAdmin 管理面只处理 DEPLOYMENT/GLOBAL Job；查看项目 Job 必须具有项目 membership/role。
- Retry 创建新 Job/generation，引用原 Job 和新 idempotency key；终态历史不复活。不可重试的越权、Schema、签名、Secret/配置错误返回 `JOB_NOT_RETRYABLE`。
- Cancel 是协作式；已发布不可变版本、Artifact、Audit 或外部副作用不会伪装回滚。
- Outbox 没有通用编辑/删除。Redeliver 不能更改 payload/aggregate version，消费者仍按 event_id/idempotency 去重。

## Plugin Package、Installation 与 Execution

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|PLUGIN_PACKAGE_LIST|GET `/api/v1/admin/plugins/packages`|DeploymentAdmin|S,L|Package metadata page|
|PLUGIN_PACKAGE_GET|GET `/api/v1/admin/plugins/packages/{plugin_package_id}`|DeploymentAdmin|S,L|manifest/signature verification summary|
|PLUGIN_PACKAGE_IMPORT|POST `/api/v1/admin/plugins/packages:import`|DeploymentAdmin|S,L,C,I,A|202 verification JobRef；流式签名包|
|PLUGIN_PACKAGE_VERIFY|POST `/api/v1/admin/plugins/packages/{plugin_package_id}:verify`|DeploymentAdmin|S,L,C,I,A|202 verification JobRef|
|PLUGIN_PACKAGE_REVOKE|POST `/api/v1/admin/plugins/packages/{plugin_package_id}:revoke`|DeploymentAdmin|S,L,C,I,M,A|200 REVOKED；停止新安装/执行|
|PLUGIN_INSTALLATION_LIST|GET `/api/v1/admin/plugins/installations`|DeploymentAdmin|S,L|Installation page|
|PLUGIN_INSTALLATION_GET|GET `/api/v1/admin/plugins/installations/{installation_id}`|DeploymentAdmin|S,L|runtime compatibility/operations + ETag|
|PLUGIN_INSTALL|POST `/api/v1/admin/plugins/installations`|DeploymentAdmin|S,L,C,I,A|202 install/validation JobRef|
|PLUGIN_ENABLE|POST `/api/v1/admin/plugins/installations/{installation_id}:enable`|DeploymentAdmin|S,L,C,I,M,A|200 ENABLED operations|
|PLUGIN_DISABLE|POST `/api/v1/admin/plugins/installations/{installation_id}:disable`|DeploymentAdmin|S,L,C,I,M,A|200 DISABLED|
|PLUGIN_RETIRE|POST `/api/v1/admin/plugins/installations/{installation_id}:retire`|DeploymentAdmin|S,L,C,I,M,A|200 RETIRED|
|PLUGIN_EXECUTION_LIST|GET `/api/v1/projects/{project_id}/plugin-executions`|ProjectManager、ImplementationMember|S,L|关联 Output 的 Execution page|
|PLUGIN_EXECUTION_GET|GET `/api/v1/projects/{project_id}/plugin-executions/{execution_id}`|受权项目角色|S,L|safe state/result refs/error|
|PLUGIN_EXECUTION_CANCEL|POST `/api/v1/projects/{project_id}/plugin-executions/{execution_id}:cancel`|关联 Output 创建者、ProjectManager|S,L,C,I,M,A|200 CANCEL_REQUESTED|

- Package import 只接受开发者签名包；验证 Hash、Signature、Manifest、Plugin API、OS/架构、依赖、entry point 边界。客户 API 不接收签名私钥。
- Package/Manifest 不可变；升级导入新版本。V1 不提供客户 SDK、任意第三方插件、插件市场或 URL 在线安装。
- Enable 只能选择 Manifest 声明操作的子集；同 plugin_id/operation 最多一个 enabled installation。
- 不提供公共 `invoke` 端点。PluginExecution 只能由 OutputService 使用固定 OutputContextSnapshot 创建，避免任意调用插件能力。
- Execution DTO 不返回 PID、stdio、工作目录、完整环境或 traceback。SUCCEEDED 仅表示暂存结果协议合法，不表示 Artifact 已发布。

## OutputRequest 与 OutputArtifact

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|OUTPUT_REQUEST_LIST|GET `/api/v1/projects/{project_id}/output-requests`|ProjectManager、ImplementationMember、CustomerManager|S,L|OutputRequest page|
|OUTPUT_REQUEST_CREATE|POST `/api/v1/projects/{project_id}/output-requests`|ProjectManager、ImplementationMember|S,L,C,I,A|202 RequestRef + JobRef|
|OUTPUT_REQUEST_GET|GET `/api/v1/projects/{project_id}/output-requests/{output_request_id}`|创建者/受权项目角色|S,L|fixed sources/context/policy refs、state、JobRef|
|OUTPUT_REQUEST_CANCEL|POST `/api/v1/projects/{project_id}/output-requests/{output_request_id}:cancel`|创建者、ProjectManager|S,L,C,I,M,A|200 CANCEL_REQUESTED/terminal|
|OUTPUT_REQUEST_REGENERATE|POST `/api/v1/projects/{project_id}/output-requests/{output_request_id}:regenerate`|创建者、ProjectManager|S,L,C,I,M,A|202 新 generation Request/Job|
|OUTPUT_ARTIFACT_LIST|GET `/api/v1/projects/{project_id}/output-artifacts`|受权 Project member|S,L|AVAILABLE/受权 Artifact page|
|OUTPUT_ARTIFACT_GET|GET `/api/v1/projects/{project_id}/output-artifacts/{artifact_id}`|受权 Project member|S,L|Artifact metadata/validation/source refs|
|OUTPUT_ARTIFACT_DOWNLOAD|GET `/api/v1/projects/{project_id}/output-artifacts/{artifact_id}/content`|受权 Project member|S,L|DocumentService 流式内容，不返回路径|
|OUTPUT_ARTIFACT_RESTRICT|POST `/api/v1/projects/{project_id}/output-artifacts/{artifact_id}:restrict`|ProjectManager|S,L,C,I,M,A|200 RESTRICTED|
|OUTPUT_ARTIFACT_REVOKE|POST `/api/v1/projects/{project_id}/output-artifacts/{artifact_id}:revoke`|ProjectManager|S,L,C,I,M,A|200 REVOKED；历史/Trace 保留|

- Create 固定 output type、template version、source version refs、output policy、plugin operation 和最小 ContextSnapshot；不接受 dynamic current/latest refs。
- Source refs 必须同一 Project、已授权且符合状态/Review policy。Request 不因源对象后续升版而静默变化。
- 相同 project/output type/input fingerprint/template/policy 的幂等请求返回既有进行中/成功结果；Regenerate 明确创建新 generation。
- OutputContext 不含 ORM、绝对路径、Secret、无权资料或 Provider 配置；Plugin 只获得最小快照和单次工作区。
- Artifact 只有 FileObject、DocumentVersion、PluginExecution、Hash、媒体类型和 validation 全部一致时才 AVAILABLE。插件成功但验证失败返回 Output FAILED，不发布中间文件。
- 重新生成不覆盖旧 Artifact/DocumentVersion。下载沿用 DocumentService 权限，Output 不直接读取文件系统。

## DTO 目录

### AI 与外发

|DTO|核心字段|禁止/约束|
|---|---|---|
|`ProviderView`|provider_id/kind、display name、endpoint policy/region/egress class、capabilities、secret_ref masked、state/config version、etag|API Key、Secret value、Adapter traceback|
|`ModelView`|model_id/provider ref、model key、kind/capabilities、dimension、revision、quality profile、state/etag|把 AVAILABLE 表述为质量通过|
|`PromptTemplateView`|template id/task type/state、active version/schema/policy refs、hash/etag|Secret、固定客户数据、Golden 答案|
|`EgressPreviewView`|purpose/provider/model/region、data categories/source refs、count/bytes/token bounds、fingerprint/expiry|超出权限正文、API Key|
|`EgressAuthorizationRef`|authorization_id、preview fingerprint、scope/purpose/provider config、bounds、approved actor/time、expiry/state|可复用通配授权|
|`AITaskView`|task/state/type、input/prompt/schema/context/authorization refs、job/current invocation、suggestion state、trace/times|Secret、完整 payload、Provider raw response|
|`AIInvocationView`|attempt、actual provider/model/revision/prompt/schema/context refs、state/schema validation、usage/latency、safe error|完整请求/响应、Secret、无权 Context|
|`SuggestionView`|fact_status、schema version、suggestion payload ref/authorized projection、Evidence/conflict/quality flags、input/model/prompt/context refs|“正式事实”标记、无来源自动结论|

### RAG 与 Job

|DTO|核心字段|禁止/约束|
|---|---|---|
|`EmbeddingIndexView`|index id/version/scope/purpose/model/dimension/chunk/source refs、state/build job/count/validation/activation/etag|向量、Runtime DDL、其他项目 source|
|`RetrievalRunView`|run/state/query fingerprint、global/project index refs、policy/rerank/authorization、job/quality/degraded/times|无权 query/正文、其他项目存在性|
|`RetrievalResultView`|authorized candidate refs、DocumentVersion/Evidence locator、score parts/rank/source type、minimal snippet|向量、Golden 标签、人工答案|
|`ContextBundleView`|bundle fingerprint、authorized source refs/ranges/order/token budget/policy|完整无界正文、动态 current ref|
|`JobView`|job/type/owner/scope/state、safe progress/checkpoint、attempt count/retryable/error、result ref/times/etag|payload、Lease/fencing、Secret/Prompt/路径|
|`OutboxEventView`|event/type/owner/scope、aggregate/version refs、delivery state/attempt/available time、trace|正文、Secret、业务 payload 副本|

### Plugin 与 Output

|DTO|核心字段|禁止/约束|
|---|---|---|
|`PluginPackageView`|package/plugin/version/hash、manifest operations/OS/API/dependencies、signature verification/state|签名私钥、包内任意文件读取|
|`PluginInstallationView`|installation/package、state、runtime snapshot、enabled operations、actor/times/etag|宿主完整环境、Secret|
|`PluginExecutionView`|execution/installation/operation、OutputContext ref/fingerprint、job/attempt/state/result manifest ref/fingerprint、safe error/times|PID、stdio、workdir、traceback|
|`OutputRequestView`|request/type/template/source versions/policy/plugin operation/context fingerprint/state/job/execution/times/etag|动态 current refs、ORM/Secret/路径|
|`OutputArtifactView`|artifact/request/kind/media、DocumentVersion、PluginExecution、hash/size/state/validation/published time/etag|storage locator、未校验暂存文件|

## 权限矩阵摘要

`R`=读，`W`=创建/操作，`E`=外发授权，`-`=默认拒绝。实际仍受 Project membership、对象状态、创建者、License 和策略约束。

|资源族|DeploymentAdmin|ProjectManager|ImplementationMember|CustomerManager|CustomerMember|
|---|---|---|---|---|---|
|Provider/Model/Prompt|R/W|-|-|-|-|
|GLOBAL RAG Index|R/W|-|-|-|-|
|PROJECT RAG Index|-|R/W|R|R|受限 R|
|Egress Preview/Authorization|-|R/W/E|R/W|R/E|受限 R|
|AITask/Suggestion|-|R/W|R/W|受权 R|受限 R|
|RetrievalRun|-|R/W|R/W|R/W|受限 R|
|Project Job|-|R/W|自身 R/W|受权 R|自身受限 R|
|Deployment/Global Job/Outbox|R/W|-|-|-|-|
|Plugin Package/Installation|R/W|-|-|-|-|
|Plugin Execution|-|R/W|关联 Output R/W|受权 R|受限 R|
|OutputRequest|-|R/W|R/W|R|受限 R|
|OutputArtifact|-|R/W|R|R|受权 R|

DeploymentAdmin 不自动访问 PROJECT Task、Retrieval、Job、Execution 或 Output。SystemActor 只在 Job 授权快照、fencing 和原始 actor/project 范围内调用 Application Port，不是交互式角色。

## SSE Event Contract

项目事件流使用 `/api/v1/projects/{project_id}/events`；部署管理事件流使用 `/api/v1/admin/events`。SSE `id` 为 event_id，`event` 为下列白名单，`data` 使用 API-01 Envelope 的安全子集：

|event_type|最小 data|
|---|---|
|`ai.task.state-changed`|task ref、state、suggestion_available、job ref、trace_id|
|`rag.index.state-changed`|index ref/version、state、validation summary ref、job ref|
|`rag.retrieval.completed`|run ref、state、result_available、quality/degraded flags|
|`job.state-changed`|job ref/type、state、safe progress、retryable/error code|
|`plugin.execution.state-changed`|execution ref、state、result_available、safe error code|
|`output.request.state-changed`|request ref、state、job/execution refs|
|`output.artifact.available`|artifact ref、kind/media、document version ref、published_at|
|`outbox.event.dead`|admin only：event ref/type/owner、safe error、attempt count|

- Event 不含 Prompt/响应、query、Context、正文、向量、Outbox payload、Secret、Cookie、stdio、路径或 traceback。
- 订阅和每个事件投递都重新校验 Project/Deployment 权限；权限撤销后关闭流。
- `Last-Event-ID` 只在受控恢复窗口内有效；超窗客户端重新 GET 资源状态，不承诺永久事件重放。

## 错误码目录

|错误码|HTTP|触发语义|
|---|---:|---|
|`AI_PROVIDER_UNAVAILABLE`|503|Provider 未激活、暂停或暂不可用|
|`AI_PROVIDER_CONFIG_INVALID`|422|endpoint/region/capability 配置非法|
|`AI_MODEL_UNAVAILABLE`|409|Model 不可路由或任务不兼容|
|`AI_MODEL_REVISION_DRIFT`|409|Provider observed revision 与冻结策略冲突|
|`AI_PROMPT_VERSION_INVALID`|422|Prompt/Schema/TaskType 不兼容|
|`AI_EGRESS_AUTHORIZATION_REQUIRED`|403|本轮外发授权缺失|
|`AI_EGRESS_AUTHORIZATION_EXPIRED`|403|授权过期/撤销|
|`AI_EGRESS_SCOPE_MISMATCH`|403|Provider/region/purpose/source 超范围|
|`AI_EGRESS_PAYLOAD_EXCEEDED`|413|记录/字节/Token 或 fingerprint 超授权|
|`AI_INPUT_VERSION_STALE`|409|输入版本/目标状态变化|
|`AI_OUTPUT_SCHEMA_INVALID`|422|结构化输出未通过 Schema|
|`AI_TASK_STATE_INVALID`|409|状态不允许 cancel/retry/accept|
|`AI_SUGGESTION_NOT_AVAILABLE`|409|无 schema-valid suggestion|
|`AI_SUGGESTION_NOT_FORMAL`|409|试图绕过 Draft/Review 直接正式化|
|`RAG_SCOPE_MISMATCH`|404|Chunk/Index/Run 跨项目或 Scope 不一致|
|`RAG_INDEX_NOT_ACTIVE`|409|查询引用非 ACTIVE Index|
|`RAG_INDEX_BUILD_INCOMPLETE`|409|缺失 Chunk/Embedding/validation|
|`RAG_MODEL_DIMENSION_MISMATCH`|422|Index/Model/Record dimension 不一致|
|`RAG_INDEX_QUALITY_FAILED`|409|质量/冒烟未过，禁止激活|
|`RAG_QUERY_INVALID`|422|query/filter/top_k 不符合白名单|
|`RAG_RERANK_UNAVAILABLE`|503|Reranker 失败且策略不允许降级|
|`RAG_CONTEXT_BUDGET_EXCEEDED`|422|Context 超策略 budget|
|`RAG_RESULT_INSUFFICIENT`|409|依赖动作要求足量证据但同授权范围候选不足；普通查询以 quality flag 成功返回|
|`JOB_STATE_INVALID`|409|状态不允许 cancel/retry/complete|
|`JOB_NOT_RETRYABLE`|409|越权/Schema/签名/配置等不可重试错误|
|`JOB_RETRY_EXHAUSTED`|409|已达到策略上限|
|`JOB_LEASE_LOST`|409|内部 Worker fencing/lease 失效；浏览器只见安全失败|
|`JOB_AUTHORIZATION_SNAPSHOT_INVALID`|403|原 actor/project/purpose 快照缺失或失效|
|`OUTBOX_EVENT_NOT_REDELIVERABLE`|409|非 DEAD/不可重试或业务状态不允许|
|`PLUGIN_SIGNATURE_INVALID`|422|开发者签名验证失败|
|`PLUGIN_PACKAGE_HASH_MISMATCH`|422|包 Hash 不一致|
|`PLUGIN_MANIFEST_INVALID`|422|Manifest/entry/operation/依赖非法|
|`PLUGIN_API_INCOMPATIBLE`|409|Plugin API/宿主版本不兼容|
|`PLUGIN_OS_INCOMPATIBLE`|409|OS/架构不兼容|
|`PLUGIN_INSTALLATION_DISABLED`|409|操作未启用或安装不可用|
|`PLUGIN_OPERATION_NOT_ALLOWED`|403|操作不在 enabled subset|
|`PLUGIN_TIMEOUT`|503|子进程超时|
|`PLUGIN_CRASHED`|503|子进程异常退出|
|`PLUGIN_PROTOCOL_INVALID`|502|JSON-RPC/结果协议无效|
|`PLUGIN_RESULT_INVALID`|422|结果越界、类型/Hash/Manifest 不合法|
|`OUTPUT_SOURCE_VERSION_INVALID`|409|源版本无权、过期或状态不符|
|`OUTPUT_CONTEXT_INVALID`|422|Context 含动态/无权/禁止字段|
|`OUTPUT_PLUGIN_UNAVAILABLE`|409|所需 operation 无 enabled installation|
|`OUTPUT_VALIDATION_FAILED`|422|格式/结构/Hash/内容检查失败|
|`OUTPUT_ARTIFACT_NOT_AVAILABLE`|409|Artifact 未完成/受限/撤销|
|`OUTPUT_STATE_INVALID`|409|状态不允许 cancel/regenerate/restrict|

通用 `RESOURCE_NOT_FOUND`、`CONFLICT_VERSION`、`CONFLICT_IDEMPOTENCY`、`VALIDATION_FAILED` 和 `SYSTEM_UNAVAILABLE` 沿用 API-01。Provider/Plugin 的 HTTP body、stdio、路径和 traceback 只转换为安全码与 retryable，不透传给前端。

## 强制 Audit 动作

- Provider/Model 创建、配置版本、连通性测试、激活/暂停/退役；Prompt version 创建/激活/退役。
- Egress preview、authorize、revoke，以及外发被授权/拒绝/超范围；不记录完整 payload。
- AITask 创建、取消、重试、建议接受/拒绝和 Schema invalid。
- Index create/build/rebuild/activate/retire、Retrieval 提交/降级/失败。
- Job 创建/取消/重试/终态，Outbox DEAD/redeliver；Lease heartbeat 不逐次写业务 Audit。
- Plugin package import/verify/revoke、install/enable/disable/retire、Execution failure。
- Output request/create/cancel/regenerate、Artifact publish/restrict/revoke/download denial。

状态改变与 Audit/Outbox 必须在同一业务事务边界提交。外部调用发生前记录授权快照和 Invocation/Job attempt，发生后以幂等结果命令登记；不得在 Audit 中复制正文或 Provider 响应。

## Contract 测试矩阵

每个 Operation 至少覆盖 API-01 的 Envelope/trace、Session、CSRF、License、Role、Project isolation、If-Match、Idempotency、validation、safe error 与 Audit。专项测试：

1. Egress：旧授权复用、过期/撤销、Provider/region/source/payload 变化、批次超限、重试相同 payload、发送前取消。
2. AI：Provider/Secret/Model/Prompt 不可用，revision drift，结构化输出 invalid，Suggestion 强制建议态，输入升版后 accept 拒绝。
3. RAG：PROJECT/GLOBAL 分离、跨项目 Chunk/Index、维度不符、build 缺失、质量失败、强过滤 exact fallback、Rerank 降级标记、Golden/人工答案零进入 Context。
4. Job：20 Worker 唯一领取、Lease expiry/fencing、旧 Worker 发布拒绝、cancel checkpoint、终态不复活、不可重试错误、Outbox 重复消费/DEAD/redeliver。
5. Plugin：签名/Hash/Manifest/API/OS/依赖/入口、禁用 operation、timeout/crash/invalid JSON、路径越界、环境/Secret 零泄露、进程树回收。
6. Output：固定 source version、幂等与 regenerate、Plugin success + Artifact validation fail、Hash 不符、DocumentVersion 登记、旧 Artifact 保留、受权下载。
7. SSE：项目/部署隔离、权限撤销断流、Last-Event-ID 窗口、重复事件去重、安全 payload。

POC-03 的分类/引用失败继续作为 Gate 3/UAT 阻塞，不能用 Contract 测试或模拟响应替代新独立留出集真实质量验证。

## 风险与关闭条件

|Risk ID|风险|当前控制|关闭条件|
|---|---|---|---|
|API3-R01|逐次授权流程过于繁琐导致用户绕过|预览可复用 UI、授权只绑定一个逻辑操作及有界相同载荷重试|UX 验证 + 外发安全测试|
|API3-R02|Provider managed model revision 漂移|记录 observed revision、config/model/prompt/input/context 快照|真实 Provider 回归与漂移告警|
|API3-R03|建议 Accept 被实现成直接正式化|只允许 Owner 创建 Draft，随后 Review|API-04 Owner command + 权限/状态测试|
|API3-R04|外部 Embedding/Rerank 批处理超过授权边界|count/bytes/token/fingerprint 上限与每批发送前检查|批次边界与取消故障注入|
|API3-R05|共享 HNSW 过滤或降级影响 Recall|Project 强过滤、iterative scan、exact fallback、degraded/quality flags|Gate 3 代表数据 Recall/P95|
|API3-R06|Job 至少一次造成重复外部费用/正式发布|幂等、Provider capability、Lease fencing、结果指纹与发布前复验|故障注入/重复交付测试|
|API3-R07|Outbox DEAD 被静默忽略或重复重放|管理面可见、原 payload 不可编辑、消费者去重|Outbox 集成与运维演练|
|API3-R08|Plugin 独立进程被误称强安全沙箱|仅开发者签名包、最小环境/工作区、无公共 invoke|Plugin Host 安全/故障测试与文档审查|
|API3-R09|Plugin result 合法但业务制品损坏|Output 二次格式/结构/Hash/DocumentVersion 验证|DOCX/PPTX/制品回归|
|API3-R10|SSE 暴露正文或无权项目事件|白名单 payload、每事件授权、撤权断流|SSE 权限/泄露测试|
|API3-R11|正式超时、Token、TopK、Lease 参数尚未冻结|Contract 只引用版本化策略，不硬编码未经验证数值|基础工程性能/质量配置|
|API3-R12|POC-03 下游分类/引用质量未达标|Suggestion + Evidence + 人工确认，Gate 3/UAT 阻塞保留|新独立留出集达到门槛|

## API-03 验收

- 5 个 Owner、15 个 Root 均有明确 API 或 INTERNAL 边界：PASS。
- Provider/Model/Prompt 管理只使用 SecretRef，配置与质量语义分离：PASS。
- 外发 preview/authorize/revoke 与每轮 Provider/region/source/payload 快照明确：PASS。
- AITask/Invocation/Suggestion 的异步、重试、Schema、建议态和 Accept-to-draft 边界明确：PASS。
- Index generation、外部 Embedding 授权、全量重建、质量验证和原子激活明确：PASS。
- RetrievalRun 的 Project 隔离、GLOBAL 合并、Rerank 降级、Context 最小化和 exact fallback 明确：PASS。
- Job/Outbox 的只读/取消/新 Job 重试、至少一次、fencing 与受控 redelivery 明确：PASS。
- Plugin 签名包、安装启停、无公共 invoke、Execution 隔离与安全 DTO 明确：PASS。
- Output 固定 source/context、幂等/regenerate、二次校验、DocumentVersion 与 Artifact 发布明确：PASS。
- Role 矩阵、SSE 白名单、错误码、强制 Audit 和 Contract 测试矩阵明确：PASS。
- Secret、正文、向量、stdio、路径、Lease/fencing 和内部 payload 禁止外露：PASS。
- POC-03 质量失败和 Gate 3/UAT 阻塞未被改写：PASS。
- 12 项风险均有当前控制和关闭位置：PASS。
- 未执行真实外部调用，未创建 FastAPI/Pydantic/Worker/Plugin/ORM/Migration：PASS。

## 下一步

API-04：在 API-01 公共协议及 API-02/03 平台能力之上，冻结 Capability、Handover、Survey、Requirement、Prototype、Solution 与 Plan 的实施业务主链资源、版本、AI 建议接入、Review、Trace、权限、错误和 DTO。
