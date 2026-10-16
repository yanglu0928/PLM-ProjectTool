# API-02：平台、安全、文档与治理 Contract V1 候选

## 状态

`CANDIDATE / API-02_COMPLETE / API-03_NEXT / NOT_GATE_2_FROZEN / NO_FASTAPI_IMPLEMENTATION`

本文件在 API-01 公共协议上，冻结 Platform、Auth、Project、Workflow、Document、Evidence、Review、Trace、Audit 与 License 的 V1 路径、Operation ID、DTO、权限、错误和审计契约。它不创建 FastAPI Router、Pydantic Model、Service、ORM 或 Migration。

## 范围与 Root 覆盖

|Owner|Root IDs|数量|API 边界|
|---|---|---:|---|
|platform|PLT-01、PLT-02|2|Configuration 与 Secret metadata/write-only value|
|auth|AUT-01、AUT-02|2|User 与受控 Session 命令|
|project|PRJ-01、PRJ-02、PRJ-03|3|Project、Member、Department|
|workflow|WFL-01、WFL-02|2|Workflow 状态、Checklist 和追加 Transition|
|review|RVW-01、RVW-02|2|Review identity、不可变版本 Round 与 Decision|
|trace|TRC-01|1|Version graph link/query/supersede|
|audit|AUD-01|1|只读时间线与受审导出|
|license|LIC-01、LIC-02、LIC-03|3|安装、验证状态与内部可信时间|
|document|DOC-01、DOC-02、DOC-03、DOC-04|4|Document/version/upload/download/parse；FileObject 内部|
|evidence|EVD-01、EVD-02|2|Evidence/Viewer/Binding|

合计 10 个 Owner、22 个 Root，均与 API-01 资源目录一致。FileObject、Session、TrustedTimeState 等内部 Root 只通过专用命令或投影访问，不提供通用 CRUD。

## 控制标记

端点表使用以下标记：

|标记|含义|
|---|---|
|`S`|有效 Server Session|
|`L`|有效 License；License 恢复面除外|
|`C`|状态改变请求必须通过 CSRF|
|`I`|必须提供 `Idempotency-Key`|
|`M`|必须提供 `If-Match`|
|`A`|必须写 Audit|

所有 PROJECT 操作另行强制 ProjectId、成员状态、Role、资源归属和对象状态检查；表中不重复写 `P`。无权、跨项目和不存在对普通用户统一返回 `404 RESOURCE_NOT_FOUND`。

## Platform Configuration 与 Secret

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|PLATFORM_CONFIG_LIST|GET `/api/v1/admin/configurations`|DeploymentAdmin|S,L|配置 metadata page|
|PLATFORM_CONFIG_GET|GET `/api/v1/admin/configurations/{configuration_id}`|DeploymentAdmin|S,L|配置 identity、active version 与 ETag|
|PLATFORM_CONFIG_CREATE|POST `/api/v1/admin/configurations`|DeploymentAdmin|S,L,C,I,A|201 ConfigurationRef|
|PLATFORM_CONFIG_CREATE_VERSION|POST `/api/v1/admin/configurations/{configuration_id}/versions`|DeploymentAdmin|S,L,C,I,M,A|201 immutable version|
|PLATFORM_CONFIG_ACTIVATE|POST `/api/v1/admin/configurations/{configuration_id}/versions/{version_no}:activate`|DeploymentAdmin|S,L,C,I,M,A|200 active version projection|
|PLATFORM_SECRET_LIST|GET `/api/v1/admin/secrets`|DeploymentAdmin|S,L|Secret metadata page，永不含值/密文|
|PLATFORM_SECRET_GET|GET `/api/v1/admin/secrets/{secret_id}`|DeploymentAdmin|S,L|purpose/state/consumer/version metadata|
|PLATFORM_SECRET_CREATE|POST `/api/v1/admin/secrets`|DeploymentAdmin|S,L,C,I,A|201 SecretRef，不回显 value|
|PLATFORM_SECRET_ROTATE|POST `/api/v1/admin/secrets/{secret_id}:rotate`|DeploymentAdmin|S,L,C,I,M,A|200 新 version metadata，不回显 value|
|PLATFORM_SECRET_DISABLE|POST `/api/v1/admin/secrets/{secret_id}:disable`|DeploymentAdmin|S,L,C,I,M,A|200 disabled projection|

- Configuration value 只允许非敏感标量/受控 JSON，并携带 `schema_version`；Secret/API Key/密码/Token/客户正文提交到 Configuration 时返回 `PLATFORM_SENSITIVE_VALUE_FORBIDDEN`。
- Secret 请求中的 `secret_value` 是 write-only；响应、错误、Audit、Job、Outbox 和日志均不得出现原值或 encrypted payload。
- `allowed_consumer` 只接受受控 Adapter capability，不接受任意模块名、路径或插件 ID。

## Auth 与 User

### Session 面

|Operation ID|Method / Path|主体|控制|结果|
|---|---|---|---|---|
|AUTH_LOGIN|POST `/api/v1/auth/login`|Anonymous|Origin/Host、rate limit、A|200 SessionView + CSRF；设置 `plm_session`|
|AUTH_SESSION_GET|GET `/api/v1/auth/session`|Authenticated|S|SessionView；License 无效时仍可读取最小身份|
|AUTH_SESSION_RENEW|POST `/api/v1/auth/session:renew`|Authenticated|S,C,A|200 轮换 Session/CSRF|
|AUTH_LOGOUT|POST `/api/v1/auth/logout`|Authenticated|S,C,I,A|200 revoked；清除 Cookie|
|AUTH_PASSWORD_CHANGE|POST `/api/v1/auth/password:change`|Authenticated|S,C,I,A|200 credential version；撤销其他 Session|

- 登录输入只有 `username`、`password`；外部错误统一 `AUTH_INVALID_CREDENTIALS`，不区分用户不存在、停用或密码错误。
- 登录成功必须生成新 Session token 与 CSRF token；原始 token 只进入 HttpOnly Cookie/当前响应，不写数据库明文或日志。
- Password change 需要当前密码、新密码和幂等键；不得返回强度规则之外的凭据细节。

### User 管理面

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|AUTH_USER_LIST|GET `/api/v1/admin/users`|DeploymentAdmin|S,L|UserSummary page|
|AUTH_USER_GET|GET `/api/v1/admin/users/{user_id}`|DeploymentAdmin|S,L|UserView + ETag|
|AUTH_USER_CREATE|POST `/api/v1/admin/users`|DeploymentAdmin|S,L,C,I,A|201 UserView；初始密码 write-only|
|AUTH_USER_PATCH|PATCH `/api/v1/admin/users/{user_id}`|DeploymentAdmin|S,L,C,M,A|200 display metadata + ETag|
|AUTH_USER_ENABLE|POST `/api/v1/admin/users/{user_id}:enable`|DeploymentAdmin|S,L,C,I,M,A|200 ENABLED|
|AUTH_USER_DISABLE|POST `/api/v1/admin/users/{user_id}:disable`|DeploymentAdmin|S,L,C,I,M,A|200 DISABLED；撤销全部 Session|
|AUTH_USER_RESET_PASSWORD|POST `/api/v1/admin/users/{user_id}:reset-password`|DeploymentAdmin|S,L,C,I,M,A|200 credential version；临时密码永不回显|
|AUTH_USER_REVOKE_SESSIONS|POST `/api/v1/admin/users/{user_id}:revoke-sessions`|DeploymentAdmin|S,L,C,I,A|200 revoked count|

User DTO 不返回 password hash、credential algorithm parameters、Session token/hash 或 CSRF hash。username canonical 由服务端生成，客户端只提交显示 username。管理员重置时由请求提交 write-only `temporary_password` 与 `must_change_password=true`，响应和幂等结果均不返回密码。

## Project、Member 与 Department

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|PROJECT_LIST|GET `/api/v1/projects`|Authenticated|S,L|仅授权 Project page|
|PROJECT_GET|GET `/api/v1/projects/{project_id}`|Project member|S,L|ProjectView + ETag|
|PROJECT_CREATE|POST `/api/v1/projects`|DeploymentAdmin|S,L,C,I,A|201 ProjectView；原子创建首个 ProjectManager|
|PROJECT_PATCH|PATCH `/api/v1/projects/{project_id}`|ProjectManager|S,L,C,M,A|200 metadata + ETag|
|PROJECT_ARCHIVE|POST `/api/v1/projects/{project_id}:archive`|ProjectManager|S,L,C,I,M,A|200 ARCHIVED；禁止新写/Job|
|PROJECT_MEMBER_LIST|GET `/api/v1/projects/{project_id}/members`|ProjectManager、CustomerManager|S,L|Member page|
|PROJECT_MEMBER_CREATE|POST `/api/v1/projects/{project_id}/members`|ProjectManager|S,L,C,I,A|201 MemberView|
|PROJECT_MEMBER_PATCH|PATCH `/api/v1/projects/{project_id}/members/{project_member_id}`|ProjectManager|S,L,C,M,A|200 role/department + ETag|
|PROJECT_MEMBER_SUSPEND|POST `/api/v1/projects/{project_id}/members/{project_member_id}:suspend`|ProjectManager|S,L,C,I,M,A|200 SUSPENDED|
|PROJECT_MEMBER_RESUME|POST `/api/v1/projects/{project_id}/members/{project_member_id}:resume`|ProjectManager|S,L,C,I,M,A|200 ACTIVE|
|PROJECT_MEMBER_REMOVE|POST `/api/v1/projects/{project_id}/members/{project_member_id}:remove`|ProjectManager|S,L,C,I,M,A|200 REMOVED；历史保留|
|PROJECT_DEPARTMENT_LIST|GET `/api/v1/projects/{project_id}/departments`|Project member|S,L|Department page|
|PROJECT_DEPARTMENT_CREATE|POST `/api/v1/projects/{project_id}/departments`|ProjectManager|S,L,C,I,A|201 DepartmentView|
|PROJECT_DEPARTMENT_PATCH|PATCH `/api/v1/projects/{project_id}/departments/{department_id}`|ProjectManager|S,L,C,M,A|200 name/code + ETag|
|PROJECT_DEPARTMENT_DEACTIVATE|POST `/api/v1/projects/{project_id}/departments/{department_id}:deactivate`|ProjectManager|S,L,C,I,M,A|200 INACTIVE|

- `PROJECT_CREATE` 请求包含 project code/name、initial manager user_id 和可选 department seed；DeploymentAdmin 不因创建项目自动成为成员。
- 一个 User 同时最多一个未 REMOVED ProjectMember；跨项目添加返回 `PROJECT_USER_ALREADY_ASSIGNED`，不暴露另一个项目详情。
- Department 停用在仍有 ACTIVE/SUSPENDED Member 时返回 `PROJECT_DEPARTMENT_IN_USE`，除非同一专用迁移命令在后续 Contract 明确支持；V1 不静默迁移。
- Archived Project 只允许受权读取、审计、导出和恢复流程；V1 不提供普通反归档端点。

## Workflow 与 Stage Gate

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|WORKFLOW_GET|GET `/api/v1/projects/{project_id}/workflow`|Project member|S,L|WorkflowView、current stage、checklist、ETag|
|WORKFLOW_START|POST `/api/v1/projects/{project_id}/workflow:start`|ProjectManager|S,L,C,I,M,A|200 ACTIVE workflow|
|WORKFLOW_CHECKLIST_RECORD|POST `/api/v1/projects/{project_id}/workflow/checklist-items/{item_key}:record`|ProjectManager|S,L,C,I,M,A|200 checklist projection|
|WORKFLOW_TRANSITION|POST `/api/v1/projects/{project_id}/workflow:transition`|ProjectManager|S,L,C,I,M,A|200 new stage + immutable TransitionRef|
|WORKFLOW_TRANSITION_LIST|GET `/api/v1/projects/{project_id}/workflow/transitions`|Project member|S,L|追加历史 page|

- Checklist record 只接受 `PASS / FAIL / WAIVED`。WAIVED 必须含 reason、impact、evidence/approved-exception refs，不能把失败质量指标改写为 PASS。
- Transition 请求包含 `target_stage_key`、reason 和 gate_snapshot refs；from stage 由服务器从当前 Workflow 读取，不接受客户端伪造。
- Gate 未满足、非法跳级、Project Archived 或 If-Match 失败均不创建 StageTransition；失败写 Audit。

## Review

|Operation ID|Method / Path|角色/主体|控制|结果|
|---|---|---|---|---|
|REVIEW_LIST|GET `/api/v1/projects/{project_id}/reviews`|Project member|S,L|Review page|
|REVIEW_GET|GET `/api/v1/projects/{project_id}/reviews/{review_id}`|受权 Project member|S,L|Review/Round/Assignment projection + ETag|
|REVIEW_CREATE|POST `/api/v1/projects/{project_id}/reviews`|ProjectManager|S,L,C,I,A|201 Review identity|
|REVIEW_START_ROUND|POST `/api/v1/projects/{project_id}/reviews/{review_id}/rounds`|ProjectManager|S,L,C,I,M,A|201 IN_REVIEW round；锁定固定 subject version|
|REVIEW_DECIDE|POST `/api/v1/projects/{project_id}/reviews/{review_id}/rounds/{review_round_id}:decide`|本轮 assigned reviewer|S,L,C,I,A|200 assignment/aggregate status|
|REVIEW_WITHDRAW|POST `/api/v1/projects/{project_id}/reviews/{review_id}/rounds/{review_round_id}:withdraw`|ProjectManager|S,L,C,I,M,A|200 WITHDRAWN|

- `subject_ref` 由 `resource_type`、`resource_id`、必填 `version_id` 构成，project_id 从路径注入；API 不暴露 owner_module。
- Reviewer set 为 1～N 个互不重复且在项目内有效的 User；发起者不得以无资格身份替他人决定。
- Decision 为 `APPROVE / RETURN`；RETURN 必须有实质 comment。一个 reviewer 每轮只能产生一个最终 Decision。
- 任一 RETURN 则本轮 RETURNED；全部决定且无 RETURN 才 APPROVED。ReviewService 只发布结果，主题 Owner 才能更新正式状态/current approved version。
- Returned 后修改必须创建新业务 Version 和新 Round；旧 Decision 不覆盖。IN_REVIEW 期间主题版本及其内容 child 只读。

## Document 与三步上传

### Document 读取与元数据

以下 `{scope_base}` 仅用于本表压缩，实际 OpenAPI 展开为 `/api/v1/projects/{project_id}` 和 `/api/v1/global` 两套明确路径；不得把它实现为用户可控自由路径。

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|DOCUMENT_LIST|GET `{scope_base}/documents`|项目成员；GLOBAL 受权读|S,L|Document page|
|DOCUMENT_GET|GET `{scope_base}/documents/{document_id}`|受权主体|S,L|DocumentView + ETag|
|DOCUMENT_PATCH|PATCH `{scope_base}/documents/{document_id}`|项目 PM/IM；GLOBAL DeploymentAdmin|S,L,C,M,A|200 metadata + ETag|
|DOCUMENT_ARCHIVE|POST `{scope_base}/documents/{document_id}:archive`|项目 PM/IM；GLOBAL DeploymentAdmin|S,L,C,I,M,A|200 ARCHIVED|
|DOCUMENT_VERSION_LIST|GET `{scope_base}/documents/{document_id}/versions`|受权主体|S,L|immutable version page|
|DOCUMENT_VERSION_GET|GET `{scope_base}/documents/{document_id}/versions/{document_version_id}`|受权主体|S,L|DocumentVersionView|
|DOCUMENT_VERSION_DOWNLOAD|GET `{scope_base}/documents/{document_id}/versions/{document_version_id}/content`|受权主体|S,L|受权流式内容，不返回 locator|
|DOCUMENT_PARSE_LIST|GET `{scope_base}/documents/{document_id}/versions/{document_version_id}/parses`|受权主体|S,L|ParseRecord page|
|DOCUMENT_PARSE_RETRY|POST `{scope_base}/documents/{document_id}/versions/{document_version_id}/parses:retry`|项目 PM/IM；GLOBAL DeploymentAdmin|S,L,C,I,A|202 JobRef + ParseRecordRef|

### 上传协议

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|DOCUMENT_UPLOAD_CREATE|POST `{scope_base}/document-uploads`|项目 PM/IM/CustomerManager；GLOBAL DeploymentAdmin|S,L,C,I,A|201 UploadIntent，短时 upload token|
|DOCUMENT_UPLOAD_CONTENT|PUT `{scope_base}/document-uploads/{upload_id}/content`|创建者|S,L,C|200 size/hash/detected MIME；不创建业务版本|
|DOCUMENT_UPLOAD_COMMIT|POST `{scope_base}/document-uploads/{upload_id}:commit`|创建者|S,L,C,I,A|201 DocumentVersionRef + Parse JobRef|
|DOCUMENT_UPLOAD_ABORT|POST `{scope_base}/document-uploads/{upload_id}:abort`|创建者|S,L,C,I,A|200 cleanup-pending|

- UploadIntent 请求声明用途、document category、display name、size/mime hint，以及新建 Document 或给既有 document 升版；ProjectId/Scope 从路径固定。
- Content 使用流式请求；服务端检查配置限额、扩展名、声明 MIME、detected MIME、文件特征并同时计算 SHA-256。upload token 只绑定 upload_id/actor/project/期限，不是通用 Session 替代。
- Commit 只有在临时内容校验通过、同卷原子提升成功且 FileObject AVAILABLE 后才创建不可变 DocumentVersion；失败/半完成内容不可见。
- 同一 Document 升版 Commit 必须携带父 Document 的 If-Match。由于内容 PUT 可重传，Content 以 upload_id + Content-Length/Hash 检查，Commit 以 Idempotency-Key 防重复版本。
- DocumentVersion REVOKED/RESTRICTED、文件缺失或 Hash 不符时下载失败关闭并写完整性事件；不自动伪造文件或退回旧 locator。
- GLOBAL 写只允许 DeploymentAdmin；PROJECT 成员读取 GLOBAL 文档必须经引用/类别策略授权，知道 ID 不代表可读。

## Evidence 与 Viewer

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|EVIDENCE_LIST|GET `{scope_base}/evidence`|受权主体|S,L|Evidence page|
|EVIDENCE_GET|GET `{scope_base}/evidence/{evidence_id}`|受权主体|S,L|EvidenceView；excerpt 受限|
|EVIDENCE_CREATE|POST `{scope_base}/evidence`|项目 PM/IM；GLOBAL DeploymentAdmin|S,L,C,I,A|201 CANDIDATE Evidence|
|EVIDENCE_SET_ELIGIBILITY|POST `{scope_base}/evidence/{evidence_id}:set-eligibility`|项目 PM/受权 CustomerManager；GLOBAL DeploymentAdmin|S,L,C,I,M,A|200 ELIGIBLE/INELIGIBLE|
|EVIDENCE_VIEWER|GET `{scope_base}/evidence/{evidence_id}/viewer`|受权主体|S,L|固定 DocumentVersion + typed locator + short preview|
|EVIDENCE_BIND|POST `{scope_base}/evidence/{evidence_id}/bindings`|项目 PM/IM 或主题 Owner；GLOBAL DeploymentAdmin|S,L,C,I,A|201 active binding|
|EVIDENCE_BINDING_REVOKE|POST `{scope_base}/evidence/{evidence_id}/bindings/{binding_id}:revoke`|项目 PM/主题 Owner；GLOBAL DeploymentAdmin|S,L,C,I,A|200 revoked binding|
|EVIDENCE_BINDING_SUPERSEDE|POST `{scope_base}/evidence/{evidence_id}/bindings/{binding_id}:supersede`|项目 PM/主题 Owner；GLOBAL DeploymentAdmin|S,L,C,I,A|201 replacement binding|

- `locator` 是以 `locator_type` 判别的 union：DOCUMENT、PAGE、TEXT_RANGE、SECTION、PARAGRAPH、TABLE_CELL、SHEET_RANGE、SLIDE_SHAPE、STRUCTURED_NODE；每种只接受白名单字段。
- Evidence 必须指向固定 AVAILABLE DocumentVersion。display_excerpt 是受限提示，不是权威正文，不进入列表以外的非必要响应。
- AI 只能创建 CANDIDATE；ELIGIBLE/INELIGIBLE 是策略 + 受权人工命令。TEMPLATE 不得独立成为客户事实 Evidence。
- ViewerDescriptor 只含 document/version metadata、typed locator、定位精度和短 preview；点击定位通过受权 Viewer/Content route，不返回静态 URL 或绝对路径。
- Binding subject 必须是固定 version ref，purpose 只允许 SUPPORTS、CONTRADICTS、DERIVED_FROM、REFERENCE_ONLY。CONTRADICTS 不得从 Review/AI Context 中静默过滤。

## Trace

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|TRACE_LINK_LIST|GET `/api/v1/projects/{project_id}/trace-links`|Project member|S,L|按 source/target/type 白名单筛选的 page|
|TRACE_LINK_CREATE|POST `/api/v1/projects/{project_id}/trace-links`|ProjectManager、ImplementationMember、受控 Owner Service|S,L,C,I,A|201 TraceLinkRef|
|TRACE_LINK_REVOKE|POST `/api/v1/projects/{project_id}/trace-links/{trace_link_id}:revoke`|ProjectManager、关系 Owner|S,L,C,I,A|200 revoked|
|TRACE_LINK_SUPERSEDE|POST `/api/v1/projects/{project_id}/trace-links/{trace_link_id}:supersede`|ProjectManager、关系 Owner|S,L,C,I,A|201 replacement|
|TRACE_GRAPH_UPSTREAM|GET `/api/v1/projects/{project_id}/trace-graph:upstream`|Project member|S,L|受权 graph page|
|TRACE_GRAPH_DOWNSTREAM|GET `/api/v1/projects/{project_id}/trace-graph:downstream`|Project member|S,L|受权 graph page|

- source/target 使用固定 ResourceVersionRef；相同 Active edge 幂等。Evidence 支持关系只由 EvidenceBinding 表达，不重复创建 TraceLink。
- 请求限制 relation type、max_depth（默认 3、最大 10）、max_nodes（默认 100、最大 500）和 cursor；禁止无 Scope 全库递归。
- 查询逐节点/逐边授权；无权节点/边不返回占位标题、计数或存在性。过滤后图不完整时返回 `truncated=true`，不说明被过滤对象详情。
- PROJECT↔其他 PROJECT 禁止；PROJECT→GLOBAL 默认禁止；GLOBAL capability/reference→PROJECT 仅允许白名单关系。

## Audit

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|AUDIT_PROJECT_LIST|GET `/api/v1/projects/{project_id}/audit-events`|ProjectManager|S,L|项目 Audit page|
|AUDIT_PROJECT_GET|GET `/api/v1/projects/{project_id}/audit-events/{audit_event_id}`|ProjectManager|S,L|脱敏 Audit detail|
|AUDIT_ADMIN_LIST|GET `/api/v1/admin/audit-events`|DeploymentAdmin|S,L|部署安全 Audit page；不隐式包含客户正文|
|AUDIT_ADMIN_GET|GET `/api/v1/admin/audit-events/{audit_event_id}`|DeploymentAdmin|S,L|脱敏 Audit detail|
|AUDIT_EXPORT|POST `/api/v1/admin/audit-exports` 或 `/api/v1/projects/{project_id}/audit-exports`|对应 Admin/ProjectManager|S,L,C,I,A|202 JobRef；范围/用途受审|

- Audit 没有 create/update/delete 公共端点；仅 AuditService 可追加。
- 筛选白名单为时间范围、action、outcome、actor ref、object type/id 和 trace_id；时间范围/page size 有上限。
- DeploymentAdmin 不因部署角色获得项目正文；项目 Audit 导出需要显式项目成员权限。导出不包含 Secret、密码 hash、Session/CSRF、文件正文、Prompt/响应或 License 私钥。

## License 恢复面

License 无效时只允许最小健康、登录、当前 Session，以及已认证 DeploymentAdmin 的以下端点；这些端点不带 `L` 标记，但仍执行 Session/CSRF/Role/Audit。

|Operation ID|Method / Path|角色|控制|结果|
|---|---|---|---|---|
|LICENSE_STATUS|GET `/api/v1/admin/license/status`|DeploymentAdmin|S|LicenseStatusView；安全分类|
|LICENSE_INSTALLATION_LIST|GET `/api/v1/admin/license/installations`|DeploymentAdmin|S|导入历史 metadata page|
|LICENSE_IMPORT|POST `/api/v1/admin/license/installations`|DeploymentAdmin|S,C,I,A|201 Installation + validation result|
|LICENSE_REVALIDATE|POST `/api/v1/admin/license:revalidate`|DeploymentAdmin|S,C,I,A|200 new validation event/status|
|LICENSE_DIAGNOSTICS|GET `/api/v1/admin/license/diagnostics`|DeploymentAdmin|S|最小安全诊断，不回显原 MAC/签名 payload|

- Import 只接受签名 License document；客户 API 不接收、生成或返回 Ed25519 私钥。
- validation_code 至少包括 VALID、NOT_INSTALLED、MALFORMED、SIGNATURE_INVALID、MACHINE_MISMATCH、NOT_YET_VALID、EXPIRED、TIME_ROLLBACK。
- machine fingerprint 只以摘要/掩码显示；原始 MAC 不持久化、不进入 Audit/错误。
- TrustedTimeState 无公共写端点，只由 LicenseService/TrustedTimeStatePort 在成功验证时使用 expected version 单调前移。
- 导入失败保留脱敏验证事实和 Audit，但无效 License 不激活；新 Active 安装使旧安装 SUPERSEDED，不覆盖历史。

## DTO 目录

### 通用引用

|DTO|字段|约束|
|---|---|---|
|`ResourceRef`|resource_type、resource_id|resource_type 为 API 白名单，不暴露 owner_module|
|`ResourceVersionRef`|resource_type、resource_id、version_id|正式 Review/Evidence/Trace 引用 version_id 必填|
|`ActorRef`|actor_type、actor_id、display_name?|不返回 Session、credential 或 SystemActor 内部权限|
|`JobRef`|job_id、state、status_url|不返回 lease、fencing、payload、Outbox|
|`Page<T>`|items、next_cursor、has_more|遵循 API-01 keyset；不返回 total 除非有低成本明确需求|

### 平台与身份

|DTO|核心字段|永不返回|
|---|---|---|
|`ConfigurationView`|configuration_id、config_key、value_type、active_version、state、updated_at、etag|Secret/敏感业务正文|
|`SecretMetadataView`|secret_id、purpose、state、allowed_consumer、current_version_no、rotated_at|secret_value、encrypted_payload、nonce/tag、key material|
|`SessionView`|user、absolute/idle expiry、deployment role、authorized project summary、csrf_token（仅创建/轮换）|session token/hash、csrf hash、password metadata|
|`UserView`|user_id、username_display、account_state、deployment_role、credential_version、timestamps、etag|password hash/parameters、Session data|
|`ProjectView`|project_id、code、name、state、created_at、etag|current_stage 副本|
|`ProjectMemberView`|member_id、user summary、role、department、state、effective/ended、etag|其他项目 membership|
|`DepartmentView`|department_id、code、name、state、etag|跨项目成员统计|

### Workflow 与 Review

|DTO|核心字段|约束|
|---|---|---|
|`WorkflowView`|workflow_id/version/state/current_stage、stages/checklist summaries、etag|current stage 唯一来源|
|`ChecklistRecordRequest`|result、reason?、impact?、evidence_refs、exception_refs|WAIVED 时 reason/impact/依据必填|
|`StageTransitionRequest`|target_stage_key、reason、gate_snapshot_refs|from stage 由服务器确定|
|`ReviewView`|review_id、subject identity、state、active_round、etag|不复制主题正文|
|`StartReviewRoundRequest`|subject_version_ref、reviewer_user_ids、policy_code|1～N 唯一有资格 reviewer|
|`ReviewDecisionRequest`|decision、comment?|RETURN comment 必填；actor 从 Session|

### Document、Evidence 与 Trace

|DTO|核心字段|约束|
|---|---|---|
|`DocumentView`|document_id、scope、category/subtype、title/display name、state、latest/effective version refs、etag|storage_locator|
|`DocumentVersionView`|version_id/no、content_sha256、size、mime、availability、supersedes、created/integrity time|file path、parser traceback|
|`UploadIntentRequest`|purpose、category/subtype、display name、size/mime hint、document_id?、supersedes_version_id?|Scope/Project 来自路径|
|`ParseRecordView`|parse_record_id、profile/version、state/attempt、job_ref、result_ref?、safe error、timestamps|result physical path、traceback|
|`EvidenceView`|evidence_id、document/version refs、typed locator、fingerprint、label、limited excerpt、eligibility、etag|绝对路径、未授权正文|
|`ViewerDescriptor`|document/version metadata、locator、precision、short preview、authorized content URL|静态 file URL、storage locator|
|`EvidenceBindingView`|binding_id、evidence ref、subject version ref、purpose/state、actor/time|正文副本|
|`TraceLinkView`|link_id、source/target version refs、relation/state、created actor/time|无权节点 metadata|
|`TraceGraphView`|authorized nodes/edges、next_cursor、truncated|被过滤对象数量/标题/存在性|

### Audit 与 License

|DTO|核心字段|禁止字段|
|---|---|---|
|`AuditEventView`|event_id/time、safe actor、project?、action/outcome、object/version refs、safe summary、trace_id|Secret、credential、Session、正文、完整 Prompt/响应|
|`LicenseStatusView`|validation_code、entitlement summary、validity window、last_validated_at、active installation ref?|原始 MAC、签名材料、私钥、可信时间路径|
|`LicenseInstallationView`|installation_id、state、public key ref/version、imported actor/time、validation code|私钥、完整敏感 payload|

## 权限矩阵摘要

`R`=读，`W`=创建/修改，`D`=Review decision，`-`=默认拒绝。具体 assigned reviewer/资源状态限制仍必须满足。

|资源族|DeploymentAdmin|ProjectManager|ImplementationMember|CustomerManager|CustomerMember|
|---|---|---|---|---|---|
|Configuration/Secret/User/License|R/W|-|-|-|-|
|Project identity|仅创建/部署列表|R/W|R|R|R|
|Member/Department|-|R/W|R|R|受限 R|
|Workflow/Gate|-|R/W|R|R|R|
|Project Document|-|需策略 R/W|R/W|需策略 R/W|受限 R|
|GLOBAL Document|R/W|受权 R|受权 R|受权 R|受权 R|
|Evidence/Binding|-|R/W|R/W|受权 R/W|受限 R|
|Review|-|R/W/D|R/assigned D|R/assigned D|R/assigned D|
|Trace|-|R/W|R/W|R|受限 R|
|Project Audit|-|R|-|-|-|
|Deployment Audit|R|-|-|-|-|

DeploymentAdmin 只有显式成为某 Project 的成员后，才能按相应 Project Role 访问该项目业务资源。SystemActor 不出现在交互矩阵，只能按 Job 授权快照调用已登记 Application Port。

## 错误码目录

|前缀/错误码|HTTP|触发语义|
|---|---:|---|
|`PLATFORM_SENSITIVE_VALUE_FORBIDDEN`|422|敏感值试图进入普通配置|
|`PLATFORM_SECRET_PURPOSE_INVALID`|422|Secret purpose/consumer 不在白名单|
|`PLATFORM_SECRET_UNAVAILABLE`|503|主材料/解密不可用，失败关闭|
|`AUTH_INVALID_CREDENTIALS`|401|登录统一失败|
|`AUTH_SESSION_EXPIRED`|401|Session 过期/撤销/credential version 不符|
|`AUTH_CSRF_INVALID`|403|CSRF/Origin/Host 失败|
|`AUTH_USER_DISABLED`|409|管理命令与 User 当前状态冲突|
|`AUTH_USERNAME_CONFLICT`|409|canonical username 冲突|
|`PROJECT_USER_ALREADY_ASSIGNED`|409|User 已有另一未移除 membership|
|`PROJECT_DEPARTMENT_IN_USE`|409|部门仍被有效成员引用|
|`PROJECT_ARCHIVED`|409|归档项目的新写/Job 被拒绝|
|`PROJECT_ROLE_INVALID`|422|角色/部门/项目组合非法|
|`WORKFLOW_GATE_NOT_SATISFIED`|409|required checklist/evidence/review 缺失|
|`WORKFLOW_TRANSITION_INVALID`|409|跳级、from/current 不一致或终态迁移|
|`WORKFLOW_WAIVER_INCOMPLETE`|422|Waiver 缺理由/影响/依据|
|`REVIEW_SUBJECT_LOCKED`|409|IN_REVIEW 主题内容被修改|
|`REVIEW_REVIEWER_INELIGIBLE`|422|Reviewer 无资格/重复/不在 Scope|
|`REVIEW_COMMENT_REQUIRED`|422|RETURN 缺实质意见|
|`REVIEW_DECISION_EXISTS`|409|Reviewer 重复最终决定|
|`FILE_UPLOAD_EXPIRED`|409|UploadIntent 过期/已提交/已终止|
|`FILE_TOO_LARGE`|413|超过用途或部署限制|
|`FILE_TYPE_UNSUPPORTED`|415|类型/MIME/特征不允许|
|`FILE_INTEGRITY_MISMATCH`|409|Hash/Size/持久文件不一致|
|`FILE_CONTENT_UNAVAILABLE`|503|正式 metadata 存在但文件不可用|
|`EVIDENCE_LOCATOR_INVALID`|422|Locator union 或来源位置无效|
|`EVIDENCE_FINGERPRINT_MISMATCH`|409|固定版本定位内容漂移|
|`EVIDENCE_INELIGIBLE`|409|资格/模板/撤销规则拒绝正式使用|
|`EVIDENCE_SCOPE_MISMATCH`|404|跨项目/禁止方向，对外不泄露|
|`TRACE_RELATION_INVALID`|422|关系类型、方向或自环非法|
|`TRACE_CYCLE_DETECTED`|409|受控子图成环|
|`TRACE_GRAPH_LIMIT_EXCEEDED`|422|深度/节点/查询范围超上限|
|`AUDIT_EXPORT_SCOPE_INVALID`|422|导出范围/用途不允许|
|`LICENSE_NOT_INSTALLED`|403|无有效安装且不在恢复面|
|`LICENSE_SIGNATURE_INVALID`|403|签名/Schema 验证失败|
|`LICENSE_MACHINE_MISMATCH`|403|机器指纹不符|
|`LICENSE_EXPIRED`|403|已过有效期|
|`LICENSE_TIME_ROLLBACK`|403|可信时间回拨/完整性失败|

通用 `RESOURCE_NOT_FOUND`、`CONFLICT_VERSION`、`CONFLICT_IDEMPOTENCY`、`VALIDATION_FAILED` 和 `SYSTEM_UNAVAILABLE` 沿用 API-01。模块错误 message 不包含他项目 ID、路径、SQLSTATE、原始 MAC、签名 payload 或 Secret。

## 强制 Audit 动作

- 登录成功/失败、注销、换密、User 启停、Session 撤销。
- Project 创建/归档、Member/Role/Department 变化。
- Workflow checklist、Waiver 和 StageTransition 成功/拒绝。
- Configuration 版本/激活；Secret 创建/轮换/停用和访问失败。
- License 导入、验签、机器/时间拒绝、激活和重验证。
- 文件上传/提交/失败恢复、Version 创建、受限下载拒绝和完整性异常。
- Evidence 资格、Binding 变更；Review start/decision/withdraw；Trace create/revoke/supersede。
- Audit 导出请求、完成与失败。

状态改变与 Audit 必须在同一业务事务/Outbox 边界提交；Audit 不可用且属于强制点时操作失败关闭。

## Contract 测试矩阵

每个 Operation 至少覆盖：

1. Happy path 与 Envelope/trace_id。
2. Session 缺失、过期、撤销与 credential version 变化。
3. 状态改变请求的 CSRF/Origin/Host 失败。
4. License 无效；仅恢复面继续可用。
5. Role 拒绝、member suspended/removed、Project Archived。
6. ProjectId/资源归属/subject/evidence/trace 两端跨项目负例。
7. 缺少/过期 If-Match 与同 key 不同 payload 幂等冲突。
8. 未知字段、未知枚举、长度/格式、cursor/query 白名单。
9. 安全错误不泄露资源存在性、路径、SQL、Secret 或 traceback。
10. 强制 Audit 成功/拒绝/失败记录。

专项测试：

- Auth：用户名规范化冲突、停用立即失效、换密撤销其他 Session、多标签 CSRF 轮换。
- Project：单项目 membership、单角色/部门、部门引用阻断、Archived 只读。
- Workflow/Review：Gate 缺项、Waiver、并发 transition、1～N reviewer、任一退回、送审锁、升版重审。
- Document：上传崩溃矩阵、重复 Commit、Hash/MIME、路径越界、升版并发、文件缺失、Parse retry。
- Evidence/Trace：9 类 locator、模板非事实、CONTRADICTS 保留、GLOBAL→PROJECT 白名单、跨项目/自环/成环、逐节点授权。
- License：签名、机器、有效期、时间回拨、损坏状态、无效 License 恢复面和私钥/原 MAC 零泄露。

## 风险与关闭条件

|Risk ID|风险|当前控制|关闭条件|
|---|---|---|---|
|API2-R01|登录/Session/CSRF 具体 TTL 与多标签行为尚未实测|名称/轮换/内存保存/失效语义已固定|基础工程安全测试|
|API2-R02|DeploymentAdmin 与 Project role 组合可能被实现成超级用户|矩阵明确分离，项目访问要求 membership|Permission 集成与枚举负测|
|API2-R03|项目创建时首个 Manager/Department 的原子性|单命令 + Audit + idempotency|正式 ORM/Migration/API transaction test|
|API2-R04|Workflow 正式 stage/checklist 配置尚未冻结|API 只引用 key/policy/version，不硬编码清单|业务配置设计 + Gate 测试|
|API2-R05|Review generic ref 与 Owner version 状态可能漂移|固定 version ref、Owner Port、送审锁、Review event|模块 API 集成测试|
|API2-R06|三步上传的超时/重传/崩溃留下孤儿文件|UploadIntent、STAGED 状态、幂等 Commit、恢复矩阵|文件故障注入与恢复测试|
|API2-R07|GLOBAL 文档/Evidence 被项目用户过度读取|引用/类别策略 + 每次授权，ID 不授予访问|GLOBAL→PROJECT 权限测试|
|API2-R08|Viewer 定位精度依源格式变化|返回 precision，固定 version/locator，不伪造高亮|PDF/Office/扫描件 Viewer 集成|
|API2-R09|Trace 图裁剪泄露无权节点数量或关系|逐节点授权、无占位、truncated 不说明原因|图权限属性测试|
|API2-R10|Audit 导出包含敏感字段或项目越权|白名单投影、范围/用途、异步 Job、再次审计|Export snapshot/permission test|
|API2-R11|License 恢复面被扩大为业务旁路|端点白名单；无 L 仍要求 Session/Role/CSRF/Audit|无效 License 全路由测试|
|API2-R12|错误码与后续模块重名/语义漂移|Operation/Error registry 在 API-05 统一 lint|OpenAPI/错误码唯一性检查|

## API-02 验收

- 10 个 Owner、22 个 Root 均有明确 API 或 INTERNAL 边界：PASS。
- Platform Configuration 与 Secret write-only/metadata 契约明确：PASS。
- Login/Session/User 生命周期、Cookie/CSRF 和凭据零泄露明确：PASS。
- Project/Member/Department 的单项目、单角色、归档与权限契约明确：PASS。
- Workflow checklist、Waiver、Transition、Gate 与乐观并发契约明确：PASS。
- Review identity/round/version/reviewer/decision/lock/升版重审契约明确：PASS。
- Document 三步上传、不可变版本、受权流式下载、Parse retry 与 GLOBAL/PROJECT 边界明确：PASS。
- Evidence 9 类 Locator、资格、Viewer、Binding 与模板非事实规则明确：PASS。
- Trace 双向图、Scope、关系白名单、无环与逐节点授权明确：PASS。
- Audit 只读/导出与 License 最小恢复面、可信时间内部边界明确：PASS。
- DTO 明确禁止 Secret、Session、路径、正文和内部运行字段：PASS。
- 角色矩阵、错误码、强制 Audit 与 Contract 测试矩阵明确：PASS。
- 12 项风险均有当前控制和关闭位置：PASS。
- 未创建 FastAPI、Pydantic、Service、ORM、Migration 或业务代码：PASS。

## 下一步

API-03：在 API-01 公共协议上冻结 AI、RAG、Job、Plugin 与 Output 的异步提交、外发授权、状态、取消、结果、SSE、错误和权限契约。
