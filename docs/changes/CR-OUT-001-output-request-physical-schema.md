# CR-OUT-001：OutputRequest 物理 Schema 实现映射

## 状态

`APPROVED_BY_CONTINUOUS_EXECUTION_AUTHORIZATION / IMPLEMENTED_STATIC_VALIDATION_PASS / DATABASE_ACCEPTANCE_PENDING`

用户持续授权允许在冻结方案物理细节不足时先记录变更、兼容性/迁移/回滚和验证计划后自主实施。此 CR 不改写 Gate 2 原始冻结内容，也不改变外部 API、Root、Scope 或业务状态语义。

## 背景与差异

冻结 DM-05 描述 OutputRequest、固定输入和 OutputContextSnapshot 的语义字段；SC-01 指定 `out_requests`、`out_context_snapshots`、`out_context_source_refs`、`out_context_evidence_refs`；SC-02 固定 OUT-01 为 R-PRJ，并固定幂等字段语义 `(project_id, output_type, input_fingerprint, template_version_id, policy_version)`；SC-03 固定 live 状态集合和索引名 `uq_out_requests__generation_live`。这些基线未逐表列出完整 SQL 列、子表键和 JSON Schema。仓库当前无 Output ORM/Migration/Owner，Document 公共上传也拒绝 GENERATED_ARTIFACT。

## 实施决策（物理细化，不改变业务合同）

1. `out_requests` 为 R-PRJ：uuidv7 PK、project/requester、output_type、固定 template_version_id（FK 至 Prototype TemplateVersion）、policy_version、plugin_operation、固定 input_fingerprint、generation_no、request_state、job_ref/current_execution_ref、idempotency_key/trace_id、attempt_count、created/started/completed/error/retryable、lock_version、retention_due_at。状态 CHECK 与冻结状态集合一致；当前执行引用可空。`input_fingerprint` 为由固定来源版本、模板版本、策略版本和输出类型确定的 SHA-256 bytea，不保存动态 latest/current 指针。
2. `out_context_snapshots` 与 Request 一对一，保存 `context_snapshot_id`、project/request 外键、schema_version、最小授权上下文 JSONB、独立 SHA-256 `context_fingerprint` 和 created_at。JSONB 只保存 API/DM-05 白名单字段，长度受限；不得包含 ORM 对象、路径、Secret 或未授权正文。
3. `out_context_source_refs`、`out_context_evidence_refs` 以显式 ordinal 保存固定多态来源标识；所有引用要求相同 project_id、非空 version id、唯一 ordinal。跨模块具体对象/版本由对应只读 Owner 在创建事务中校验；数据库 FK 只约束 request/project 与同一 Output aggregate 的 owned rows，不对尚未存在或异构的目标表伪造单一 FK。
4. live generation partial unique index 使用冻结键组成和 SC-03 状态谓词；generation_no 只用于显式重新生成的有序区分。请求幂等仍由 idempotency_key 和既有 IdempotencyService 收敛，不以 partial index 取代。
5. 外部 Job FK 只在 `job_ref` 非空时验证对象存在；Project/Job Scope 一致性由创建同事务的 Job Owner 证明。PLG-03 尚无生产物理表，`current_execution_ref` 暂为可空 UUID，后续 Plugin/Output 集成不得绕过 Owner 校验。

## 影响与风险

- 外部 `/api/v1` 不变；不增加产品 Root、不改变 PROJECT 隔离，也不开放任何下载或发布能力。
- 固定来源多态引用依赖应用 Owner 校验；未完成 Owner 时 Create 必须关闭，禁止仅凭 FK-less UUID 形成正式业务事实。
- JSONB 快照 schema 演进须版本化；旧 Snapshot 不原地重写。
- Partial unique 状态集合必须与 ORM 常量、迁移和 Repository SQL 一致，并测试并发冲突。
- Document 受控 GENERATED_ARTIFACT 内部登记、Artifact、Trace、Plugin/Worker、HTTP/UI 均不在本 CR/WBS 内。

## 迁移、回滚与验证

- 新增 Alembic revision，创建 OUT-01 Root 与 SC-01 三个 owned tables；不改旧 revision。空库升级、当前有数据库升级、schema introspection/drift、约束绕过负例、up/down/重升均验证。
- 降级前检查四表为空；存在任何 OutputRequest/Context 数据时拒绝 downgrade，避免静默丢弃业务记录。恢复优先使用迁移前 PostgreSQL 备份。
- 先跑 Output schema 定向测试与 Alembic drift，再跑完整后端测试并构建 wheel；不制造客户事实或调用外部 AI。
- 风险记录、代码/测试/版本说明均同步当前获准 feature 分支；推送前 fetch，发现未知远端变更则停止。

## 验收边界

CR-OUT-001 仅在列级实现与上述决策一致、Migration 可重复升降（有数据降级明确拒绝）、数据库负例与漂移验收通过后关闭。此决策不表示 Output API、生成工作流、Artifact 发布/下载、Pilot、Gate 或 Release 已通过。
