# CR-EVD-004：Evidence 资格操作结果精确回查

日期：2026-10-01；来源：`EVD-01-A04-P03-A08-P06` 前置核查；状态：`OPTIONAL_HTTP_PG_VERIFIED / PLATFORM_AND_UI_PENDING`。原 Gate 2 API Contract 冻结提交 `64cdf09` 不修改。

实施检查点：P07 收据只读查询、P08 当前身份边界、P09 scoped Evidence→原操作者收据内部服务已在 Windows11/隔离 PostgreSQL18 验证；公开路由、平台组合和前端仍未实现，CR 不关闭。证据见 [P09](../progress/evd-01-a04-p03-a08-p09-internal-lookup.md)。

P10 已新增默认关闭的可选项目/全局 HTTP 路由，并在隔离 PostgreSQL18 完成同源 POST→收据回查，见 [P10](../progress/evd-01-a04-p03-a08-p10-lookup-http.md)；前句为 P09 当时检查点保留。Windows 显式组合/前端/真实浏览器仍未验，CR 不关闭。

P11 已仅在 Windows `--platform-write` 显式组合挂载该路由；隔离 PG18 资格写入→回查和拒绝矩阵通过，见 [P11](../progress/evd-01-a04-p03-a08-p11-windows-lookup-composition.md)。上句为 P10 当时检查点保留。前端、真实浏览器及正式目标信任源仍未验，CR 不关闭。

## 冲突与证据

冻结 `EVIDENCE_SET_ELIGIBILITY` 要求持久幂等，现有内部命令把 Evidence、Audit 与收据同事务提交。浏览器在 POST 后断线/刷新可能拿不到回执；前端已先保存操作号并停止换号重试。冻结 `AUDIT_PROJECT_LIST` 仅 ProjectManager 可用，审计事件不包含 Idempotency-Key；CustomerManager 也能提交资格，却不能据 Audit 精确核对自己的操作。当前读取 API 只返回 Evidence 的**当前**资格，不能将某次操作号与已提交结果对应。若仅凭当前状态/审计时间推断，可能把另一位操作者的裁定误认作本次成功；若清除提醒再换 Key，可能造成重复命令或误导用户。

## 方案比较与选择

- A：前端保存理由/完整请求，在未知结果时自动同 Key 重放。会将潜在客户内容写入浏览器存储，且重新提交仍受身份/状态变化影响；不采用。
- B：扩大 CustomerManager 的项目 Audit 读取。违反冻结角色边界，审计仍不含操作号；不采用。
- C：新增受权、只读的原操作者收据回查，使用请求体传操作号；已提交只返回最小结果，未查到返回 `UNCONFIRMED`，绝不判定失败或自动重试。采用。

## 合同增量与安全边界

新增可选 `POST /api/v1/projects/{project_id}/evidence/{evidence_id}:lookup-eligibility-operation`，以及对应 GLOBAL 路径。请求体仅 `{ "operation_key": "..." }`；Key 不进入 URL、日志、响应、Audit 或浏览器长期存储。使用 POST 仅为避免查询 Key 落入 URL/访问日志，服务端保证无业务写入/收据预留；因此不要求新的 `Idempotency-Key` 或 `If-Match`，但必须验证可信 Origin/Host、Session、CSRF、License、当前项目 PM/CustomerManager 或 GLOBAL Admin、Evidence Scope/归属，再读取原 actor/project/operation/key 摘要对应的已完成收据。查无收据或并发尚未提交时统一返回 `UNCONFIRMED`，客户端继续保留原操作号；已完成且引用匹配返回 `COMPLETED` 与最小 EvidenceId/首次 HTTP 状态，不返回理由、正文、密钥或数据库结构。已完成收据引用不匹配必须失败关闭，不以猜测归属返回成功。当前 Evidence 状态另由原 GET 核对，`COMPLETED` 本身不是当前资格证明。

项目归档后允许当前有资格操作者只读核对历史，不允许再写资格；成员暂停/移除、Session/License失效仍拒绝。GLOBAL Admin 不获项目旁路。普通默认应用不挂载新端点，Windows 显式写组合经单独集成验收后才能开启；登录专用/只读组合保持关闭。接口为冻结 V1 的非 Breaking 增量，需独立 API 增量文档，不追写原 Contract。不得把 `UNCONFIRMED` 解释为可换 Key 重试。

## 差异、迁移/回滚与验证

改变首版 API Scope，但不改现有路由、Schema、ORM、幂等签名/Hash、业务状态或 License 算法；利用现有 `20260925_0015` 收据表。回滚为关闭新的可选路由/前端回查，保留全部已提交 Evidence、Audit 和收据历史。不存在生产数据回填；升级须先确认 `0015` 已应用，正式目标账户/HTTPS/License 门禁不因本 CR 放宽。

分项验收：收据只读查询 SQL/无 autoflush、权限矩阵、同 actor/key 匹配与跨 actor/project/scope 错误、归档历史读取、未提交/并发尚不可见/故障 `UNCONFIRMED` 或安全错误、收据与 Evidence 不一致失败关闭；可选 HTTP 默认关闭/CSRF/畸形/无日志 Key；隔离 PostgreSQL 真实提交与回滚、Windows 显式组合；前端在 `COMPLETED` 后仍 GET 当前资格而不把首次结果当现状。浏览器和正式环境另验，不以单元/合成测试关闭 Gate 3。
