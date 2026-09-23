# PLM 项目实施辅助工具 API Contract Candidate V1

## 状态

`API-CONTRACT-CANDIDATE-V1 / API-01～API-05_PASS / GATE_2_PENDING / DESIGN_FROZEN_CANDIDATE / NO_FASTAPI_IMPLEMENTATION / NO_EXTERNAL_CALLS`

本文件是 API-01～API-04 的单一汇总候选，统一 `/api/v1` 的资源、Operation、DTO、受控枚举、权限、安全控制、错误、SSE、兼容性和测试边界。详细端点继续由四份受控明细定义，机器目录由 API-05 Contract Lint 从明细确定性生成。Gate 2 正式确认前，本候选不授权创建生产 FastAPI Router、Pydantic DTO、ORM、Migration 或业务模块。

## 候选标识与规范来源

|项目|值|
|---|---|
|Candidate ID|`API-CONTRACT-CANDIDATE-V1`|
|Protocol|HTTPS + REST/JSON + multipart + SSE|
|Version prefix|`/api/v1`|
|Owner count|22|
|Aggregate Root count|65|
|Operation ID count|323|
|展开 Method/Path 变体|363|
|统一错误码|150|
|SSE event type|18|
|Schema Query 映射|20|
|Gate|Gate 2 待用户正式确认|

规范来源：

1. `api-01-resource-common-protocol-v1-candidate.md`：资源目录与公共 HTTP/Security 协议。
2. `api-02-platform-security-document-governance-v1-candidate.md`：平台、安全、项目、文档、Evidence、Review、Trace、Audit、License。
3. `api-03-ai-rag-job-plugin-output-v1-candidate.md`：AI、RAG、Job、Plugin、Output 与逐次外发授权。
4. `api-04-implementation-business-chain-v1-candidate.md`：Capability 到 Plan 的实施业务主链。
5. `validation/api-05-contract-lint/generated/api-contract-manifest-v1.json`：从以上明细生成的 Root、Operation、错误、SSE、Query 和枚举机器目录。

若表述出现差异，优先级为：用户最新明确变更 > Gate 2 正式冻结结果 > 本汇总候选统一规则 > API-01～04 中较晚且更具体的模块规则 > 较早阶段假设。机器目录只索引规范，不替代规范正文；源文件 Hash 不一致时必须重新生成并通过 lint。

## 统一资源与暴露目录

|Owner|Root IDs|Root 数|主要 API family|
|---|---|---:|---|
|platform|PLT-01、PLT-02|2|`/api/v1/admin/configurations`、`/api/v1/admin/secrets`|
|auth|AUT-01、AUT-02|2|`/api/v1/auth`、`/api/v1/admin/users`|
|project|PRJ-01、PRJ-02、PRJ-03|3|`/api/v1/projects` 及成员/部门嵌套资源|
|workflow|WFL-01、WFL-02|2|`/api/v1/projects/{project_id}/workflow`|
|review|RVW-01、RVW-02|2|`/api/v1/projects/{project_id}/reviews`|
|trace|TRC-01|1|`/api/v1/projects/{project_id}/trace-links`|
|audit|AUD-01|1|项目/部署只读 Audit 与受审导出|
|license|LIC-01、LIC-02、LIC-03|3|`/api/v1/admin/license` 最小恢复面|
|document|DOC-01、DOC-02、DOC-03、DOC-04|4|PROJECT/GLOBAL documents、upload、parse、content|
|evidence|EVD-01、EVD-02|2|PROJECT/GLOBAL evidence、binding、viewer|
|jobs|JOB-01、JOB-02|2|项目 Job 投影；Lease/Outbox 内部/受控运维|
|ai|AI-01、AI-02、AI-03、AI-04|4|部署 AI 配置与项目 AITask/Suggestion|
|rag|RAG-01、RAG-02、RAG-03、RAG-04|4|Index、RetrievalRun；Chunk/Embedding 内部|
|capability|CAP-01、CAP-02|2|GLOBAL capability baseline/version/item|
|handover|HND-01、HND-02、HND-03|3|交接分析版本与 ActionItem|
|survey|SRV-01、SRV-02、SRV-03、SRV-04、SRV-05|5|调研定义、Round、Assignment、Conclusion|
|requirement|REQ-01、REQ-02、REQ-03、REQ-04|4|需求包、身份/版本与关系|
|prototype|PRT-01、PRT-02、PRT-03、PRT-04、PRT-05|5|原型包、版本、模板与需求链接|
|solution|SOL-01、SOL-02、SOL-03、SOL-04、SOL-05、SOL-06|6|参考方案、目录、章节与专项设计|
|plan|PLN-01、PLN-02、PLN-03|3|参考计划、PlanVersion 与 WBS|
|output|OUT-01、OUT-02|2|OutputRequest 与受权 Artifact|
|plugin|PLG-01、PLG-02、PLG-03|3|签名 Package/Installation 与 Execution 投影|

暴露分类为 DIRECT 34、NESTED 18、READ_ONLY 6、INTERNAL 7，合计 65。暴露不等于授权；未登记 Operation 默认拒绝。FileObject、Session、Chunk、Embedding、Job Lease/fencing、Outbox delivery、TrustedTimeState 等内部 Root 不提供通用 CRUD。

## Operation 与路径目录

|详细来源|Operation ID|展开路径变体|范围|
|---|---:|---:|---|
|API-02|86|由机器目录展开|Platform/Auth/Project/Workflow/Review/Document/Evidence/Trace/Audit/License|
|API-03|79|由机器目录展开|AI/RAG/Job/Plugin/Output|
|API-04|158|由机器目录展开|Capability/Handover/Survey/Requirement/Prototype/Solution/Plan|
|**合计**|**323**|**363**|22 Owner 全覆盖|

- Operation ID 在全局唯一；Method + 展开 Path 组合在全局唯一。
- PROJECT 资源路径必须显式包含 `{project_id}`，并与 Session 成员、资源归属及所有 DTO 引用逐项复核。
- `{scope_base}`、`{solution_scope}`、`{plan_scope}` 只用于设计文档压缩；OpenAPI 必须展开为明确的 PROJECT 与 GLOBAL Path，不允许客户端提交自由 Scope 路径。
- GET/HEAD 不改变状态；创建使用 POST，受控元数据修改使用 PATCH，状态迁移使用 `POST ...:action`。V1 无通用 DELETE。
- 不可变 Version 无 PATCH；修订创建新 Version。Append-only 历史通过 revoke/supersede/replacement 表达。

机器目录为 OpenAPI/Router 实现输入，不是可部署 OpenAPI 文档。Gate 2 后实现必须从同一受控常量源生成实际 OpenAPI，并以 Operation/Path/Schema diff 检查与本候选一致。

## 公共 HTTP 与安全协议

### Envelope 与类型

- JSON 成功：`{"data": ..., "trace_id": "uuid"}`；所有 JSON 成功都有 data/trace_id，不使用空体 204。
- JSON 错误：`{"error": {"code": "...", "message": "安全本地化信息", "details": []}, "trace_id": "uuid"}`。
- 时间为 UTC RFC 3339 `...Z`；日期为 `YYYY-MM-DD`；ID 为 canonical lowercase UUID；枚举为 UPPER_SNAKE_CASE。
- 金额/高精度数使用十进制字符串。未知请求字段和未知枚举失败关闭；响应可增加可选字段。
- 错误不得包含 traceback、SQL/SQLSTATE、表/列名、绝对路径、Cookie/Token、Secret、Provider 原始响应或他项目标识。

### 固定检查顺序

```text
Trace/Security Context
→ License Guard
→ Server Session
→ CSRF（状态改变）
→ Deployment/Project Role
→ ProjectId + Resource Ownership
→ Resource State + Review Lock + If-Match
→ Owner Application Port
→ Audit
```

- Session Cookie 为 HttpOnly `plm_session`；生产 Secure、SameSite=Lax。CSRF Header 为 `X-CSRF-Token`，Token 仅在前端内存保存。
- 无权、不存在、跨项目对普通主体统一 `404 RESOURCE_NOT_FOUND`；内部差异只进入安全 Audit。
- 可变 Root 使用强 ETag 与 `If-Match`；缺失返回 428，冲突返回 409。可重试写使用 16～128 字符 `Idempotency-Key`。
- 列表只用绑定资源族、授权 Scope 与查询指纹的不透明 keyset cursor；page size 默认 50、最大 200，禁止 SQL/列名/任意 filter/order 表达式。
- API DTO 不接受 body 中的 actor_id/project_id 覆盖安全上下文；Worker 继承原 actor/project/purpose/trace 授权快照。

## DTO 与引用目录

|DTO 家族|统一约束|
|---|---|
|Envelope/Page|Success、Error、FieldDetail、CursorPage、Trace ID|
|Security Context|SessionView、CsrfToken、Role/Scope、ETag/If-Match、Idempotency；Token/Secret 不回显|
|Stable Ref|ObjectRef、ResourceVersionRef、EvidenceRef、ReviewSubjectRef、AITaskRef、JobRef、ArtifactRef；正式关系只用固定 version_id|
|Identity/Version|可变 Identity metadata + lock_version；不可变 Version content_fingerprint/version_no/supersedes/source refs|
|Review/Evidence/Trace|固定主题版本、Reviewer/Decision、typed Evidence Locator、逐节点授权 Trace graph|
|File/Document|UploadIntent、stream result、DocumentVersion、ParseRef、ViewerDescriptor；不返回 Storage Locator|
|AI/RAG|EgressPreview/Authorization、Provider/Model/Prompt policy refs、AITask/Suggestion、Index/Run/Context；建议为 NOT_FORMAL_FACT|
|Job/Plugin/Output|Job 安全投影、签名包/安装、Execution 安全结果、OutputRequest/Artifact；不返回 Lease/stdio/PID|
|Implementation Chain|Capability、Handover、Survey、Requirement、Prototype、Solution、Plan 的 Identity/Version/Validation/Review DTO|

多态引用只允许 API 白名单 object_type + id + 固定 version_id + Scope；Owner 由服务端解析，不暴露数据库 owner_module/FK。Evidence Locator 仅允许 DOCUMENT/PAGE/TEXT_RANGE/SECTION/PARAGRAPH/TABLE_CELL/SHEET_RANGE/SLIDE_SHAPE/STRUCTURED_NODE 判别联合。

## 受控枚举目录

机器目录冻结 18 个跨模块核心枚举族：

|枚举族|值|
|---|---|
|Scope|DEPLOYMENT、GLOBAL、PROJECT、GLOBAL_OR_PROJECT|
|ProjectRole|DEPLOYMENT_ADMIN、PROJECT_MANAGER、IMPLEMENTATION_MEMBER、CUSTOMER_MANAGER、CUSTOMER_MEMBER、SYSTEM_ACTOR|
|Exposure|DIRECT、NESTED、READ_ONLY、INTERNAL|
|VersionState|DRAFT、IN_REVIEW、APPROVED、RETURNED、SUPERSEDED、RESTRICTED|
|ReviewDecision|APPROVE、RETURN|
|FactStatus|NOT_FORMAL_FACT|
|EvidencePurpose|SUPPORTS、CONTRADICTS、DERIVED_FROM、REFERENCE_ONLY|
|JobState|PENDING、RUNNING、RETRY_WAIT、SUCCEEDED、FAILED、CANCEL_REQUESTED、CANCELLED|
|RequirementClassification|STANDARD_FUNCTION、NONSTANDARD_FUNCTION、DIFFERENCE、PENDING_CONFIRMATION|
|CapabilityMatch|DIRECT、PARTIAL、NONE、UNKNOWN|
|HandoverItemType|GAP、MISSING、CONFLICT、RISK、SCOPE、NEED_CONFIRM|
|ActionItemState|OPEN、IN_PROGRESS、SUBMITTED、VERIFIED、CLOSED、CANCELLED|
|SurveyRoundState|PLANNED、OPEN、CLOSED、CANCELLED|
|SurveyAssignmentState|ASSIGNED、IN_PROGRESS、SUBMITTED、VALIDATED、RETURNED|
|PrototypeState|ACTIVE、NOT_REQUIRED、ARCHIVED、RESTRICTED|
|ReferenceEligibility|REFERENCE_ONLY、ELIGIBLE、RESTRICTED、REVOKED|
|StructuredSpecType|PROCESS_MODEL、INTERFACE_SPEC、MIGRATION_SPEC、PERMISSION_DESIGN|
|WbsDependencyType|FS|

模块局部状态/类型继续以 API-02～04 对应 DTO 为准。冻结后删除、改名、改变语义或新增请求必填枚举值属于 Breaking Change；不得用 UNKNOWN/OTHER 静默接受未知值，除非该字段规范明确允许该业务值。

## Role × Operation × Scope 基线

|主体|部署/GLOBAL|所属 PROJECT|禁止边界|
|---|---|---|---|
|DeploymentAdmin|配置、User、License、Provider/Model、GLOBAL Capability、签名 Plugin|只有显式成为项目成员后按项目角色访问|不得成为隐式项目数据超级用户|
|ProjectManager|无部署 Secret/License 权|项目全链管理、送审、状态命令、受权 AI/输出|不得跨项目、绕过 Review/Audit|
|ImplementationMember|无部署管理权|创建/修订分析、调研、需求、原型、方案、计划和受权 AI/输出|不得替客户 Review、直接正式化 AI|
|CustomerManager|无部署管理权|项目读取、调研组织/答复、Review、范围/风险确认|不得替实施方生成正式版本|
|CustomerMember|无部署管理权|本人 Assignment/Review 与明确授权的最小读取|不得批量枚举工作区或跨项目|
|SystemActor|无交互登录|仅授权快照内的固定 Owner Port|不得创建授权、扩大 Scope 或替人工决定|

每个 Operation 的具体角色字符串、S/L/C/I/M/E/A 控制和结果在机器目录及明细中逐项登记。未登记角色、Scope、资源状态或 License 场景即拒绝。

## AI/RAG、异步与外发

- 业务模块只调用 AIService/RetrievalService/PluginService/OutputService，不提交厂商 SDK、原始 API Key、任意 endpoint、pgvector SQL 或 Plugin 入口路径。
- 外发必须先 preview，再由具备权限的人员授权；授权绑定 Provider、region、purpose、source version、payload fingerprint、上限、期限和一次逻辑操作。
- 仅 5 个 Operation 带 `E`：AI_TASK_CREATE、AI_TASK_RETRY、RAG_INDEX_BUILD、RAG_INDEX_REBUILD、RAG_RETRIEVAL_CREATE。
- 同 payload 的有界重试可复用本次授权；Provider/region/purpose/source/payload 变化必须重新授权。PoC、历史轮次或其他任务授权不得复用。
- 长任务短事务返回 `202 + JobRef`；Job/Outbox 至少一次、消费者幂等，Lease/fencing 不开放浏览器修改。
- AI Suggestion 永远为 NOT_FORMAL_FACT；Accept-to-draft 由目标 Owner 创建 Draft，正式化仍需 Evidence、业务校验和 Review。

## 文件、Evidence、版本与实施主链

- 上传固定为 UploadIntent → 流式 Content → 幂等 Commit；完成类型/大小/特征/Hash 与原子持久化后才创建 DocumentVersion/Parse Job。
- 文件下载/Viewer 每次重新授权；不返回绝对路径或静态文件 URL。Evidence 指向固定 DocumentVersion + typed locator。
- 正式对象采用逻辑 Identity + 不可变 Version；ReviewRound 绑定固定版本与指纹，Returned 后新建版本和 Round。
- 实际调研记录/客户原始答复优先于 TEMPLATE；模板、参考方案和 AI 不自动成为客户事实。
- Requirement 四分类、Prototype NOT_REQUIRED、Solution 覆盖/IMPLEMENTS Trace、Plan 六级/FS DAG 均按 API-04 失败关闭。
- 上游 Approved Version 被替代只生成 UPSTREAM_CHANGED 影响项，不自动改写下游版本或交付。

## 150 个统一错误码

|HTTP|数量|主要语义|
|---:|---:|---|
|400|1|请求/游标无法解析|
|401|3|认证或 Session|
|403|12|CSRF、License、授权快照、外发/Plugin 拒绝|
|404|3|资源/Scope 不泄露|
|409|59|并发、状态、版本、图、覆盖与运行冲突|
|413|2|文件或外发载荷超限|
|415|1|文件类型不支持|
|422|58|字段/业务规则/Schema 校验|
|428|1|缺少 If-Match|
|429|1|高风险入口限速|
|500|1|安全内部错误|
|502|1|Plugin 协议失败|
|503|7|关键依赖不可用|

机器码及 HTTP 映射以 manifest 为统一索引、API-01～04 为语义正文。客户端只能按 code 判断，不按 message 文本判断。冻结后既有 code 的 HTTP/语义不得静默改变。

## SSE 统一目录

18 个 event type 覆盖 AI/RAG/Job/Plugin/Output 与 Handover/Survey/Requirement/Prototype/Solution/Plan。SSE data 只含 event_id、event_type、occurred_at、project/resource/version ref、state、progress、trace_id 的安全子集；不含正文、回答、Prompt/响应、query、Context、向量、Secret、Cookie、路径、Outbox payload 或 Plugin stdio。

- 项目流：`/api/v1/projects/{project_id}/events`；部署受权流：`/api/v1/admin/events`。
- 订阅与每次事件发送均重新授权；撤权/归档后断流。
- `Last-Event-ID` 只支持受限恢复窗口；超窗重新 GET，不承诺永久事件存储。
- event type 全局唯一；新增事件必须保持 payload 最小化和向后兼容。

## 20 个 Schema Query 映射

|Query ID|API/Application 映射|
|---|---|
|Q-AUTH-01|AUTH_LOGIN|
|Q-PRJ-01|PROJECT_LIST|
|Q-PRJ-02|PROJECT_MEMBER_LIST、PROJECT_DEPARTMENT_LIST|
|Q-WFL-01|WORKFLOW_GET、WORKFLOW_TRANSITION_LIST|
|Q-VER-01|Document/Capability/Handover/Survey/Requirement/Prototype/Solution/Plan Version List|
|Q-RVW-01|REVIEW_LIST、REVIEW_GET|
|Q-DOC-01|DOCUMENT_VERSION_GET、DOCUMENT_PARSE_LIST|
|Q-EVD-01|EVIDENCE_LIST、EVIDENCE_GET|
|Q-TRC-01|TRACE_GRAPH_UPSTREAM、TRACE_GRAPH_DOWNSTREAM|
|Q-AUD-01|AUDIT_PROJECT_LIST、AUDIT_ADMIN_LIST|
|Q-JOB-01|JOB_ADMIN_LIST|
|Q-JOB-02|内部 JobService 过期 Lease 回收 Port|
|Q-OUT-01|内部 OutboxDispatcher 到期领取 Port|
|Q-RET-01|内部 RetentionService 到期候选 Port|
|Q-RAG-01|RAG_RETRIEVAL_CREATE、RAG_RETRIEVAL_RESULT_GET|
|Q-RAG-02|同上，由 RetrievalService 受控 exact fallback|
|Q-REQ-01|REQ_RELATION_LIST|
|Q-WBS-01|PLAN_VERSION_WBS_LIST、PLAN_VERSION_GET|
|Q-PLG-01|内部 PluginService.invoke + PLUGIN_INSTALLATION_LIST|
|Q-OUTPUT-01|OUTPUT_REQUEST_LIST、OUTPUT_ARTIFACT_LIST|

映射表示受权 Application Port/Operation 消费查询能力，不允许客户端提交 SQL、索引名、执行计划或 Worker 内部参数。

## 兼容性与变更规则

- 冻结后的 `/api/v1` 可新增可选响应字段、全新非冲突端点和新错误码；客户端必须容忍响应新增字段。
- 删除/改名 Path、Operation、请求/响应字段，改变类型/Null/默认/枚举/错误语义，新增请求必填字段或放宽安全边界均为 Breaking Change。
- Breaking Change 使用新端点、`/api/v2` 或 API Change Request；不得在普通实现任务中静默修改。
- Header/Cookie、Idempotency/ETag、Cursor、Envelope、固定 VersionRef 与错误码属于公共兼容面。
- 实际 FastAPI OpenAPI 必须通过 manifest diff：Root/Owner、Operation ID、Method/Path、请求/响应 Schema、角色控制、错误和 SSE 不得遗漏。

## API-05 自动一致性证据

|检查|结果|
|---|---|
|API Root 与 Schema Manifest|65/65 一致，22/22 Owner|
|暴露分类|DIRECT 34、NESTED 18、READ_ONLY 6、INTERNAL 7|
|Operation|323/323 ID 唯一；363/363 Method+Path 变体唯一|
|写安全|除匿名登录外状态写均 CSRF；PATCH 全部 If-Match；可重试 POST 幂等|
|外发|5/5 Operation 精确带 E 控制|
|错误/SSE|150/150 错误唯一映射；18/18 event type 唯一|
|Schema Query|20/20 映射到公开 Operation 或明确 INTERNAL_PORT|
|枚举|18/18 核心枚举族非空、值唯一且为 UPPER_SNAKE_CASE|
|删除/外部调用|通用 DELETE 0；真实外部调用 0|
|回归测试|5/5 PASS|

详细结果见 `validation/api-05-contract-lint/evidence/windows-11/result.json`。这是静态 Contract 证据，不是 API 运行、性能、UAT 或跨平台实机验证。

## 统一风险与 Gate 2 后关闭位置

|Risk ID|风险|当前控制|关闭位置|
|---|---|---|---|
|API5-R01|Markdown 与实际 OpenAPI 漂移|Hash manifest + Operation/Schema diff|基础工程 CI|
|API5-R02|角色自然语言未落实为策略常量|逐 Operation 角色/控制目录、默认拒绝|Auth/Permission 实现测试|
|API5-R03|无 RLS 时 Repository 漏 Project 条件|ProjectId 双检、Owner Repository、跨项目 404|跨项目 API/SQL 负测|
|API5-R04|多态 Ref 悬空或越 Scope|白名单 Ref + Owner Port + 复合约束|ORM/Migration/集成测试|
|API5-R05|Review 事件重复/丢失导致正式指针漂移|Outbox 至少一次、Owner 幂等短事务|故障注入测试|
|API5-R06|文件/数据库非原子导致孤儿|STAGED、Hash、原子提升、恢复器|文件集成/恢复测试|
|API5-R07|外发授权被错误复用|不可变授权快照、5 个 E Operation 白名单|AI/RAG 安全测试|
|API5-R08|Job/Outbox/Plugin 重试造成重复副作用|幂等、fencing、结果指纹、发布复验|并发/故障测试|
|API5-R09|SSE/Trace/Evidence 泄露无权元数据|逐节点/逐事件授权、最小 DTO|Permission/leakage 测试|
|API5-R10|业务版本被实现为可变记录|无 Version PATCH/DELETE、指纹/Review 锁|Domain/DB 绕过负测|
|API5-R11|正式 Schema 仍只有候选 Profile|Gate 2 后按模块正式 ORM/Migration|各模块 Schema WBS|
|API5-R12|性能指标尚未由真实 API 验证|不在候选中声明性能 PASS|Gate 3/Integration 性能测试|
|API5-R13|POC-03 分类/引用质量失败|NOT_FORMAL_FACT、Evidence、强制 Review|Gate 3/UAT 新留出集|
|API5-R14|Server Office 与 Debian 范围未完整实机验证|保留批准例外，不外推结果|Release Gate|
|API5-R15|Ghostscript AGPL 发行合规未完成|ADR-002、当前仅开发验证|公开源码/许可证/第三方声明 Gate|

上述均已登记并有关闭 Gate，不构成 API Contract 候选内部冲突。若关闭风险需要改变技术栈、Scope、总体架构、安全/License 核心机制或已冻结 API，则按 L3/API Change Request 处理。

## API-05 验收

- API-01～API-04 纳入单一 `API-CONTRACT-CANDIDATE-V1`，规范优先级明确：PASS。
- 22 个 Owner、65 个 Root 与 Schema Manifest 完整一致：PASS。
- 323 个 Operation ID、363 个展开 Method/Path 变体全局唯一：PASS。
- Envelope、Session/CSRF、License、Project 隔离、ETag/If-Match、幂等和分页统一：PASS。
- DTO/固定引用、18 个核心枚举族和内部字段禁止清单统一：PASS。
- 六类主体的 Role × Operation × Scope 默认拒绝边界明确：PASS。
- 逐次外发授权、AI 建议态、RAG 隔离、Job/Plugin/Output 内部边界统一：PASS。
- 文件、Evidence、Review、Trace 与实施业务正式化链统一：PASS。
- 150 个错误码、18 个 SSE event type 和 20 个 Query ID 映射完整：PASS。
- `/api/v1` 兼容性、Breaking Change 与实际 OpenAPI diff 规则明确：PASS。
- 15 项统一风险具有当前控制和后续关闭位置：PASS。
- Contract Lint 5/5 测试通过，通用 DELETE 0，真实外部调用 0：PASS。
- 未创建生产 FastAPI/Pydantic/ORM/Migration 或业务实现：PASS。
- Gate 2 未被自动批准，正式业务编码继续阻塞：PASS。

## Gate 2 结论边界

`API-CONTRACT-CANDIDATE-V1` 满足 API Contract V1 候选条件。Architecture、Data Model、DB Schema 与 API Contract 四份候选现已齐备，应由用户执行 Gate 2 正式确认。确认前状态保持 `GATE_2_PENDING`；确认后才可把四份候选标记为冻结基线并进入正式基础工程/业务编码。
