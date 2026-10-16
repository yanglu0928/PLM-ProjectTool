# API-01：资源目录与通用协议 V1 候选

## 状态

`CANDIDATE / API-01_COMPLETE / API-02_NEXT / NOT_GATE_2_FROZEN / NO_FASTAPI_IMPLEMENTATION`

本文件冻结 API Contract V1 的公共外壳：资源分类、URL 语法、JSON Envelope、Session/CSRF、Trace、分页、筛选、幂等、乐观并发、上传下载、异步任务、错误与角色边界。模块级端点和 DTO 在 API-02～API-04 细化，API-05 汇总为单一候选。

## 输入与优先级

1. `ARCH-CANDIDATE-V1` 与 Application Port/Security 边界。
2. `DATA-MODEL-CANDIDATE-V1` 的 22 Owner、65 Root、Scope、版本和生命周期。
3. `DB-SCHEMA-CANDIDATE-V1` 的 ProjectId、并发、Query、文件和 Migration 边界。
4. 用户最新明确变更、正式 ADR 和批准例外。

API Contract 不暴露数据库实现。出现冲突时遵循：用户最新明确变更 > Gate 2 后正式 Contract > 本候选 > Architecture/Data/Schema 明细中的 API 假设。

## 协议与媒体类型

|项目|V1 规则|
|---|---|
|Base path|`/api/v1`|
|业务协议|HTTPS 上 REST/JSON；开发环境可受控使用 HTTP|
|JSON|`application/json; charset=utf-8`|
|上传|`multipart/form-data`，文件流式接收|
|下载|受权流式响应；`Content-Disposition` 文件名经过安全规范化|
|事件|SSE `text/event-stream; charset=utf-8`|
|编码|UTF-8|
|时间|RFC 3339 UTC，例如 `2026-09-23T08:30:00.123456Z`|
|日期|ISO `YYYY-MM-DD`，不隐含时区|
|ID|canonical lowercase UUID 字符串|
|枚举|UPPER_SNAKE_CASE；未知值必须失败而非静默降级|
|金额/高精度数|十进制字符串；禁止二进制浮点金额|

业务端点全部位于 `/api/v1`。最小健康面使用 `/health/live` 和 `/health/ready`，不得返回版本、路径、数据库、用户、项目、License 细节或 Secret 状态。

## URL 与资源命名

- 集合和资源使用英文 `lower-kebab-case` 复数名词；路径参数使用 `{resource_id}` 的语义名。
- PROJECT 资源统一嵌套在 `/api/v1/projects/{project_id}/...`，不提供省略 ProjectId 的平行路径。
- 部署管理资源位于 `/api/v1/admin/...`；GLOBAL 标准能力读面位于 `/api/v1/global/...`。
- 动作只用于无法自然表示为 CRUD 的状态命令，格式为 `POST .../{id}:action`，例如 `:submit-review`、`:approve`、`:cancel`。
- 创建使用 `POST collection`；读取使用 `GET`；可变元数据更新使用 `PATCH`；V1 不提供通用物理 `DELETE`。
- Archive、withdraw、revoke、disable、cleanup-preview/execute 使用专用命令并写 Audit。
- URL 不包含数据库表名、`owner_module`、内部状态投影、文件路径、Provider 名称分支或 SQL 查询表达式。

## 成功与错误 Envelope

### 成功

```json
{
  "data": {},
  "trace_id": "018f0000-0000-7000-8000-000000000001"
}
```

- 所有 JSON 成功响应都有 `data` 与 `trace_id`；V1 不使用空体 `204`。
- 创建返回 `201`；同步成功返回 `200`；已受理长任务返回 `202`。
- `X-Trace-Id` 响应头与 body `trace_id` 必须一致。

### 错误

```json
{
  "error": {
    "code": "CONFLICT_VERSION",
    "message": "资源已被更新，请刷新后重试。",
    "details": []
  },
  "trace_id": "018f0000-0000-7000-8000-000000000001"
}
```

- `code` 是稳定机器码；`message` 是安全本地化信息；`details` 仅包含字段级安全提示，可省略或为空。
- 不返回 Python traceback、SQL/SQLSTATE、表/列名、绝对路径、Cookie、Token、Secret、Provider 原始响应或其他项目标识。
- FastAPI/Pydantic 的默认验证错误必须转换为本 Envelope，不能泄露内部模型名。

## HTTP 状态与通用错误

|HTTP|通用错误码|语义|
|---:|---|---|
|400|`REQUEST_MALFORMED`|JSON、Header、Cursor 或参数无法解析|
|401|`AUTH_REQUIRED`、`AUTH_SESSION_EXPIRED`|未认证或 Session 已失效|
|403|`AUTH_CSRF_INVALID`、`LICENSE_OPERATION_DENIED`|请求已识别但安全前置失败|
|404|`RESOURCE_NOT_FOUND`|不存在、无权或跨项目对普通用户统一语义|
|409|`CONFLICT_VERSION`、`CONFLICT_STATE`、`CONFLICT_DUPLICATE`、`CONFLICT_IDEMPOTENCY`|并发、状态、唯一或幂等载荷冲突|
|413|`FILE_TOO_LARGE`|上传超过用途/部署限制|
|415|`FILE_TYPE_UNSUPPORTED`|扩展名、MIME 或文件特征不允许|
|422|`VALIDATION_FAILED`|语法有效但字段/业务输入无效|
|428|`CONFLICT_VERSION_REQUIRED`|修改可变资源时缺少 `If-Match`|
|429|`AUTH_RATE_LIMITED`|登录/恢复等高风险入口限速|
|500|`SYSTEM_INTERNAL`|未分类内部失败，外部消息固定安全|
|503|`SYSTEM_UNAVAILABLE`|数据库、存储或关键依赖暂不可用|

模块错误继续使用 `AUTH_`、`PROJECT_`、`FILE_`、`AI_`、`RAG_`、`PLUGIN_`、`LICENSE_`、`REVIEW_`、`SYSTEM_` 等前缀；API-02～API-04 登记完整码表。客户端不得根据 message 文本判断错误类型。

## Trace 与请求上下文

- 客户端可发送 `X-Trace-Id`，仅接受 canonical UUID；缺失或无效时服务器生成新的 uuidv7。
- 同一 trace_id 贯穿 API、Application、Job、AI、Plugin、Integration Log 和 Audit，但不能充当权限或幂等凭据。
- 服务器从 Session 解析 `actor_id`，从受控路径解析 `project_id`，从 Header 解析幂等/并发信息；不得信任 body 中重复的 actor/project。
- Worker 继承原 `actor_id`、project_id、trace_id 和授权目的，并使用受控 `SystemActor`；SystemActor 不是跨项目通配符。

## Session、Cookie 与 CSRF

|项目|V1 候选|
|---|---|
|Session Cookie|`plm_session`；HttpOnly、Path=/、生产 Secure、SameSite=Lax|
|CSRF Header|`X-CSRF-Token`|
|CSRF Token|登录/Session 刷新响应通过受权 DTO 返回，只在前端内存保存；服务端 Session 保存摘要|
|Origin/Host|生产环境白名单校验|
|Session renewal|轮换 Session ID 与 CSRF Token；密码变更、停用、注销和管理员撤销使旧 Session 失效|

- Cookie 认证的 POST/PATCH/PUT/DELETE 和所有 `:action` 必须校验 CSRF；GET/HEAD 不得改变业务状态。
- 不把 Session、CSRF 或长期 Token 写入 localStorage/sessionStorage、URL、日志或 SSE payload。
- 未登录只开放最小健康面和登录。License 无效时，已认证 DeploymentAdmin 只可访问最小 License 查询/导入/诊断面。

## License、授权与检查顺序

受许可业务操作固定执行：

```text
Trace/Security Context
→ License Guard
→ Session
→ CSRF（状态改变）
→ Deployment/Project Role
→ ProjectId + Resource Ownership
→ Resource State + Review Lock + If-Match
→ Application Port
→ Audit
```

- License 有效不代表用户已授权；DeploymentAdmin 不自动获得项目业务数据访问权。
- PROJECT 路径中的 `project_id` 必须与资源归属、Session 成员关系和 DTO 引用逐项一致。
- GLOBAL→PROJECT 引用需要白名单关系和逐节点授权；禁止通过 Trace/Evidence/Search 泄露无权元数据。
- 对普通用户，不存在、无权限和跨项目均返回 `RESOURCE_NOT_FOUND`；内部原因只进入 Audit/安全日志。

## Role × Scope 基线

|角色|部署/GLOBAL|所属 PROJECT|禁止事项|
|---|---|---|---|
|DeploymentAdmin|配置、用户、License、Provider/Model、全局能力、签名 Plugin 安装/启停|只有显式成为该项目成员后才按项目角色访问业务数据|不得绕过 Session、License、Review Lock、Audit 或直接读取客户正文|
|ProjectManager|无部署管理权|项目设置、成员/部门、Workflow、Review 发起、实施业务全链管理与受权输出|不得管理 Secret/License/全局 Provider，不得跨项目|
|ImplementationMember|无部署管理权|项目资料、分析、调研、需求、原型、方案、计划的创建/修订与受权 AI/输出|不得管理成员角色、替客户确认、绕过 Review|
|CustomerManager|无部署管理权|项目读取、调研组织/结论、Review 决策和客户确认范围|不得修改系统配置、替实施方生成正式版本、跨项目|
|CustomerMember|无部署管理权|项目最小读取、被分配调研答复和 Review 决策|不得浏览未授权工作区、管理项目、批量导出或跨项目|
|SystemActor|无交互登录|仅在 Job 授权快照范围内调用 Application Port|不得作为全局管理员、创建新授权或绕过原 actor/project|

API-02～API-04 必须把本表展开为 `Role × Operation × Project × Resource State` 矩阵；默认拒绝，未登记即不可调用。

## 乐观并发与 ETag

- 可变资源的 GET/创建/更新响应返回强 ETag：`"v<lock_version>"`。
- 修改、状态命令和 Archive 必须发送 `If-Match`；服务器映射为 Application Command 的 `expected_version`。
- 缺失 `If-Match` 返回 `428 PRECONDITION_REQUIRED` + `CONFLICT_VERSION_REQUIRED`；不匹配返回 `409 CONFLICT_VERSION`。
- 不可变 Version 内容不提供 PATCH；修订通过创建新 Version。Review 决策、Audit、Trace 历史使用追加命令。
- ETag 只表示该资源的并发版本，不作为缓存权限或跨资源事务版本。

## 幂等

- 可重试的 POST/命令必须发送 `Idempotency-Key`，格式为 16～128 个可打印 ASCII 字符；推荐 UUID。
- 幂等范围至少包含 actor、project、operation 和 key；服务器保存规范化 payload hash 与结果引用。
- 同 key + 同 payload 返回原结果和原语义状态；同 key + 不同 payload 返回 `409 CONFLICT_IDEMPOTENCY`。
- 文件上传的幂等 hash 不得只依赖文件名；长任务返回同一 JobRef，不能重复提交外部调用。
- Idempotency Key 不得包含客户正文、Secret、文件路径或用户密码。

## 列表、分页、排序与筛选

列表成功数据固定为：

```json
{
  "data": {
    "items": [],
    "next_cursor": null,
    "has_more": false
  },
  "trace_id": "018f0000-0000-7000-8000-000000000001"
}
```

- `page_size` 默认 50、最小 1、最大 200；高成本图/搜索端点可设置更低上限并在模块 Contract 固定。
- `cursor` 是服务器签名或完整性保护的不透明 token，包含资源族、授权 Scope、稳定排序值和查询指纹；客户端不得构造或解析。
- 排序字段由每个端点白名单定义，默认 `updated_at DESC, resource_id DESC` 或追加记录的 `created_at DESC, record_id DESC`。
- 筛选只接受显式命名参数/DTO；禁止客户端提交 SQL、列名、JSONPath、任意表达式或动态 `order_by`。
- Cursor 与筛选、Scope、用户授权不匹配时返回 `REQUEST_MALFORMED`，不能退化为新查询或放宽 ProjectId。

## Null、Patch 与字段演进

- JSON 字段缺失表示“不修改/未提供”；显式 `null` 只在字段允许清空时有效；空字符串不自动等于 null。
- PATCH 使用受控 partial DTO，不采用任意 JSON Patch/Merge Patch；只允许模块 Contract 列出的可变字段。
- 输出 DTO 可新增可选字段作为向后兼容演进；删除/改名、改变类型/语义或新增必填请求字段属于 Breaking Change。
- 冻结后的 `/api/v1` Breaking Change 必须新端点、`/api/v2` 或 API Change Request；不得静默改变枚举、默认值或错误码含义。
- 客户端必须容忍响应新增字段，但服务器对未知请求字段默认拒绝，避免拼写错误被静默忽略。

## 文件上传、下载与 Evidence 定位

- 上传先创建或使用一次性上传意图，再流式校验大小、扩展名、MIME、文件特征与 SHA-256；通过后才创建 STAGED FileObject/DocumentVersion。
- `original_filename` 仅作为规范化显示元数据，不参与服务器路径拼接。
- 下载/预览端点每次重新执行 Session、Project/Global、资源状态与用途检查，不返回 `storage_locator`。
- 下载失败不泄露目标是否存在；Range/缓存头按文件模块 Contract 冻结，不能绕过授权。
- Evidence DTO 返回 `evidence_id`、document/version 标识和 page/section/offset 等安全 Locator；按钮定位文档通过受权 Viewer route，不暴露物理路径。
- 上传、解析、OCR、转换和 Plugin 失败产生安全错误码；临时/半完成内容不能成为正式业务引用。

## 长任务、Job 与 SSE

长任务受理响应：

```json
{
  "data": {
    "job_id": "018f0000-0000-7000-8000-000000000010",
    "state": "PENDING",
    "status_url": "/api/v1/projects/018f.../jobs/018f..."
  },
  "trace_id": "018f0000-0000-7000-8000-000000000001"
}
```

- API 在短事务内提交业务状态、Job/Outbox 和 Audit 后返回 `202`；不等待 OCR、Embedding、LLM、文件转换或 Plugin。
- 客户端通过受权 Job 资源查询，或订阅 `/api/v1/projects/{project_id}/events` SSE。
- SSE 事件包含 `event_id`、`event_type`、`occurred_at`、`project_id`、`resource_ref`、`state`、`progress`、`trace_id` 的最小子集；不包含正文、Prompt/响应、Secret、Cookie、路径或 Plugin stdio。
- SSE 使用 Outbox/event_id 支持 `Last-Event-ID` 受限恢复；恢复窗口之外要求客户端重新获取资源状态，不承诺永久事件流。
- Job 取消是协作式专用命令；已发布正式版本、外部副作用和 Audit 不伪装为回滚。

## 65 Root → API 资源目录

暴露级别：`DIRECT` 为顶级或项目集合资源，`NESTED` 为父资源下受控子资源，`READ_ONLY` 仅允许受权查询/下载，`INTERNAL` 不提供通用 CRUD，只能由专用命令或 Application Port 驱动。

|Owner / API family|Root IDs|暴露|V1 资源边界|
|---|---|---|---|
|platform `/api/v1/admin/configurations`、`/api/v1/admin/secrets`|PLT-01、PLT-02|DIRECT / INTERNAL|配置通过版本化命令；Secret 值 write-only，查询永不回显|
|auth `/api/v1/auth`、`/api/v1/admin/users`|AUT-01、AUT-02|DIRECT / INTERNAL|User 管理；Session 只经 login/logout/current/renew/revoke，不提供通用 Session CRUD|
|project `/api/v1/projects`|PRJ-01、PRJ-02、PRJ-03|DIRECT / NESTED|Project、members、departments；ProjectId 路径与资源归属双检|
|workflow `/api/v1/projects/{project_id}/workflow`|WFL-01、WFL-02|DIRECT / READ_ONLY|Workflow 状态与 transition history；迁移只经专用命令|
|review `/api/v1/projects/{project_id}/reviews`|RVW-01、RVW-02|DIRECT / NESTED|Review identity、rounds、assignments/decisions；历史追加|
|trace `/api/v1/projects/{project_id}/trace-links`|TRC-01|DIRECT|link/supersede/upstream/downstream，深度和节点上限固定|
|audit `/api/v1/projects/{project_id}/audit-events`|AUD-01|READ_ONLY|受权时间线；普通用户无修改/删除|
|license `/api/v1/admin/license`|LIC-01、LIC-02、LIC-03|DIRECT / READ_ONLY / INTERNAL|导入、状态、最小诊断；可信时间只由专用端口更新|
|document `/api/v1/projects/{project_id}/documents`|DOC-01、DOC-02、DOC-03、DOC-04|DIRECT / NESTED / INTERNAL / READ_ONLY|Document/versions/upload/download/parse status；FileObject 无通用 CRUD|
|evidence `/api/v1/projects/{project_id}/evidence`|EVD-01、EVD-02|DIRECT / NESTED|Evidence resolve/viewer locator 与 subject binding；不返回绝对路径|
|jobs `/api/v1/projects/{project_id}/jobs`|JOB-01、JOB-02|READ_ONLY / INTERNAL|Job 查询/协作取消；Lease/Outbox/消费不暴露|
|ai `/api/v1/admin/ai`、`/api/v1/projects/{project_id}/ai-tasks`|AI-01、AI-02、AI-03、AI-04|DIRECT / DIRECT / DIRECT / NESTED|Provider/Model/Prompt 管理与 Task 建议；API Key 仅 SecretRef，输出标记建议态|
|rag `/api/v1/admin/rag`、`/api/v1/projects/{project_id}/retrievals`|RAG-01、RAG-02、RAG-03、RAG-04|INTERNAL / DIRECT / INTERNAL / NESTED|Chunk/Embedding 无通用 CRUD；Index 创建/激活/重建与 RetrievalRun 查询|
|capability `/api/v1/global/capability-baselines`|CAP-01、CAP-02|DIRECT / NESTED|GLOBAL baseline identity/version/items；项目只能受权引用|
|handover `/api/v1/projects/{project_id}/handover-analyses`|HND-01、HND-02、HND-03|DIRECT / NESTED / DIRECT|分析 identity/versions 与 action items；AI 建议需确认后正式化|
|survey `/api/v1/projects/{project_id}/surveys`|SRV-01、SRV-02、SRV-03、SRV-04、SRV-05|DIRECT / NESTED / DIRECT / NESTED / DIRECT|模板版本、round、assignment/answer、conclusion；实际调研记录优先|
|requirement `/api/v1/projects/{project_id}/requirements`|REQ-01、REQ-02、REQ-03、REQ-04|DIRECT / DIRECT / NESTED / DIRECT|Package、identity/version、relations；正式版本必须 Review|
|prototype `/api/v1/projects/{project_id}/prototypes`|PRT-01、PRT-02、PRT-03、PRT-04、PRT-05|DIRECT / DIRECT / NESTED / DIRECT / DIRECT|Package、identity/version、template、requirement link；支持 NOT_REQUIRED 决策|
|solution `/api/v1/projects/{project_id}/solutions`|SOL-01、SOL-02、SOL-03、SOL-04、SOL-05、SOL-06|DIRECT / DIRECT / NESTED / NESTED / NESTED / DIRECT|Reference、outline/section versions、structured specs；正文受控引用|
|plan `/api/v1/projects/{project_id}/plans`|PLN-01、PLN-02、PLN-03|DIRECT / NESTED / DIRECT|Plan/version/WBS、ReferencePlan；WBS 最多六级且仅 FS|
|output `/api/v1/projects/{project_id}/outputs`|OUT-01、OUT-02|DIRECT / READ_ONLY|受权上下文提交、Job 进度、Artifact 下载/验证；历史不覆盖|
|plugin `/api/v1/admin/plugins`、`/api/v1/projects/{project_id}/plugin-executions`|PLG-01、PLG-02、PLG-03|DIRECT / DIRECT / NESTED|只安装开发者签名包；调用只接收 OutputContextRef，不暴露进程/stdio|

目录覆盖 22 个 Owner 与 65 个 Root。暴露级别不等于角色授权；实际操作仍由 API-02～API-04 的权限矩阵逐项允许。

## API-02～API-05 输入清单

1. 为每个 `DIRECT/NESTED/READ_ONLY` 资源冻结 collection/item/action 路径、请求/响应 DTO 和状态码。
2. 为每个操作登记 Owner Application Port、Role、Scope、License、CSRF、If-Match、Idempotency 和 Audit 要求。
3. 为所有 Version/Review/Trace/Evidence/Output DTO 固定不可变引用，不使用动态 current pointer。
4. 为长任务固定 JobRef、取消语义、进度、结果引用和 SSE event_type。
5. 为上传/下载/Viewer 固定大小、媒体类型、Range/缓存和 Content-Disposition 安全策略。
6. 为 AI/RAG 固定当轮外发授权、最小 Context、模型/Prompt/Index version 和建议态标记。
7. 汇总完整错误码、Role × API × Project × State 与 OpenAPI schema，并验证无内部字段泄露。

## 风险与关闭条件

|Risk ID|风险|当前控制|关闭条件|
|---|---|---|---|
|API1-R01|资源目录过度暴露内部 Root|四级暴露分类；Job/Outbox/File/Embedding 等无通用 CRUD|API-02～04 端点审查 0 个越界|
|API1-R02|DeploymentAdmin 被误当作项目数据超级用户|全局角色与项目成员分离|Permission 矩阵与跨项目负测|
|API1-R03|404 统一语义掩盖合法诊断|外部统一、内部 trace/Audit 区分；仅受权管理员诊断|API 错误与 Audit 集成测试|
|API1-R04|CSRF Token 生命周期与多标签页刷新冲突|Session 绑定、轮换、内存保存；不使用 localStorage|Auth 实现 PoC/多标签测试|
|API1-R05|Cursor 被篡改或跨 Scope 重放|不透明、完整性保护、绑定查询指纹/Scope|分页属性与越权测试|
|API1-R06|幂等结果与 payload 演进产生歧义|规范化 payload hash、operation/version 范围|重放/不同 payload/过期策略测试|
|API1-R07|ETag 与业务 Version ID 混淆|ETag 只映射 mutable lock_version；正式引用用 version_id|API-02～04 DTO review|
|API1-R08|SSE 恢复窗口被误解为永久事件存储|Last-Event-ID 受限恢复，超窗重新 GET|Job/SSE 断线集成测试|
|API1-R09|大文件上传在请求中占用内存/事务|流式临时区、Hash/类型校验、短事务提交|文件集成与故障恢复测试|
|API1-R10|通用错误过度归一导致客户端不可操作|稳定模块码 + 安全 details；message 不作机器判断|API-05 完整错误码审查|
|API1-R11|未知枚举/字段导致前后端静默不一致|请求未知字段拒绝、未知枚举失败、响应允许新增可选字段|OpenAPI contract tests|
|API1-R12|65 Root 到路径映射遗漏或重复|机器可读 Root 清单与本目录一致性检查|API-05 自动 Contract lint|

## API-01 验收

- API-01～API-05 执行顺序、输入、输出和 Gate 边界明确：PASS。
- `/api/v1`、REST/JSON、multipart、SSE、UTF-8、时间/ID/枚举规则明确：PASS。
- URL、CRUD/专用命令、PROJECT/admin/global 路径边界明确：PASS。
- 成功/错误 Envelope、HTTP 状态和安全错误规则明确：PASS。
- Trace、Session Cookie、CSRF、License 与授权检查顺序明确：PASS。
- 六类主体的 Role × Scope 基线和 DeploymentAdmin 非项目超级用户边界明确：PASS。
- ETag/If-Match、Idempotency-Key、Null/Patch 和 Breaking Change 规则明确：PASS。
- keyset cursor、page size、排序和显式筛选规则明确：PASS。
- 文件上传/下载/Evidence Viewer 不暴露物理路径：PASS。
- 长任务 `202 + JobRef`、协作取消和最小 SSE 事件规则明确：PASS。
- 22 Owner、65 Root 全部进入资源目录且暴露级别明确：PASS。
- 12 项风险均有当前控制和关闭位置：PASS。
- 未创建 FastAPI、DTO、ORM、Migration 或正式业务代码：PASS。

## 下一步

API-02：在本公共协议上冻结 Platform/Auth/Project/Workflow/Document/Evidence/Review/Trace/Audit/License 的具体资源、命令、DTO、权限和错误码。
