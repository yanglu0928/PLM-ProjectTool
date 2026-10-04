# SC-03：索引与关键查询计划 V1 候选

## 状态

`CANDIDATE / SC-03_COMPLETE / SC-04_NEXT / NOT_GATE_2_FROZEN / NO_MIGRATION_YET / PLAN_NOT_RUNTIME_VALIDATED`

本文件把 SC-01 的物理表边界和 SC-02 的字段/约束语义转换为 PostgreSQL 18 + pgvector 的索引、关键查询与执行计划验证候选。本阶段没有创建索引、业务表、ORM 或 Alembic Migration；所有 DDL、`EXPLAIN (ANALYZE, BUFFERS)` 和并发验证留在 SC-04。

## 已有证据与结论边界

- POC-02 在 Windows 11 的 PostgreSQL 18.6 + pgvector 0.8.6 上验证了 100,000 条、32 维合成向量 HNSW；20 组 Top-5 平均/最低 Recall 100%，HNSW P95 4.645 ms，执行计划命中 HNSW。
- POC-03 在 1,000 条合成记录上验证了 GIN + HNSW Hybrid Retrieval；`m=32`、`ef_construction=200`、`ef_search=200`、每通道 `4 × Top-K` 时 4 个场景 Top-5 Recall 100%。
- POC-03 的 50 条真实独立留出集 Top-5 为 98%，但分类 48%、引用 74% 失败。SC-03 只继承“检索链可用”和初始调参证据，不把下游质量写成 PASS。
- 上述性能不代表正式 Schema、真实维度、真实数据量或三平台生产性能。Debian 13 仍未实机验证；Windows Server 2025 的数据库 PoC 已在批准范围内验证。

## 核心决策

1. B-tree 是 PK、FK、唯一、授权过滤、状态/时间排序和图边的默认索引；不为低选择性状态列单独建索引。
2. PK/UNIQUE 自带的索引不重复创建。引用侧 FK 不由 PostgreSQL 自动建索引，SC-04 必须按本文件的访问路径生成或显式豁免。
3. PROJECT 列表统一以 `project_id` 为第一前缀，使用稳定的 `(sort_time DESC, root_id DESC)` keyset 分页；禁止把大 Offset 作为正式主路径。
4. GLOBAL_OR_PROJECT 查询拆为 GLOBAL 与指定 PROJECT 两个授权分支再合并，不使用“ProjectId 为空即全局可见”的模糊条件。
5. 条件唯一使用 partial unique index；谓词只使用不可变的常量状态集合，不在谓词中使用 `now()`、会话变量或跨表子查询。
6. 追加式大表按时间使用 B-tree 主访问路径；只有达到容量阈值并有计划证据时再增加 BRIN，不在 V1 默认分区。
7. 全文检索使用 Application 生成的受控 `search_body` + stored `tsvector` + GIN。中文原文不能直接依赖 `simple` 配置分词，必须先由统一文本规范化/分词策略产生可检索 Token。
8. 向量使用 HNSW + `vector_cosine_ops`。维度是 Index Model 的不可变属性；不同维度通过受控表达式 HNSW 索引族支持，新增维度必须走 Migration，Runtime Role 不执行 DDL。
9. 共享 HNSW 上的 Scope/Project/Index 过滤可能降低召回。查询强制过滤并使用 pgvector iterative scan；不足 Top-K 时执行受限扩大扫描或同 Scope 精确回退，不允许放宽 ProjectId。
10. Job/Outbox 使用短事务、原子状态更新、`FOR UPDATE SKIP LOCKED`、租约 fencing 和幂等唯一键；不承诺精确一次。
11. `INCLUDE` 只放窄且稳定的展示列；正文、JSONB、向量、密文、密码/Token 摘要和长错误不得进入 covering index。
12. 每个索引必须对应唯一约束、FK/删除检查、关键查询或已测性能问题；无消费者的“预防性索引”不进入 V1。

## 索引命名与生成规则

|类别|命名|规则|
|---|---|---|
|PK / UNIQUE / CHECK / FK|沿用 SC-02|约束拥有的索引不再创建 `ix_*` 副本|
|普通 B-tree|`ix_<table>__<semantic>`|列序与查询等值、范围、排序顺序一致|
|Partial unique|`uq_<table>__<semantic>`|谓词文本由 Migration 常量生成并测试|
|GIN FTS|`ix_<table>__search_gin`|只索引 `search_vector`|
|HNSW|`ix_rag_embed__v<dimension>_hnsw`|表达式 cast + 维度/AVAILABLE 常量谓词|
|BRIN|`ix_<table>__<time>_brin`|仅容量门槛通过后生成|

- PostgreSQL 标识符必须不超过 63 bytes；生成器先用稳定缩写，仍超长时追加 8 位语义 Hash。
- 相同列序、谓词和 operator class 的索引只保留一个；左前缀已覆盖的索引须有独立排序/选择性证据才保留。
- SC-04 输出最终 index manifest，并验证名称、表、列、谓词和 operator class 全库唯一。

## 通用访问索引 Profile

### C1：PK、唯一与引用侧 FK

- 每张 Root/child 表一个 uuidv7 PK；不再建同列普通索引。
- SC-02 的 regular UNIQUE/`NULLS NOT DISTINCT` 由唯一约束或唯一索引承载。
- 每个引用侧 FK 至少具有以完整 FK 列组为左前缀的 B-tree，除非行数上限很小且 SC-04 有显式豁免。
- 复合 Project FK 使用 `(project_id, target_id)` 或与主查询一致的 `(target_id, project_id)`；删除目标的反查必须能命中引用侧索引。
- current pointer 在 identity 侧不额外索引；Version 侧的复合唯一 `(version_id,parent_id[,project_id])` 已服务 FK 检查。

### C2：PROJECT mutable Root 列表

```text
(project_id, state, updated_at DESC, root_id DESC)
```

- 用于项目内状态列表和 keyset 翻页。
- 若正式查询不按 state 过滤，使用 `(project_id, updated_at DESC, root_id DESC)`，不能指望跳过中间 state 后仍稳定高效。
- `INCLUDE` 最多加入 code/title 等窄展示列；详情仍回表。

### C3：PROJECT append-only / runtime 记录

```text
(project_id, created_at DESC, record_id DESC)
(project_id, state, created_at DESC, record_id DESC)  # 仅状态队列/列表确有消费者
```

终态历史以时间列表为主；不为每个状态各建一个索引。

### C4：GLOBAL_OR_PROJECT

```text
(scope, project_id, state, updated_at DESC, root_id DESC)
```

GLOBAL 与 PROJECT 使用两个参数化查询分支。高频 GLOBAL-only 或 PROJECT-only 查询在 SC-04 计划证明确有收益后，可增加常量 partial index；不得按每个 Project 创建索引。

### C5：Version 与 owned child

```text
(parent_id, version_no DESC)
(project_id, parent_id, version_no DESC)       # PROJECT 授权路径
(version_id, ordinal, child_id)                # 有序 child
(version_id, child_id)                         # 无序 child/FK 反查
```

版本详情按明确 version_id 查；“当前正式版本”先解析 identity.current_approved_version_id，禁止用 `ORDER BY version_no DESC LIMIT 1` 冒充 Approved。

## 28 组唯一语义的物理实现

SC-02 的 28 组语义映射为 29 个物理唯一键；“Outline section order”一组需要 ordinal 和 section 两个唯一键。

|#|语义|实现|候选索引/约束|
|---:|---|---|---|
|1|用户名|regular unique|`uq_auth_users__username_norm`|
|2|Project code|regular unique|`uq_prj_projects__code_norm`|
|3|单项目成员|partial unique|`uq_prj_members__user_active`|
|4|项目成员重复|partial unique|`uq_prj_members__project_user_active`|
|5|部门代码|partial unique|`uq_prj_departments__project_code_live`|
|6|Project Workflow|regular unique|`uq_wfl_workflows__project`|
|7|Version no|各 Version 表 regular unique|`uq_<version_table>__parent_version_no`|
|8|一个 Active ReviewRound|partial unique `round_state='IN_REVIEW'`|`uq_rvw_rounds__review_in_review`|
|9|Review assignment|regular unique|`uq_rvw_assignments__round_reviewer`|
|10|一个 Active SecretVersion|partial unique `activated_at IS NOT NULL AND retired_at IS NULL`|`uq_plt_secret_versions__record_active`|
|11|Document Version|regular unique|`uq_doc_versions__document_version_no`|
|12|Evidence active binding|partial unique `state='ACTIVE'`|`uq_evd_bindings__active_subject`|
|13|Trace active edge|partial unique `state='ACTIVE'`|`uq_trc_links__active_edge`|
|14|Job idempotency|regular `UNIQUE NULLS NOT DISTINCT`|`uq_job_jobs__idempotency`|
|15|Job lease|partial unique `state='ACTIVE'`|`uq_job_leases__job_active`|
|16|Outbox consumption|regular unique|`uq_job_consumptions__event_consumer`|
|17|Prompt version|regular unique|`uq_ai_prompt_versions__template_no`|
|18|Embedding index version|regular `UNIQUE NULLS NOT DISTINCT`|`uq_rag_indexes__scope_purpose_version`|
|19|Active index|partial unique + `NULLS NOT DISTINCT`|`uq_rag_indexes__scope_purpose_active`|
|20|Embedding record|partial unique `state='AVAILABLE'`|`uq_rag_embeddings__index_chunk_available`|
|21|Survey assignment|regular `UNIQUE NULLS NOT DISTINCT`；全部历史唯一|`uq_srv_assignments__round_target`|
|22|Package membership|regular unique|`uq_<membership_table>__package_member`|
|23|Requirement relation|partial unique `state='ACTIVE'`|`uq_req_relations__active_edge`|
|24a|Outline ordinal|regular unique|`uq_sol_outline_sections__outline_ordinal`|
|24b|Outline section|regular unique|`uq_sol_outline_sections__outline_section`|
|25|WBS code|regular unique|`uq_pln_wbs_items__version_code`|
|26|Plugin package version|regular unique|`uq_plg_packages__plugin_version`|
|27|Enabled plugin operation|child 保存受控 plugin identity/启用投影；partial unique `is_enabled`|`uq_plg_operations__plugin_operation_enabled`|
|28|Output idempotency|partial unique；`REQUESTED/QUEUED/GENERATING/VALIDATING/SUCCEEDED`|`uq_out_requests__generation_live`|

限制：

- Partial predicate 中不使用参数或 `now()`；正式查询必须包含与索引一致、可被 planner 推导的状态谓词。
- 依赖 partial index 的状态集合由 Repository 以固定 SQL literal 生成，不能作为用户输入或 bind parameter；其他值仍全部参数化，禁止拼接用户文本。
- Active Lease 的“未过期”不放进 partial predicate；领取事务先以 fencing 方式关闭过期 Lease，再建立新 Active Lease。
- Plugin 启用唯一性不能通过跨表 partial index 实现；`plg_enabled_operations` 保存最小受控 `plugin_id_normalized` 与 `is_enabled` 投影，由 PluginService 同事务更新并由 trigger 校验所属 Installation 状态。
- Output 的状态白名单在 SC-04 生成 DDL 前必须与最终命名 CHECK 使用同一常量来源，避免谓词漂移。

## 关键查询目录

|Query ID|用途|主过滤/排序|索引 Profile|
|---|---|---|---|
|Q-AUTH-01|登录用户名定位|username_normalized|唯一键 #1|
|Q-PRJ-01|用户有效项目成员|user_id + active|唯一键 #3|
|Q-PRJ-02|项目内成员/部门列表|project_id + state + cursor|C2|
|Q-WFL-01|项目 Workflow 与最近迁移|project_id；workflow_id + created_at desc|#6 + C3|
|Q-VER-01|对象版本历史|project_id + parent_id + version_no desc|C5|
|Q-RVW-01|主题 Review/Active Round|subject tuple；review_id + IN_REVIEW|多态反查 + #8|
|Q-DOC-01|Document 固定版本/Parse 历史|document_id + version_no；version_id + created_at desc|#11 + C5/C3|
|Q-EVD-01|按主题找有效 Evidence|subject tuple + state|多态反查 + #12|
|Q-TRC-01|Trace 出边/入边|source tuple / target tuple + state|双向边索引|
|Q-AUD-01|项目/对象 Audit 时间线|project_id/target tuple + occurred_at desc|Audit 索引族|
|Q-JOB-01|领取到期 Job|state + available_at + priority|Job claim partial index|
|Q-JOB-02|回收过期 Lease|RUNNING + lease_expires_at|Lease recovery partial index|
|Q-OUT-01|投递 Outbox|delivery state + next_attempt_at|Outbox claim partial index|
|Q-RET-01|Retention 到期候选|terminal + retention_due_at|Retention partial index|
|Q-RAG-01|授权 Hybrid Retrieval|scope/project/index + FTS/vector + Top-K|GIN + HNSW + metadata B-tree|
|Q-RAG-02|向量精确回退|同 index/scope/project + cosine order|metadata filter + bounded exact scan|
|Q-REQ-01|Requirement 图双向遍历|project/version + source/target|双向边索引|
|Q-WBS-01|WBS 子项与依赖双向遍历|plan_version + parent/source/target|树/双向边索引|
|Q-PLG-01|已启用操作解析|plugin identity + operation + enabled|唯一键 #27|
|Q-OUTPUT-01|输出幂等与历史|project + fingerprint/policy；created cursor|#28 + C3|

## Job、Lease 与 Outbox

### Job 领取

候选索引：

```sql
CREATE INDEX ix_job_jobs__claim
ON plm.job_jobs (priority DESC, available_at, job_id)
WHERE state IN ('QUEUED','RETRY_WAIT');
```

候选短事务：

```sql
WITH picked AS (
  SELECT job_id
  FROM plm.job_jobs
  WHERE state IN ('QUEUED','RETRY_WAIT')
    AND available_at <= statement_timestamp()
  ORDER BY priority DESC, available_at, job_id
  FOR UPDATE SKIP LOCKED
  LIMIT :batch_size
)
UPDATE plm.job_jobs j
SET state='RUNNING', lock_version=lock_version+1
FROM picked
WHERE j.job_id=picked.job_id
RETURNING j.job_id, j.project_id, j.job_type, j.lock_version;
```

- 外部调用不在领取事务内执行；提交领取与 Lease 后立即结束事务。
- 批次初值为 1～20，由 SC-04 并发测试决定，不把大批量锁行作为吞吐优化。
- 每次发布结果校验 `(job_id, fencing_token, state='RUNNING')`，过期 Worker 更新影响 0 行并失败关闭。

### Lease 回收与 heartbeat

```text
ix_job_jobs__lease_expiry (lease_expires_at, job_id) WHERE state='RUNNING'
uq_job_leases__job_active (job_id) WHERE state='ACTIVE'
ix_job_leases__heartbeat (job_id, fencing_token, lease_expires_at)
```

`lease_expires_at < statement_timestamp()` 只出现在查询条件，不进入索引谓词。Heartbeat 使用 expected fencing token；回收先追加 Lease 终止事件，再使 Job 回到 RETRY_WAIT/FAILED。

### Outbox 投递

```text
ix_job_outbox__claim
  (next_attempt_at, event_id)
  WHERE delivery_state IN ('PENDING','RETRY_WAIT')

uq_job_consumptions__event_consumer
  (event_id, consumer_id)
```

投递同样使用 `FOR UPDATE SKIP LOCKED` + 短状态事务。至少一次重复通过消费唯一键和业务幂等键消解；DEAD/未解决事件不进入普通 Retention 清理。

## Audit、Review、Evidence 与 Trace

### Audit

```text
ix_aud_events__project_time
  (target_project_id, occurred_at DESC, audit_event_id DESC)
ix_aud_events__target_time
  (target_owner_module, target_object_type, target_object_id,
   target_version_id, occurred_at DESC)
ix_aud_events__actor_time
  (actor_id, occurred_at DESC, audit_event_id DESC)
```

- Audit 详情严格按 actor/project/resource 权限返回，索引不能成为跨项目枚举接口。
- 当 Audit 表达到 5,000,000 行或 2 GiB 且时间相关性实测良好时，评估 `occurred_at` BRIN；未达门槛不创建。
- V1 不分区。若单表维护窗口、备份或清理超出 Release 目标，再以容量证据发起后续设计，不在 SC-03 假设高规模。

### Review / Evidence / Trace 多态反查

```text
ix_rvw_reviews__subject
  (subject_owner_module, subject_object_type, subject_object_id,
   subject_project_id, created_at DESC)
ix_evd_bindings__subject_active
  (subject_owner_module, subject_object_type, subject_version_id,
   subject_project_id, evidence_id) WHERE state='ACTIVE'
ix_trc_links__source_active
  (source_owner_module, source_object_type, source_version_id,
   source_project_id, relation_type, target_version_id) WHERE state='ACTIVE'
ix_trc_links__target_active
  (target_owner_module, target_object_type, target_version_id,
   target_project_id, relation_type, source_version_id) WHERE state='ACTIVE'
```

查询先建立授权 Scope，再访问边。Trace 图分页和深度均有上限；无环、合法关系与逐节点授权仍由 Application/transaction guard 保证，索引不替代业务规则。

## Requirement 与 WBS 图

```text
ix_req_relations__out
  (project_id, source_version_id, relation_type, target_version_id)
  WHERE state='ACTIVE'
ix_req_relations__in
  (project_id, target_version_id, relation_type, source_version_id)
  WHERE state='ACTIVE'

ix_pln_wbs_items__parent_order
  (plan_version_id, parent_item_id, ordinal, wbs_item_id)
ix_pln_wbs_deps__out
  (plan_version_id, predecessor_item_id, successor_item_id)
ix_pln_wbs_deps__in
  (plan_version_id, successor_item_id, predecessor_item_id)
```

- 递归查询始终固定 project/plan/version，并设置最大深度/节点数；不能在全库无 Scope 地执行递归 CTE。
- 写入依赖前在同一 PlanVersion/Project 内验证无环；`dependency_type='FS'` 由 CHECK，索引只加速邻接访问。

## Retention、Hold 与保护引用

高容量终态表使用：

```text
(retention_due_at, root_id)
WHERE retention_due_at IS NOT NULL AND state IN (<可清理终态白名单>)
```

候选发现查询只返回小批 ID，随后逐对象验证：Active Hold、Review/Evidence/Trace/Artifact/Audit 解释链、活动 Job/Lease、未完成 Outbox 和文件恢复状态。禁止用一个跨全库巨型 DELETE 或 CASCADE 清理。

```text
ix_plt_retention_holds__selector_active
  (scope, project_id, object_owner, object_type, object_id)
  WHERE state='ACTIVE'
```

- 不把 `retention_due_at <= now()` 写进 partial predicate。
- 清理预览与执行使用同一 policy version 和幂等键；结果批次化并写 Audit。
- 保护引用反查使用各 FK/多态 target 索引；SC-04 必须对 65 个 Root 生成反向引用清单，遗漏即失败。

## RAG、全文与向量检索

### 元数据与全文

`rag_document_chunks` 至少具有独立列：`scope`、`project_id`、`embedding_index_id/generation`、`document_version_id`、`state`、`search_body`、`search_vector`。核心授权和来源字段不得只存 JSONB。

```sql
search_vector tsvector GENERATED ALWAYS AS
  (to_tsvector('simple', search_body)) STORED;

CREATE INDEX ix_rag_chunks__search_gin
ON plm.rag_document_chunks USING gin (search_vector);
```

`search_body` 由统一 Retrieval/Parser 策略构造，包含规范化、去噪和适合中文的受控 Token；不得假设 PostgreSQL `simple` 配置能自动完成中文分词。查询参数生成 `to_tsquery('simple', :safe_tsquery)`，Token/操作符由 Application 白名单构造，不拼接原始 SQL。

元数据索引：

```text
ix_rag_chunks__project_index_state
  (project_id, embedding_index_id, state, chunk_id)
ix_rag_chunks__global_index_state
  (embedding_index_id, state, chunk_id) WHERE scope='GLOBAL'
```

### 维度与 HNSW

这是对 SC-02 `vector(n)` 语义的物理细化：n 仍由 Index Model 固定，但共享记录表不把全系统锁成单一维度。逻辑列允许保存受控 `vector` 值，同时保存 `embedding_dimension`；数据库以 `CHECK (vector_dims(embedding)=embedding_dimension)` 和 `(embedding_index_id,embedding_dimension)` 复合 FK 保证记录与 Index Model 一致。每个受支持维度由 Migration 创建固定 cast 的表达式索引：

```sql
CREATE INDEX ix_rag_embed__v<dimension>_hnsw
ON plm.rag_embedding_records
USING hnsw ((embedding::vector(<dimension>)) vector_cosine_ops)
WITH (m=32, ef_construction=200)
WHERE state='AVAILABLE' AND embedding_dimension=<dimension>;
```

- Index Model、dimension、Chunk Profile 或 normalization 不兼容变化必须新建 EmbeddingIndex 并全量重建。
- 未经 Migration 支持的新维度不得激活；可在受限数据量下精确验证，但不能绕过 Gate 直接建立 Runtime DDL。
- pgvector 0.8.6 的 HNSW `vector` 支持上限为 2,000 维。大于 2,000 维的模型在 V1 默认判为 INCOMPATIBLE；若要采用 `halfvec`、量化、子向量或降维，必须先补质量 PoC 和 Gate 2 变更评审。
- `m=32`/`ef_construction=200` 是 POC-03 初始候选，不是不可修改常量；SC-04 用正式候选维度和代表数据复验 build time、内存、Recall 与 P95。

### 授权 Hybrid 查询

每次查询固定：`scope`、`project_id`、`embedding_index_id`、dimension、model/version、metadata policy 和 Top-K。事务内候选设置：

```sql
SET LOCAL hnsw.ef_search = 200;
SET LOCAL hnsw.iterative_scan = strict_order;
```

Vector 与 FTS 各取初始 `4 × Top-K` 候选，由 RetrievalService 按版本化策略融合并交给 Reranker。若授权过滤后不足 Top-K：

1. 在相同 Scope/Project/Index 下提高扫描上限；
2. 仍不足且候选集合低于容量阈值时执行同范围精确 cosine 查询；
3. 仍不足则返回资料不足，绝不移除 ProjectId 或混入其他 Index generation。

GLOBAL 与 PROJECT 候选分别查询、分别授权，再由策略融合；PROJECT 数据不得进入 GLOBAL 索引。Golden 标签、人工答案和未授权正文不得进入 `search_body`、query 或 Context。

## 查询计划与性能验收计划

SC-04 为每个 Query ID 固化参数化 SQL 和代表数据，执行：

```text
EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, FORMAT JSON)
```

|类别|最小数据/并发候选|验收观察|
|---|---|---|
|Project 列表/版本|至少 100k Root/Version，含多项目偏斜|命中 Project 前缀索引；keyset 稳定；无跨项目行|
|Job/Outbox|至少 100k 历史 + 10k 可领取，20 并发 Worker|无重复有效 Lease；无长事务；无饥饿；过期 fencing 拒绝|
|Audit/Trace/Evidence|至少 1m Audit、100k 边/绑定|项目/对象反查命中索引；保护引用无遗漏|
|Retention|至少 100k 到期/未到期混合|小批候选索引扫描；Hold/引用/活动任务全部阻断|
|RAG|至少复用 POC-02 100k 基线，并使用正式候选维度/多项目偏斜|HNSW/GIN 命中；Top-K 充足；与同 Scope 精确结果比较 Recall|
|WBS/Requirement 图|最大允许节点/边候选 + 环/跨项目负例|双向邻接命中；深度/节点上限生效|

通用判定：

- 高选择性关键查询不得因缺索引退化为大表全表扫描；小表由 planner 选择 Seq Scan 不自动判 FAIL。
- 检查 estimated/actual rows 偏差、shared read/hit、temp spill、sort method、锁等待和执行时间，不只检查索引名称。
- 非 AI GET P95 ≤ 500 ms、普通写 P95 ≤ 1 s、长任务提交 ≤ 1 s 是既有初始目标，必须在 SC-04/后续性能环境实测后才能写 PASS。
- HNSW Recall 以同 Scope/Project/Index 的 exact cosine 结果为基准；不能用下游 LLM 分类正确率替代检索 Recall。
- 每个新增索引记录大小、build time、写放大和用途。单表 secondary index 超过 8 个、索引总大小超过表大小 2 倍或写 P95 退化超过 20% 时必须专项评审，不自动继续堆索引。

## 运维与生命周期

- 大批导入/重建先写新 generation，再建/验证索引并原子切换 Active pointer；旧 generation 按 R5 Retention 保留，不覆盖。
- `ANALYZE` 在批量装载和激活前执行；Autovacuum 参数只在 SC-04 有写入/膨胀证据时逐表调整。
- HNSW rebuild、REINDEX、VACUUM 和备份窗口纳入 Release 运维；不能在 API 请求内执行。
- V1 不使用按 Project 动态分区、每项目 HNSW、运行时 DDL 或额外向量数据库。若共享 HNSW 在代表性多租户数据上无法达到 Recall/时延目标，先评估固定 hash partition；仍属 PostgreSQL 方案，但必须在 Gate 2 前补充证据。
- Windows 11/Server 的已有 PoC 结果可作为可行性证据；Debian 13 不生成未经验证的性能结论。

## 风险与关闭条件

|Risk ID|风险|当前控制|关闭条件|
|---|---|---|---|
|SC3-R01|共享 HNSW 过滤后候选不足|强制 Scope/Project/Index、iterative scan、精确回退|SC-04 多项目偏斜 Recall/隔离测试|
|SC3-R02|可配置 Embedding 维度无法由单一 `vector(n)` 覆盖|受控 dimension 列 + Migration 表达式索引族|正式模型维度 Migration/切换测试|
|SC3-R03|中文 FTS `simple` 不自动分词|Application 受控 Token 化 + GIN；Vector/Rerank 补充|真实中文查询 Recall 与 query 安全测试|
|SC3-R04|Partial predicate 与状态 CHECK 漂移|同一常量源生成 CHECK/索引/查询|SC-04 schema introspection + 状态迁移测试|
|SC3-R05|Job `SKIP LOCKED` 造成饥饿或重复发布|稳定排序、小批次、Lease fencing、幂等键|20 Worker 并发/崩溃/回收测试|
|SC3-R06|无 RLS 时缺少 Project 前缀造成越权或慢查询|ProjectAuthorizationService + 强制查询模板 + 复合约束|Permission/跨项目负测 + plan lint|
|SC3-R07|Audit/Trace/Retention 索引写放大|最小索引族、BRIN 容量门槛、索引预算|代表写负载与 size/bloat 报告|
|SC3-R08|多态保护引用遗漏导致错误清理|source/target 双向索引 + 65 Root 反向引用清单|SC-04 清理预览与悬空负测|
|SC3-R09|HNSW 参数直接沿用合成 PoC|参数仅为候选，按正式维度/数据复验|Recall/P95/build/memory 报告|
|SC3-R10|索引计划在三平台表现不同|DDL 保持跨平台；分别记录验证范围|Windows 11/Server 回归；Debian Release 约束|
|SC3-R11|Embedding 模型维度超过 HNSW `vector` 2,000 上限|激活前 capability/dimension 检查，默认 INCOMPATIBLE|如需 halfvec/量化/降维，先完成质量 PoC 与 Gate 2 评审|

## SC-03 验收

- 已明确 PK/UNIQUE 复用、引用侧 FK、Project 列表、Version/child 五类通用索引规则：PASS。
- SC-02 的 28 组唯一语义已映射为 29 个物理唯一键，并标明普通/条件唯一边界：PASS。
- PROJECT/GLOBAL_OR_PROJECT 授权前缀、keyset 分页和无 RLS 查询边界明确：PASS。
- 20 个关键 Query ID 已登记主过滤、排序和索引 Profile：PASS。
- Job 领取、Lease heartbeat/回收、Outbox 投递的 `SKIP LOCKED`、fencing 和幂等路径明确：PASS。
- Audit、Review、Evidence、Trace 的项目/对象时间线与双向保护引用索引明确：PASS。
- Requirement/WBS 双向图索引、Scope、深度与无环责任边界明确：PASS。
- Retention 到期发现、Hold 与保护引用预检路径明确，未使用时间函数 partial predicate：PASS。
- 中文全文 GIN、按维度 HNSW、Project 过滤、iterative scan、Hybrid 候选和精确回退明确：PASS。
- 已继承 POC-02/03 可行性证据，并明确真实质量失败和正式性能尚未验证：PASS。
- SC-04 的数据规模、并发、`EXPLAIN`、Recall、写放大与索引预算验收计划明确：PASS。
- 未创建 ORM、Migration、表或索引，正式业务编码仍由 Gate 2 阻塞：PASS。

## 下一步

SC-04：生成 Alembic Schema 基线与 index manifest，执行空库 up/down、有数据升级/回退、直接 SQL 负向约束、关键查询计划、Job/Outbox 并发、Retention/恢复和敏感字段扫描。
