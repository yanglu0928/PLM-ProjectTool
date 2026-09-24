# 模块边界 V1 候选

## 状态

`CANDIDATE / AF-01_COMPLETE / NOT_FROZEN`

本文件只收敛模块职责、数据所有权和允许依赖。实体字段、数据库表、REST 端点仍分别等待 Data Model Freeze、Schema V1 和 API Contract V1，不得据此开始正式业务编码。

## 运行单元

第一版是一个 FastAPI 模块化单体、一个 Worker 进程、一个 PostgreSQL 18/pgvector 实例、本地文件存储和独立 Plugin 子进程。Vue 3 Web 只通过 REST/SSE 调用 API。开发者工作台是独立信任区，不部署 License 私钥到客户环境。

```text
Vue 3
  → FastAPI API / Application Ports
      → Domain Modules
          → Repository / Gateway Ports
              → PostgreSQL 18 + pgvector / Local File Storage / External AI
      → Job Table ← Worker
      → PluginService → Python Plugin Process (JSON-RPC stdio)

Developer Workbench (separate trust zone)
  → signs License / developer plugin packages
  → exports public material and signed artifacts only
```

## 模块目录与所有权

|模块|核心职责|拥有的数据/状态|公开 Application Port|允许的直接依赖|
|---|---|---|---|---|
|platform|Composition Root、配置、事务、统一异常、健康检查、运行信息|非业务配置缓存|ConfigPort、UnitOfWork、HealthService|无业务模块依赖|
|auth|用户名密码、Session、CSRF、账户启停|User、Session、PasswordCredential|AuthService、SessionService|platform、audit|
|project|项目生命周期、成员与项目资源授权入口|Project、ProjectMember、Department、RoleAssignment|ProjectService、ProjectAuthorizationService|auth、audit|
|workflow|阶段、Gate、Checklist 与状态迁移|Stage、StageChecklist、StageTransition|WorkflowService、StageGateService|project、evidence、review、audit|
|document|逻辑文件、版本、解析状态与文件元数据|Document、DocumentVersion、FileObject、ParseRecord|DocumentService、DocumentQuery|project、jobs、audit|
|evidence|正式证据引用、定位与证据资格|Evidence、EvidenceLocator、EvidenceBinding|EvidenceService|project、document、audit|
|review|统一送审、处理人、意见、锁定与升版重审|Review、ReviewRound、ReviewAssignment、ReviewDecision|ReviewService|project、audit|
|trace|跨模块可追溯关系，只保存标识与关系类型|TraceLink|TraceService、TraceQuery|project、audit|
|audit|不可删除的业务审计事件|AuditEvent|AuditService、AuditQuery|platform|
|jobs|PostgreSQL Job Table、租约、重试、取消、Worker 调度|Job、JobAttempt、JobLease|JobService、WorkerPort|platform、audit|
|ai|统一 AI Gateway、Provider/Model、Prompt Registry 与调用记录|AIProvider、AIModel、PromptTemplate、AITask、AIInvocation|AIService、PromptRegistry、ModelRouter|jobs、audit|
|rag|Chunk、Embedding Index、Hybrid Retrieval、Reranker、Context Builder|DocumentChunk、EmbeddingIndex、EmbeddingRecord、RetrievalRun|RetrievalService、IndexService|project、document、ai、jobs、audit|
|capability|GLOBAL 标准能力基线、版本与能力项|CapabilityBaseline、BaselineVersion、CapabilityItem|CapabilityService|document、review、trace、audit|
|handover|项目交接分析、差异/缺失/风险与行动项|HandoverAnalysis、AnalysisItem、ActionItem|HandoverService|project、document、evidence、ai、rag、review、trace、audit|
|survey|调研版本、轮次、问题、分派、回答与结论|Survey、SurveyVersion、SurveyRound、Question、Assignment、Response、Answer、Conclusion|SurveyService|project、document、evidence、ai、rag、review、trace、audit|
|requirement|需求包、需求版本、来源、关系与验收标准|RequirementPackage、Requirement、RequirementVersion、RequirementSource、RequirementRelation、AcceptanceCriterion|RequirementService|project、evidence、ai、rag、review、trace、audit|
|prototype|原型包、模板、版本与需求映射|PrototypePackage、Prototype、PrototypeVersion、PrototypeTemplate、RequirementPrototypeLink|PrototypeService|project、requirement、document、review、trace、audit|
|solution|参考方案、方案大纲/章节版本与结构化专项|ReferenceSolution、SolutionOutline、SolutionSection、ProcessModel、InterfaceSpec、MigrationSpec、PermissionDesign|SolutionService|project、requirement、prototype、evidence、ai、rag、review、trace、audit|
|plan|计划、WBS、FS 依赖、里程碑与参考计划|Plan、WbsItem、WbsDependency、Milestone、ReferencePlan|PlanService|project、solution、review、trace、audit|
|output|输出上下文、输出任务与制品编排；不自行实现 DOCX/PPTX 渲染器|OutputRequest、OutputContext、OutputArtifact|OutputService|project、document、solution、plan、plugin、trace、audit|
|plugin|开发者插件包、Manifest、启停、兼容检查和子进程生命周期|PluginPackage、PluginInstallation、PluginExecution|PluginService、PluginApi|jobs、audit|
|license|License 导入、验签、机器绑定、有效期与运行许可状态|LicenseInstallation、LicenseValidationState|LicenseService|audit|
|developer_workbench|离线签发 License、签名开发者插件和制作发行材料|仅开发侧私有密钥与签发记录，不进入客户数据库|LicenseIssuer、PluginSigner、ReleaseBuilder|不依赖客户运行数据库|

模块中的实体名称是边界候选，不代表字段或表已经冻结。

## 强制依赖规则

1. API 层只调用目标模块的 Application Port，不直接访问 Repository、ORM 或数据库。
2. 业务模块不得导入其他模块的 Domain/Repository 实现；跨模块读取通过 Query/Application Port，跨模块写入通过目标模块命令或 Domain Event。
3. `ai` 是唯一外部模型入口；业务模块不得出现 Provider SDK、厂商 URL 或模型分支。
4. `rag` 是唯一向量/全文检索入口；业务模块不得写 pgvector SQL。
5. `plugin` 是唯一子进程入口；`output` 和业务模块不得直接启动进程。
6. `review`、`trace`、`audit` 是公共能力，不在每个业务模块重复实现。
7. `document` 拥有文件元数据和版本；其他模块只保存 `document_id` / `document_version_id`，不得复制文件路径作为业务事实。
8. PROJECT 资源的 Application Port 必须接收并校验 `project_id`；GLOBAL Capability 不得反向写项目业务表。
9. `license` 在 API 请求入口完成有效性检查，但不得绕过 Auth、Project、Role、资源状态等后续授权链。
10. `developer_workbench` 与客户运行时物理分离；客户侧只包含公钥和签名制品。

## 允许的数据流

```text
Document → Evidence / RAG
Handover → Survey → Requirement → Prototype → Solution → Plan → Output
Capability ────────────────┘              │
Review ── controls formalization of each formal artifact
Trace ─── links every upstream/downstream version
AI/RAG ── produce suggestions only; never directly promote formal state
```

箭头表示业务输入或 Application Port 调用，不表示下游模块可以写上游模块表。

## 事务与事件边界

- 单模块命令：同一数据库事务内完成 Domain 变更、Outbox/Job 记录和 Audit 记录。
- 跨模块流程：调用目标 Application Port；长任务写 PostgreSQL Job Table，由 Worker 执行。
- 不引入分布式事务、Redis、消息队列或事件总线产品；Domain Event 首版为进程内协调和持久化 Job/Outbox 记录。
- 失败重试必须幂等；正式对象的版本创建不得覆盖历史版本。

## 禁止依赖

|来源|禁止目标/行为|
|---|---|
|Vue/UI|数据库、文件系统、Provider、Plugin 进程|
|业务模块|DeepSeek/百炼/其他厂商 SDK、pgvector SQL、subprocess|
|Plugin|数据库、License 私钥、AI Key、Provider 直连|
|RAG|修改 Requirement/Solution 等正式业务对象|
|AI|把模型输出直接写成 Formal Requirement/Solution/Plan|
|下游业务模块|直接更新上游模块表或覆盖上游版本|
|客户运行时|Developer Workbench 私钥、任意第三方插件安装|

## AF-01 验收

- V1 Scope 的 Platform、AI/RAG、七个核心业务域、Output、Plugin、License、Developer Workbench 均有唯一职责：PASS。
- Output 与 Plugin 边界明确，未新增渲染技术栈：PASS。
- 跨模块依赖均可映射为 Application Port、Domain Event、TraceLink 或 DTO：PASS。
- 未引入微服务、Redis、消息队列、独立向量库、本地模型或容器插件：PASS。
- 文件仅为候选，未提前冻结实体字段、表结构或 `/api/v1`：PASS。

## 下一步

AF-02：为 AIService、RetrievalService、PluginService、TraceService、ReviewService 以及 ProjectAuthorizationService 定义技术无关的 Application Contract 候选，并建立跨模块事件清单。
