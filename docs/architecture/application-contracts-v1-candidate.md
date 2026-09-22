# Application Contract V1 候选

## 状态

`CANDIDATE / AF-02_COMPLETE / NOT_API_FROZEN`

本文件定义模块间 Application Port 和 Domain Event 的语义边界。它不是 REST `/api/v1` Contract，不固定 Python 方法签名、数据库字段或网络序列化格式。

## 通用调用上下文

所有改变状态的 Application Command 必须携带：

|字段语义|要求|
|---|---|
|trace_id|贯穿 API、Application、Job、AI、Plugin 与 Audit|
|actor_id|发起用户或受控系统主体|
|project_id|PROJECT 资源必填；GLOBAL 资源显式为空且只允许授权操作|
|idempotency_key|可重试写操作必填|
|expected_version|修改版本化对象时用于乐观并发控制|

Application Result 只返回业务 DTO、状态、版本和必要引用，不返回 ORM Entity、文件系统绝对路径、Provider Secret、Python traceback 或插件进程细节。

## ProjectAuthorizationService

Owner：`project`。

- `authorize(subject, project, resource_type, resource_id, action)`：默认拒绝；验证项目成员、角色、资源归属和动作。
- `authorize_global(subject, resource_type, action)`：仅允许明确的全局角色操作。
- `list_authorized_projects(subject)`：返回可访问项目标识，不返回项目内部对象。

所有 PROJECT Application Port 在读写前调用本服务。资源不存在与资源无权限对非管理员使用同一外部错误语义，避免枚举。本服务不替代 License、Session、Artifact State 或 Review Lock 校验。

## AIService

Owner：`ai`。

- `submit(task_spec, input_ref, context_ref, command_context) → ai_task_ref`
- `get_task(ai_task_ref, query_context) → ai_task_status`
- `get_suggestion(ai_task_ref, query_context) → ai_suggestion`
- `cancel(ai_task_ref, command_context) → cancellation_result`

TaskSpec 必须绑定 `task_type`、`prompt_version`、`provider_policy`、`output_schema`、`rag_policy`、`timeout`、`retry_policy`。业务模块不得提交 Provider 名称分支或原始 API Key。

- 输出固定标记为 `SUGGESTION / NOT_FORMAL_FACT`。
- 保存 Provider、Model、PromptVersion、InputVersion、InputHash、输出、Token、Latency 与 Error。
- 结构化输出必须经过 Schema 校验；失败不得写入正式业务对象。
- POC-03 遗留约束：分类和引用建议必须附 Evidence 引用并进入 ReviewService，不能自动正式化。

## RetrievalService

Owner：`rag`。

- `retrieve(retrieval_request, query_context) → retrieval_result`
- `build_context(retrieval_result_ref, context_policy, query_context) → context_bundle`
- `create_index(index_spec, command_context) → index_ref`
- `activate_index(index_ref, command_context) → activation_result`
- `rebuild_index(index_ref, source_scope, command_context) → job_ref`

RetrievalRequest 必须提供 `knowledge_scope`、`project_id`、`query`、`index_version`、`top_k`、`metadata_filter`、`rerank_policy`。PROJECT 请求缺少或越权 `project_id` 时失败关闭。

- 候选包含 `chunk_id`、`document_version_id`、Evidence Locator、分数分解和 index/model 版本。
- Context Bundle 只包含已授权的最小必要正文；不得包含 Golden 标签或人工答案字段。
- 一个激活 Index 只绑定一个 Embedding Model/维度；模型变化必须新建索引并全量重建。

## PluginService

Owner：`plugin`。

- `install(signed_package_ref, command_context) → plugin_installation_ref`
- `enable(plugin_id, command_context) → plugin_state`
- `disable(plugin_id, command_context) → plugin_state`
- `invoke(plugin_id, operation, output_context_ref, command_context) → plugin_execution_ref`
- `get_execution(plugin_execution_ref, query_context) → plugin_execution_result`

- 加载前验证 Manifest、开发者签名、Plugin API 版本、OS、依赖和入口边界。
- 只通过 JSON-RPC over stdio 调用独立 Python 子进程；timeout/crash/invalid JSON 转为 `PLUGIN_*` 错误。
- 插件获得最小 OutputContext 和受控 Plugin API；不得获得数据库连接、AI Key、License 私钥或任意宿主环境变量。
- `output` 模块只持有 execution ref，不感知进程 PID、stdio 或插件目录。

## TraceService

Owner：`trace`。

- `link(source_ref, target_ref, relation_type, command_context) → trace_link_ref`
- `supersede(trace_link_ref, replacement_ref, command_context) → trace_link_ref`
- `query_upstream(target_ref, relation_filter, query_context) → trace_graph`
- `query_downstream(source_ref, relation_filter, query_context) → trace_graph`

只保存不可变对象标识、版本标识和关系类型，不复制业务正文。创建链接前由源/目标 Owner 验证对象存在和项目范围。历史链接不得物理覆盖；更正通过 supersede/version 表达。跨项目 TraceLink 默认禁止，GLOBAL Capability 到 PROJECT 引用必须使用明确关系类型。

## ReviewService

Owner：`review`。

- `start(review_subject_ref, reviewer_set, policy, command_context) → review_round_ref`
- `record_decision(review_round_ref, reviewer_id, decision, comment, command_context) → review_status`
- `withdraw(review_round_ref, reason, command_context) → review_status`
- `get_status(review_subject_ref, query_context) → review_status`
- `assert_editable(review_subject_ref, query_context) → editability_result`

- 项目负责人发起并指定 1～N 位确认人；全部处理后才汇总。
- 任一退回则本轮退回，退回意见必填；送审期间主题版本锁定。
- 修改后创建新业务版本和新 Review Round；历史确认永久保留。
- Review 只决定指定版本的审核状态，不直接修改业务模块内部表；Owner 消费 ReviewCompleted 事件执行状态迁移。

## DocumentService 与 EvidenceService

DocumentService：

- `get_version(document_version_ref, query_context) → document_version_metadata`
- `open_authorized_content(document_version_ref, purpose, query_context) → content_stream_ref`
- `create_version(document_ref, validated_file_ref, command_context) → document_version_ref`

任何下游模块不得获得或持久化本地绝对路径。

EvidenceService：

- `bind(evidence_locator, subject_ref, command_context) → evidence_ref`
- `resolve(evidence_ref, query_context) → authorized_evidence_view`
- `validate_eligibility(evidence_ref, policy, query_context) → eligibility_result`

Evidence 定位必须指向不可变 DocumentVersion，并保留 page/section/offset 等可用定位。

## Domain Event 清单

|Event|Owner|主要消费者|最小语义|
|---|---|---|---|
|DocumentVersionCreated|document|jobs、rag、audit|文档版本已持久化，可调度解析|
|DocumentParseCompleted|document|rag、evidence、audit|解析成功并产生结构化结果|
|EmbeddingIndexBuilt|rag|rag、audit|指定模型/维度/版本的索引构建完成|
|EmbeddingIndexActivated|rag|rag、audit|项目或 GLOBAL 的活动索引切换完成|
|ReviewStarted|review|主题 Owner、workflow、audit|指定主题版本进入锁定送审|
|ReviewCompleted|review|主题 Owner、workflow、trace、audit|本轮全部通过，可由 Owner 转为正式状态|
|ReviewReturned|review|主题 Owner、workflow、audit|本轮退回并附理由|
|HandoverAnalysisConfirmed|handover|survey、trace、audit|交接分析指定版本已人工确认|
|SurveyConclusionConfirmed|survey|requirement、trace、audit|调研结论指定版本已人工确认|
|RequirementVersionApproved|requirement|prototype、solution、trace、audit|正式需求版本通过 Review|
|PrototypeVersionApproved|prototype|solution、trace、audit|原型版本通过 Review|
|SolutionVersionApproved|solution|plan、output、trace、audit|方案版本通过 Review|
|PlanVersionApproved|plan|output、trace、audit|计划版本通过 Review|
|OutputRequested|output|plugin、jobs、audit|已授权输出上下文等待执行|
|OutputGenerated|output|document、trace、audit|输出制品完成并登记版本|
|OutputFailed|output|audit|输出失败，包含脱敏错误码与可重试属性|
|PluginExecutionFailed|plugin|output、audit|插件 crash/timeout/protocol failure|
|LicenseStateChanged|license|platform、audit|License 导入、失效或拒绝状态变化|

## Event 交付约束

- 第一版不引入消息队列；同步 Domain Event 在进程内分发，长任务写 PostgreSQL Job/Outbox 记录。
- 持久化事件按至少一次处理设计，消费者以 event_id / idempotency_key 去重。
- Event 只携带标识、版本、状态和必要分类，不携带文件正文、AI Prompt、Secret 或客户敏感内容。
- Event 不能绕过目标模块 Application Port 修改数据。

## 错误语义

|类别|内部前缀|要求|
|---|---|---|
|认证/授权|AUTH / PROJECT|默认拒绝，不泄露资源存在性|
|文件/证据|FILE|不返回绝对路径或解析 traceback|
|AI/RAG|AI / RAG|记录可重试属性、Provider 脱敏信息和 trace_id|
|Plugin|PLUGIN|crash、timeout、protocol、signature 分开编码|
|License|LICENSE|过期、机器不匹配、签名、时间异常分开编码|
|Review/Workflow|REVIEW|锁定、并发版本和非法迁移明确编码|
|系统|SYSTEM|外部只返回安全消息和 trace_id|

## AF-02 验收

- 六个核心公共服务具有唯一 Owner 和技术无关 Contract：PASS。
- AI 建议态、ProjectId 隔离、Plugin 环境隔离和 Review 锁定规则进入 Contract：PASS。
- 18 个跨模块事件具有 Owner、消费者和最小语义：PASS。
- 事件交付未引入 Redis、消息队列或分布式事务：PASS。
- 未冻结 REST 路径、ORM、表结构或语言级方法签名：PASS。

## 下一步

AF-03：冻结认证授权链、文件/Secret、Job Worker、日志审计、进程与部署运行边界。
