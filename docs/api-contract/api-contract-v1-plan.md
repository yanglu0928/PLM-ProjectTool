# API Contract V1 执行计划

## 状态

`IN_PROGRESS / API-01_PASS / API-02_NEXT / NOT_GATE_2_FROZEN / NO_FASTAPI_IMPLEMENTATION`

本计划把 `ARCH-CANDIDATE-V1`、`DATA-MODEL-CANDIDATE-V1` 和 `DB-SCHEMA-CANDIDATE-V1` 转换为稳定的 `/api/v1` REST/JSON + SSE 契约候选。API-01～API-05 只定义资源、路径、DTO、权限、状态命令、错误、分页、幂等和事件；Gate 2 前不创建正式 FastAPI 路由或业务实现。

## 前置条件

- Phase 0 Gate 1：`APPROVED`。
- Architecture：`ARCH-CANDIDATE-V1 / AF-01～AF-05 PASS`。
- Data Model：`DATA-MODEL-CANDIDATE-V1 / DM-01～DM-06 PASS`。
- Database Schema：`DB-SCHEMA-CANDIDATE-V1 / SC-01～SC-05 PASS`。
- 正式业务编码继续由 Gate 2 阻塞。

## API-01～API-05

|WBS|目标|交付物|完成判定|
|---|---|---|---|
|API-01|资源与通用协议基线|65 Root 到 API 资源/内部对象目录；URL、Envelope、认证、CSRF、Trace、分页、并发、幂等、上传、错误和权限规则|PASS；见 `api-01-resource-common-protocol-v1-candidate.md`|
|API-02|平台、安全、文档与治理 Contract|Auth、Project、Workflow、Document、Evidence、Review、Trace、Audit、License、Configuration/Secret 端点与 DTO|资源/命令/权限/错误完整，无 Secret/路径泄露|
|API-03|AI、RAG、Job、Plugin 与 Output Contract|AI Task、Retrieval/Index、Job、Plugin、Output 的异步提交、状态、取消、外发授权和 SSE|统一 AIService/Job/Plugin 边界，无厂商直连|
|API-04|实施业务主链 Contract|Capability、Handover、Survey、Requirement、Prototype、Solution、Plan 资源、版本、Review 和 Trace 端点|实际调研优先、AI 建议态、版本/正式化链完整|
|API-05|汇总 API Contract Candidate|OpenAPI 资源清单、DTO/枚举、Role × API × Project、错误码、SSE、兼容性和测试矩阵|形成 `API-CONTRACT-CANDIDATE-V1`，提交 Gate 2|

## 强制协议边界

- 对外版本前缀固定为 `/api/v1`；存活/就绪检查位于最小非业务健康面。
- Browser 只使用 REST/JSON、multipart 上传和 SSE；不得直连数据库、文件目录、AI Provider 或 Plugin 子进程。
- Session 使用 HttpOnly Cookie；状态改变请求必须通过 CSRF、License、Role、Project/Resource、状态/Review Lock 和 expected version 检查。
- 所有响应包含 `trace_id`；错误不返回 traceback、SQL、表名、绝对路径、Secret 或 Provider 原始响应。
- PROJECT 资源的路径必须包含 `project_id`，并由服务端与资源归属交叉验证。
- 版本化正式引用必须使用固定 `version_id`；不得把 latest/current 动态指针当历史引用。
- 可重试写操作必须使用 Idempotency Key；可变资源使用 ETag/If-Match 映射 `expected_version`。
- 长任务在短事务内返回 `202 + JobRef`；外部调用、OCR、Embedding、生成和 Plugin 不在 HTTP 请求事务内执行。
- API DTO 不暴露数据库表名、Owner prefix、内部 FK、Storage Locator、Lease/fencing、Outbox 或 SecretRef 实现细节。

## 共同验证

1. 65 个 Root 必须在资源目录中恰好出现一次，并标记 `DIRECT`、`NESTED`、`READ_ONLY` 或 `INTERNAL` 暴露级别。
2. 22 个 Owner 均有明确 API family、授权 Scope 和 Application Port。
3. 通用成功/错误 Envelope、HTTP 状态、Trace、时间、UUID、枚举和 Null 语义唯一。
4. 登录/Session/CSRF、License 恢复面和 Project 隔离遵循 AF-03 固定检查顺序。
5. 列表只使用受控 keyset cursor；API 不接收数据库列名、SQL order by 或任意 Filter 表达式。
6. 文件上传、下载和 Evidence 定位不返回服务器绝对路径；下载通过受权流式响应。
7. AI/RAG 外发授权按轮次和最小载荷保存快照；未获得当轮授权时失败关闭。
8. Role × API × Project、跨项目枚举、Review Lock、expired License、CSRF、幂等冲突和乐观锁冲突进入测试矩阵。

## 当前不做

- 不生成 FastAPI Router、Pydantic DTO、Service、Repository、ORM 或生产 Migration。
- 不连接外部 AI、GitHub 之外的外部服务或客户资料。
- 不冻结前端页面、UI 文案或具体组件。
- 不引入 GraphQL、gRPC、WebSocket、消息队列、Redis、SSO 或第三方 API Gateway。

## 下一输出

API-02：细化 Platform/Auth/Project/Workflow/Document/Evidence/Review/Trace/Audit/License 的 `/api/v1` 资源、命令、DTO、权限和错误契约。
