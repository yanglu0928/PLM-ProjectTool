# HND-02-A05-A01：Handover Action 七写 HTTP/组合前置核查

日期：2026-10-05。结论：`HND_02_A05_A01_ACTION_WRITE_HTTP_PRECHECK_PASS`。下一项：`HND-02-A05-A02` Action CREATE/PATCH 严格 HTTP 边界。

## 核查结论

冻结 API-04 已定义 CREATE、PATCH、START、SUBMIT、VERIFY、CLOSE、CANCEL 七个 `/api/v1/projects/{project_id}/handover-action-items` 写 Operation。当前七个内部业务 Owner、授权策略、SQLAlchemy Repository、Audit、License、强版本及幂等能力均已存在；公开边界只有 LIST/GET，Windows 生产组合也仅装配读取，七个写路径仍为 404。

本阶段不建立第二套业务规则。HTTP 只负责严格白名单 DTO、Origin/Session/CSRF、canonical UUID、强 `If-Match`、`Idempotency-Key` 和安全错误投影，角色、项目隔离、当前受理人、Document/Evidence/Trace 资格、Audit、收据与事务继续由既有 Owner 决定。

## 传输契约

|Operation|并发/重放|最小正文|成功结果|
|---|---|---|---|
|CREATE|`Idempotency-Key`|固定 Analysis Item 或人工来源、类型、标题、字段提示、Owner、期限、优先级、原因|201、Location、ETag，状态 OPEN|
|PATCH|强 `If-Match`，不使用幂等键|标题/字段提示/Owner/期限/优先级的非空部分更新|200、ETag，状态不越迁|
|START|强 `If-Match` + `Idempotency-Key`|`reason`|200、ETag，IN_PROGRESS|
|SUBMIT|强 `If-Match` + `Idempotency-Key`|响应 DocumentVersion、SUBMISSION Evidence、`reason`|200、ETag，SUBMITTED|
|VERIFY|强 `If-Match` + `Idempotency-Key`|VERIFICATION Evidence、`reason`|200、ETag，VERIFIED|
|CLOSE|强 `If-Match` + `Idempotency-Key`|Resolution Trace、`reason`|200、ETag，CLOSED|
|CANCEL|强 `If-Match` + `Idempotency-Key`|`reason`|200、ETag，CANCELLED|

所有正文拒绝未知字段、重复头、query、非 canonical UUID 和不受支持的 JSON 形状。`SUBMITTED` 回执只表示已提交待验证，`VERIFIED` 只表示已验证待关闭，任何 HTTP 或 UI 投影均不得把两者标成完成。

## 实施分解与边界

- A02：CREATE/PATCH 严格 HTTP，解决登记与元数据更新一个问题域。
- A03：START/SUBMIT/VERIFY/CLOSE/CANCEL 生命周期 HTTP，保持状态语义连续。
- A04：Windows 写模式生产组合与 Win11/PostgreSQL 18 真实七写闭环。
- A05：前端写客户端和操作工作台。
- A06：真实浏览器闭环与可用性验证。

这是对冻结 Operation 的传输细化，不改变 URL、状态机、权限或数据模型，无需 API Change Request。若后续发现冻结路径、Schema 或状态语义无法兼容，按持续授权先登记 Change Request、迁移/回滚与验证计划，再实施，不静默改写基线。

## 兼容、回滚与未关闭项

本任务仅记录设计，无程序、Schema、Migration、依赖、Secret、网络、外发或客户数据变化，可停止后续实施且不影响历史。正式服务账户信任材料、Windows Server 2025、真实浏览器、路由拆包性能、Gate 3、UAT 与发行仍开放；Debian 13 实机按用户最新要求跳过，不宣称已验证。
