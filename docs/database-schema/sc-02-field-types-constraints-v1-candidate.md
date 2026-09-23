# SC-02：字段、类型与约束 V1 候选

## 状态

`CANDIDATE / SC-02_COMPLETE / SC-03_NEXT / NOT_GATE_2_FROZEN / NO_MIGRATION_YET`

本文件为 SC-01 的 65 个 primary table 与 owned table 确定 PostgreSQL 18 字段类型、主键、Scope/ProjectId、版本、唯一、外键、CHECK、不可变与乐观并发规则。索引实现、pgvector/全文检索参数、Migration SQL 和运行测试分别在 SC-03/04 完成。

本候选依据仓库内已验证的 PostgreSQL 18.6 官方文档能力：`uuidv7()`、`uuid`、`jsonb`、`timestamptz`、`NULLS NOT DISTINCT`、`DEFERRABLE` 和 generated column。只使用基线 PostgreSQL 18 + pgvector，不新增数据库产品。

## 核心决策

1. 所有业务 PK 使用 PostgreSQL `uuid`，Root/Owned Entity 默认 `DEFAULT uuidv7()`；外部提供的 ID 不允许覆盖服务器生成值，导入场景走专用受审命令。
2. `created_at/updated_at/started_at/completed_at` 使用 `timestamptz(6)`；数据库连接和应用统一 UTC。计划日历字段使用 `date`，持续时间使用非负整数分钟，不用无单位数字。
3. 状态、Scope、关系类型等受控枚举使用 `text + named CHECK`，不使用 PostgreSQL ENUM；这样 Alembic 可通过增删 CHECK 演进并可靠回退。
4. 用户可见文本使用 `text + char_length CHECK`；不用 `char(n)`，也不把 `varchar(n)` 当作安全边界。代码/名称/标题按统一上限检查。
5. SHA-256、指纹、Token/CSRF 摘要使用 `bytea` 并检查 `octet_length`；密码使用自描述的 `text` 哈希串，不存明文或自制固定长度摘要。
6. PROJECT 与 GLOBAL_OR_PROJECT 的 Scope/ProjectId 使用显式列和 CHECK；高频授权/跨 Root 引用使用 `(object_id, project_id)` 复合 FK 候选，禁止只信任 JSON 或 ORM。
7. 所有跨 Aggregate FK 默认 `ON DELETE NO ACTION / ON UPDATE NO ACTION` 且 `NOT DEFERRABLE`；V1 不使用跨聚合 CASCADE。Root-owned child 也先显式顺序清理，SC-04 证明安全后才可逐表白名单 CASCADE。
8. current approved pointer 使用同父对象复合 FK + Owner 状态校验；历史引用直接指向 Version PK。数据库 FK 保证归属，Application/约束触发器保证目标已 Approved。
9. Version 内容和 Append-only 记录使用数据库写保护触发器候选 + Application Guard；状态迁移采用白名单和 expected lock_version，不允许 last-write-wins。
10. V1 不依赖 PostgreSQL RLS 作为授权机制；ProjectAuthorizationService 是主边界，显式 ProjectId/复合约束提供数据库防漂移。引入 RLS 需单独安全 PoC，不能替代应用授权。

## PostgreSQL 基础类型规范

|语义|PostgreSQL 18 类型|约束/说明|
|---|---|---|
|业务主键/外键|`uuid`|PK 默认 `uuidv7()`；FK 无默认值|
|trace_id / correlation_id|`uuid`|应用或入口生成；不作为业务 FK|
|UTC 时间|`timestamptz(6)`|创建默认 `statement_timestamp()`；业务完成时间由命令显式写入|
|计划日期|`date`|不隐含时区；项目展示时区另存 IANA zone name|
|持续时间|`integer` 分钟|`CHECK >= 0`；需更大范围时 SC-03 容量评估|
|版本号/序号/层级|`integer`|`CHECK > 0` 或 `>= 0`；WBS level 为 1..6|
|乐观锁/fencing|`bigint`|`DEFAULT 0 CHECK >= 0`；每次受控更新加 1|
|计数/字节/Token|`bigint`|`CHECK >= 0`；文件 size 不用 integer|
|布尔值|`boolean`|关键列 `NOT NULL`，显式默认|
|短代码/枚举|`text`|ASCII/长度/白名单 CHECK；不使用 PG ENUM|
|名称/标题/说明|`text`|按字段类别使用 char_length CHECK|
|正文|`text` 或受控 File/Document Ref|大正文和文件优先引用；不进日志/Event|
|结构快照|`jsonb`|至少检查 `jsonb_typeof`；核心 FK/Scope/状态不得只存在 JSON|
|Hash/指纹|`bytea`|SHA-256/内容指纹 `octet_length=32`|
|Ed25519 公钥/签名|`bytea`|公钥 32 bytes、签名 64 bytes；私钥禁止进入客户库|
|密码哈希|`text`|自描述算法/参数串；只由 PasswordHasher 解释|
|IP 地址|`inet`|可选 Audit 安全字段；最小化保存|
|金额/精确成本|`numeric(20,8)`|仅实际需要时使用；禁止浮点累计费用|
|检索/模型分数|`double precision`|Application 拒绝 NaN/Infinity；范围按策略字段校验|
|向量|`vector(n)`|仅 `rag_embedding_records`；n 与 Index Model 固定，SC-03 细化|

### 文本上限类别

|类别|上限|示例|
|---|---:|---|
|CODE_64|64 chars|project_code、capability_code、error_code、task_type|
|IDENTIFIER_128|128 chars|username_normalized、provider_model_key、plugin_id|
|NAME_255|255 chars|display_name、document title short name、MIME、operation|
|TITLE_500|500 chars|Requirement/Action/WBS/Solution title|
|SUMMARY_2000|2,000 chars|reason、impact、recommendation、safe error summary|
|LONG_TEXT|无固定数据库上限；应用限额|受权正文、AI 结果；优先 Document/File Ref|
|LOCATOR_1024|1,024 chars|storage_locator、source locator；禁止客户端绝对路径|

长度按 Unicode 字符 `char_length` 检查；上传字节大小另由 API/文件策略控制。

## 通用列 Profile

### M-DEP：Deployment mutable identity

```text
<root>_id uuid PK DEFAULT uuidv7()
state text NOT NULL
created_at timestamptz(6) NOT NULL
created_by uuid NULL/NOT NULL by bootstrap rule
updated_at timestamptz(6) NOT NULL
updated_by uuid NULL/NOT NULL by bootstrap rule
lock_version bigint NOT NULL DEFAULT 0
retention_policy_id uuid NULL
retention_due_at timestamptz(6) NULL
```

适用部署级配置/身份。`created_by` 只有安装引导创建记录可为空，之后必须是 User/SystemActor，并由 Audit 解释。

### M-GLB：Global mutable identity

沿用 M-DEP 的主键、创建/更新时间与乐观并发列，但业务 Scope 固定为 GLOBAL，不保存 `scope` 或 `project_id`；它不等于 Deployment Scope，且不能被项目数据反向修改。

### M-PRJ：Project mutable identity

在 M-DEP 基础上增加：

```text
project_id uuid NOT NULL
UNIQUE (<root>_id, project_id)
FK project_id → prj_projects(project_id) ON DELETE NO ACTION
```

项目归档后 Application 拒绝新写；数据库 FK 防止孤立 ProjectId。

### M-SCP：GLOBAL_OR_PROJECT mutable identity

```text
scope text NOT NULL CHECK (scope IN ('GLOBAL','PROJECT'))
project_id uuid NULL
CHECK (
  (scope='GLOBAL' AND project_id IS NULL) OR
  (scope='PROJECT' AND project_id IS NOT NULL)
)
UNIQUE NULLS NOT DISTINCT (<root>_id, scope, project_id)
```

GLOBAL 专用 Root 可使用固定 GLOBAL Profile，不重复 scope 列；PROJECT 专用 Root 使用 M-PRJ。

### V-GLB / V-PRJ / V-SCP：不可变 Version

```text
<version>_id uuid PK DEFAULT uuidv7()
<parent>_id uuid NOT NULL                # 无单独 parent Root 时使用 series_id
project_id uuid                          # V-PRJ 必填；V-GLB 省略；V-SCP 按 scope CHECK
version_no integer NOT NULL CHECK (version_no > 0)
version_state text NOT NULL CHECK (...)
content_fingerprint bytea NOT NULL CHECK (octet_length(...)=32)
supersedes_version_id uuid NULL
created_at timestamptz(6) NOT NULL
created_by uuid NOT NULL
UNIQUE (<parent>_id, version_no)
UNIQUE (<version>_id, <parent>_id [, project_id])
```

- parent FK 与 supersedes 复合 FK 保证同 parent/Project；Application 另验证 supersedes.version_no 较小且无环。
- Version 内容表及 owned children 在进入 IN_REVIEW 后只读；仅独立生命周期/Review 投影可变。
- 版本状态值由每类对象白名单决定，不使用一个万能状态集合。

### A-DEP / A-PRJ / A-SCP：append-only record

使用 uuidv7 PK、Scope/Profile、created_at/by、trace_id；不含 updated_at/lock_version。更正通过 replacement/superseded/revoked 记录或受控状态事件，不允许普通 UPDATE/DELETE。

### R-DEP / R-PRJ / R-SCP：runtime aggregate

使用 uuidv7 PK、Scope/Profile、state、attempt/correlation、created/started/completed、error_code、retryable、lock_version、retention_due_at。必须检查完成时间顺序，终态不能复活。

### SEC-DEP：signed/security state

使用 Deployment Scope、uuidv7 PK、签名/Hash/credential version、状态、创建/验证时间和 Audit 引用。安全材料长度固定；任何失败状态不能通过通用 UPDATE 改成成功，必须新建验证事件或专用命令。

## 65 个 Root 的 Profile 分配

|Root IDs|Profile|Scope/版本说明|
|---|---|---|
|PLT-01|M-DEP|配置 identity；配置版本在 child version table|
|PLT-02|SEC-DEP|Secret identity；SecretVersion 不可变|
|AUT-01|M-DEP|User identity + credential version|
|AUT-02|R-DEP|Session 有期限、撤销和 credential_version|
|PRJ-01|M-DEP|Project 本身属于部署，project_id 即自身 PK|
|PRJ-02、PRJ-03、WFL-01|M-PRJ|成员、部门、Workflow|
|WFL-02|A-PRJ|StageTransition append-only|
|RVW-01|M-SCP|Review 可 GLOBAL/PROJECT|
|RVW-02|A-SCP|Round/Decision 历史追加；活动状态由专用列/事件投影|
|TRC-01、EVD-02|A-SCP|不可变关系 + supersede/revoke|
|AUD-01|A-DEP|事件含可选 target_project_id，但 Owner Scope 为 DEPLOYMENT|
|LIC-01、LIC-02、LIC-03|SEC-DEP|签名/机器/可信时间安全状态|
|DOC-01、DOC-03、EVD-01|M-SCP|Document/File/Evidence 可 GLOBAL/PROJECT|
|DOC-02|V-SCP|不可变 DocumentVersion|
|DOC-04|R-SCP|解析 Attempt 运行事实|
|JOB-01|R-SCP|Job 可 Global/Project，额外 job_scope 白名单|
|JOB-02|A-SCP|Outbox append-only payload refs + delivery projection|
|AI-01、AI-02、AI-03|M-DEP|Provider/Model/Prompt 配置；版本在 child table|
|AI-04|R-SCP|AITask + Invocation Attempt|
|RAG-01、RAG-02|M-SCP|Chunk/Index generation 可 GLOBAL/PROJECT|
|RAG-03、RAG-04|R-SCP|Embedding/检索运行记录|
|CAP-01|M-GLB|GLOBAL identity，不存 project_id|
|CAP-02|V-GLB|GLOBAL BaselineVersion|
|HND-01、HND-03|M-PRJ|分析 identity / ActionItem|
|HND-02|V-PRJ|HandoverAnalysisVersion|
|SRV-01、SRV-03、SRV-04|M-PRJ|Survey/Round/Assignment|
|SRV-02、SRV-05|V-PRJ|SurveyVersion；Conclusion 使用 conclusion_series_id|
|REQ-01、REQ-02|M-PRJ|Package/Requirement identity|
|REQ-03|V-PRJ|RequirementVersion|
|REQ-04|A-PRJ|RequirementRelation append-only/supersede|
|PRT-01、PRT-02|M-PRJ|Package/Prototype identity|
|PRT-03|V-PRJ|PrototypeVersion|
|PRT-04|M-SCP|Template identity；child TemplateVersion 使用 V-SCP|
|PRT-05|A-PRJ|RequirementPrototypeLink|
|SOL-01|M-SCP|ReferenceSolution identity；child ReferenceVersion|
|SOL-02、SOL-04|M-PRJ|Outline/Section identity|
|SOL-03、SOL-05、SOL-06|V-PRJ|Outline/Section/StructuredSpec Version；Spec 使用 spec_series_id|
|PLN-01|M-PRJ|Plan identity|
|PLN-02|V-PRJ|PlanVersion|
|PLN-03|M-SCP|ReferencePlan identity；child ReferenceVersion|
|OUT-01|R-PRJ|OutputRequest runtime|
|OUT-02|M-PRJ|OutputArtifact 发布状态，内容不可覆盖|
|PLG-01|SEC-DEP|签名包不可变|
|PLG-02|M-DEP|安装/启停状态|
|PLG-03|R-PRJ|项目 OutputContext 下执行|

Profile 分配覆盖 65 个 Root；SC-02 不增加或合并 Root。

## Scope 与 ProjectId 约束

### PROJECT Root

- `project_id uuid NOT NULL`，FK 到 `prj_projects`。
- 表上提供 `UNIQUE (root_id, project_id)`，供 child/cross-root 复合 FK 使用。
- 高频授权/跨 Root child 保存 project_id，并使用 `(parent_id, project_id)` FK 到父表相同组合。
- 只在父聚合内部、无独立授权/跨 Root 查询的 child 可不冗余 project_id；查询必须 join parent。

### GLOBAL_OR_PROJECT Root

- `scope` 只允许 GLOBAL/PROJECT；Scope/ProjectId 二元 CHECK 固定。
- 所有复合唯一使用 `NULLS NOT DISTINCT` 处理 GLOBAL 的 NULL project_id，避免多个“空项目”绕过唯一语义。
- Scope/project_id 创建后由不可变列触发器保护。

### Project Root 自身

`prj_projects.project_id` 是 Project PK；其他 PROJECT 表只引用该列。Project 不再额外保存 self project_id，也不保存 Workflow current stage。

### RLS 决策

V1 不创建依赖会话变量的 Row-Level Security Policy，原因是 API、Worker、Migration、恢复与管理员诊断需不同上下文，错误设置可能造成绕过或不可恢复锁定。所有读写必须先经 ProjectAuthorizationService；数据库通过显式 ProjectId、复合 FK、唯一/CHECK 和测试提供第二层防漂移。未来启用 RLS 属安全机制变更，需 PoC、连接池上下文清理和管理员恢复方案。

## Version、current pointer 与不可变约束

### 同父 current pointer

每个逻辑 identity table：

```text
current_approved_version_id uuid NULL
latest_version_id uuid NULL                  # 只有确需编辑导航的对象
UNIQUE (root_id, project_id)                 # PROJECT
```

Version table 提供 `UNIQUE (version_id, parent_id, project_id)`；identity 的复合 FK 同时带 root_id/project_id，保证 pointer 不指向其他对象/项目的 Version。

目标是否 APPROVED 不能由普通 FK 表达，使用 Owner 命令内状态校验 + deferred constraint trigger 候选；SC-04 必须测试绕过 ORM 的非法 pointer 更新被拒绝。

### Version 内容保护

- Version identity/parent/version_no/fingerprint/supersedes/Scope 永久不可更新。
- 进入 IN_REVIEW 后，Version 内容列和 owned child INSERT/UPDATE/DELETE 均拒绝。
- Review/生命周期状态不与正文混写；允许的状态变更只经 Owner 命令和状态白名单。
- 通用触发器函数按表配置 immutable column list 和 parent state lookup，生成器输出显式触发器；禁止一个接收任意 SQL 的动态触发器。
- Application 在提交 Review 前重新计算 content_fingerprint，数据库保存结果；DB 不负责对外部 File 正文重算 Hash。

### 乐观并发

Mutable Root 更新使用：

```sql
UPDATE ...
SET ..., lock_version = lock_version + 1, updated_at = statement_timestamp()
WHERE root_id = :id AND lock_version = :expected;
```

影响行数必须为 1；0 表示不存在/无权/并发冲突，外部错误不泄露资源存在性。Append-only/Version 表不使用通用 last-write-wins。

## FK 与删除动作

|关系类别|FK|删除动作|更新动作|说明|
|---|---|---|---|---|
|Root → Project/User/固定 Root|立即 FK|NO ACTION|NO ACTION|目标 ID 不变|
|Version → parent Root|立即复合 FK|NO ACTION|NO ACTION|同 Scope/Project|
|supersedes → prior Version|自引用复合 FK|NO ACTION|NO ACTION|Application 检查较早且无环|
|current pointer → Version|复合 FK；状态另校验|NO ACTION|NO ACTION|可空，目标必须同 parent|
|Owned child → Root/Version|立即 FK|NO ACTION|NO ACTION|V1 显式顺序清理，不启用 CASCADE|
|Membership/link → 两端|两个立即 FK|NO ACTION|NO ACTION|移除 link 不影响两端|
|Review/Trace/Audit 多态目标|无普通目标 FK|Retention Guard|N/A|discriminator/Scope CHECK + Owner Port|

默认 `NOT DEFERRABLE`。只有 current pointer Approved 校验、同事务批量图校验等确有证据的约束可使用 `DEFERRABLE INITIALLY DEFERRED` constraint trigger；不把可延期约束作为插入顺序问题的通用逃生口。

## 受控状态与 CHECK

- 每个表使用独立命名 CHECK，例如 `ck_req_requirement_versions_state`；不创建全局 PG ENUM。
- CHECK 只验证单行合法值、长度、范围和列组合；跨行状态迁移、无环和目标状态由 Application + trigger/transaction guard。
- `error_code` 使用前缀 CHECK 候选：AUTH/PROJECT/FILE/AI/RAG/PLUGIN/LICENSE/REVIEW/SYSTEM 等；未知内部错误统一 SYSTEM，不保存 traceback。
- 所有时间区间检查 `completed_at IS NULL OR completed_at >= started_at`，日期检查 finish >= start。
- WBS `level BETWEEN 1 AND 6`、duration_minutes >= 0、dependency_type='FS'；无环留给 Application/SC-04 属性测试。
- 文件 size_bytes >=0，SHA-256 32 bytes；MIME/Locator 长度受限，路径越界由 Storage Adapter 检查。
- JSONB 只允许预期 object/array，必须有 `schema_version` 或伴随版本列；Secret/ProjectId/状态/核心 FK 禁止仅存在 JSON。

## 核心唯一性矩阵

|语义|唯一键候选|条件|
|---|---|---|
|用户名|`auth_users(username_normalized)`|全部未清除身份；停用不释放用户名|
|Project code|`prj_projects(project_code_normalized)`|部署内唯一|
|单项目成员|`prj_project_members(user_id)`|有效成员；普通用户不能跨项目|
|项目成员重复|`(project_id,user_id)`|有效成员|
|部门代码|`(project_id,department_code_normalized)`|未归档/按业务策略|
|Project Workflow|`wfl_project_workflows(project_id)`|恰好一个|
|Version no|`(parent_id,version_no)`|全部版本|
|一个 Active ReviewRound|`rvw_review_rounds(review_id)`|state=ACTIVE|
|Review assignment|`(review_round_id,reviewer_id)`|每轮每人一次|
|一个 Active SecretVersion|`plt_secret_versions(secret_record_id)`|state=ACTIVE|
|Document Version|`(document_id,version_no)`|全部版本|
|Evidence active binding|`(evidence_id,subject_owner,subject_type,subject_version_id,purpose)`|state=ACTIVE|
|Trace active edge|`(source tuple,target tuple,relation_type)`|state=ACTIVE|
|Job idempotency|`UNIQUE NULLS NOT DISTINCT (owner_module,job_scope,project_id,job_type,idempotency_key)`|全部非清除记录|
|Job lease|`job_leases(job_id)`|state=ACTIVE/未过期由领取逻辑|
|Outbox consumption|`(event_id,consumer_id)`|全部|
|Prompt version|`(prompt_template_id,version_no)`|全部|
|Embedding index version|`UNIQUE NULLS NOT DISTINCT (scope,project_id,index_purpose,index_version)`|全部|
|Active index|`UNIQUE NULLS NOT DISTINCT (scope,project_id,index_purpose)`|state=ACTIVE|
|Embedding record|`(embedding_index_id,chunk_id)`|state=AVAILABLE|
|Survey assignment|`UNIQUE NULLS NOT DISTINCT (survey_round_id,department_id,assignee_id)`|非取消|
|Package membership|`(package_id,member_root_id)`|全部|
|Requirement relation|`(source_version_id,target_version_id,relation_type)`|state=ACTIVE|
|Outline section order|`(outline_version_id,ordinal)`、`(outline_version_id,section_id)`|全部|
|WBS code|`(plan_version_id,wbs_code_normalized)`|全部|
|Plugin package version|`(plugin_id_normalized,plugin_version)`|全部|
|Enabled plugin operation|`(plugin_id_normalized,operation)`|installation state=ENABLED|
|Output idempotency|`(project_id,output_type,input_fingerprint,template_version_id,policy_version)`|进行中/成功 generation|

条件唯一通过 partial unique index 实现，具体名称和谓词在 SC-03 固化；SC-02 先冻结业务语义。

## 多态引用列组与白名单

### 标准列组

```text
<role>_owner_module text
<role>_object_type text
<role>_object_id uuid
<role>_version_id uuid NULL/NOT NULL by use
<role>_project_id uuid NULL
```

列组 CHECK：

- owner_module 必须为 22 个客户模块之一；Developer Workbench 类型禁止。
- `(owner_module, object_type)` 必须属于该表允许白名单，不接受任意字符串。
- 固定版本用途（ReviewRound、EvidenceBinding、Trace 正式链、Output Context）version_id 必填。
- PROJECT 目标 project_id 必填并与拥有 Root 相同；GLOBAL 目标 project_id 为空。

### 使用白名单

|表/用途|允许目标|
|---|---|
|rvw_reviews subject identity|具有 Review 能力的 Capability/Handover/Survey/Requirement/Prototype/Solution/Plan/Document/Config identity|
|rvw_subject_snapshots|上述对象的固定 Version 类型|
|evd_bindings subject|正式化业务 Version、Review/Gate 支持对象；不绑定 Session/Secret/Job|
|trc_links source/target|Document/Capability/Handover/Survey/Requirement/Prototype/Solution/Plan/Output Version/Artifact；安全对象默认禁止|
|aud_events target|65 个客户 Root/必要 child 类型；仅最小摘要|
|job_outbox_events aggregate|产生事件的 Owner Root/Version 白名单|
|ai_tasks accepted target|Handover/Survey/Requirement/Prototype/Solution/Plan Draft Version|

白名单以 Migration 生成 CHECK 常量或受控函数，随 Schema 版本演进；不创建共享 object registry。目标存在性和状态继续由 Owner Port 验证。

## 安全与敏感字段约束

|对象|列规则|
|---|---|
|auth_password_credentials|password_hash text、credential_version bigint、algorithm metadata；禁止 password/plaintext 列|
|auth_sessions|session_token_digest bytea、csrf_digest bytea、credential_version、expires/revoked；禁止原始 Token|
|plt_secret_versions|encrypted_payload bytea、key_provider_ref、nonce/tag/algorithm metadata；主密钥不在库|
|lic_installations|signed payload/document ref + public_key_ref；任何 private_key 列禁止|
|lic_validation_states|machine_fingerprint_hash bytea(32 语义)，不存原始 MAC|
|doc_file_objects|storage_locator 受控相对 Locator、sha256 bytea(32)、size_bytes bigint；不存客户端绝对路径|
|ai_invocations|SecretRef/Provider request ref/受权 payload ref；普通日志字段不复制 Prompt/响应|
|plg_executions|工作区/stdio 不落表；只存脱敏 result refs/error code|
|aud_events|actor/project/object/action/result/摘要；禁止 Secret、正文、Session 标识、密码哈希|

SC-04 增加禁止列名/敏感样例扫描，防止 Migration 意外加入 `api_key`、`private_key`、`password_plain`、`session_token` 等明文字段。

## 数据库写保护与角色边界

- Migration Owner：仅安装/升级时创建/变更 Schema，不作为 API/Worker 运行身份。
- Runtime Role：对所需表执行受控 DML；不得 DDL、修改 Alembic 版本、禁用触发器或改 `search_path`。
- Maintenance/Recovery Role：只在维护模式执行受审清理/恢复；不能由普通请求使用。
- Audit/Append-only 表对 Runtime Role 不授予普通 UPDATE/DELETE；更正写新事件。
- Version/签名包等不可变表通过触发器和列权限候选限制内容更新；Owner 状态命令使用明确函数/事务路径。
- 这些角色不替代模块 Owner；V1 单体运行身份可能访问多表，但代码只能经所属 Repository/Application Port。

## JSONB、Generated Column 与 Domain 决策

- 不创建 PostgreSQL DOMAIN：Domain CHECK 的跨版本演进会同时影响大量列，Alembic 回退复杂；统一字段模板由 Migration 生成器和测试保证。
- 不使用 PostgreSQL ENUM：状态演进和 downgrade 风险高；采用 text + named CHECK。
- Generated column 只用于确定性、同一行、不可变表达式，例如规范化辅助值在确认数据库表达与 Python NFC/case-fold 完全一致后才可使用。用户名规范化首版由 Python 写入并在 DB 唯一，不用数据库 lower() 替代 Unicode case-fold。
- JSONB 只保存版本化快照/低查询扩展；使用 `jsonb_typeof`、schema_version 和最大载荷的 Application 限制。JSON Schema 由 Application 验证，不能宣称 PostgreSQL 原生 CHECK 已验证全部 JSON Schema。

## 约束命名

|对象|格式|
|---|---|
|Primary key|`pk_<table>`|
|Foreign key|`fk_<table>__<column_group>__<target>`|
|Unique|`uq_<table>__<semantic>`|
|Check|`ck_<table>__<semantic>`|
|Trigger|`trg_<table>__<semantic>`|
|Index（SC-03）|`ix_<table>__<semantic>`|

若名称超过 63 bytes，使用稳定缩写 + 8 位语义 Hash，不依赖 PostgreSQL 静默截断。SC-03/04 自动检查全库名称唯一和长度。

## 无法仅靠声明式约束完成的规则

以下必须由 Application Command + 必要 trigger/transaction guard + 测试共同保证：

- target Version 已 APPROVED 且属于 current pointer 的同逻辑对象。
- Version/owned child 在 IN_REVIEW/APPROVED 后不可修改。
- Workflow、Requirement、Trace、WBS 图无非法环。
- 状态迁移合法，终态不复活，取消不伪造回滚。
- Lease 领取、heartbeat、过期回收与 fencing token 防旧 Worker 发布。
- GLOBAL→PROJECT 关系类型、Evidence Eligibility、模板不能证明客户事实。
- Retention 到期、零保护引用、无 Hold、无活动 Job 后才可物理清理。
- 文件系统 Hash/Locator 与数据库 FileObject 的跨资源一致性。

每条规则必须在 SC-04/API 阶段具有绕过 ORM 的数据库级负向测试；不能只测试正常 UI 路径。

## SC-03 输入与索引需求

1. 为全部 PK/FK、复合 Scope FK、current pointer 和唯一语义生成物理索引。
2. 用 partial unique index 实现 Active/Enabled/Available 条件唯一。
3. 为 Project 授权查询统一 `(project_id, state, updated_at/id)` 前缀策略，避免每表随意设计。
4. 为 Job 领取、Lease 回收、Outbox 投递、Retention 扫描定义并发索引与 SKIP LOCKED 查询。
5. 为 Audit/Trace/Evidence/Review 反向查找和保护引用定义索引。
6. 为 RAG pgvector、全文检索、metadata filter、Hybrid/Rerank 候选定义索引和查询计划。
7. 为 WBS/Requirement/Trace 图遍历定义边索引，但无环仍在写入期验证。
8. 验证所有表/约束/索引名称≤63 bytes 且全库唯一。

## 风险与关闭条件

|Risk ID|风险|当前控制|关闭条件|
|---|---|---|---|
|SC2-R01|uuidv7 暴露大致生成时间|ID 不作为 Secret；授权仍按 Project/Resource，外部错误防枚举|API 权限/枚举测试|
|SC2-R02|text + CHECK 状态演进遗漏旧/新值|每表命名 CHECK、Migration 双版本兼容窗口|SC-04 up/down 有数据测试|
|SC2-R03|current pointer Approved 状态不能普通 FK 保证|复合归属 FK + Owner 校验 + deferred constraint trigger 候选|SC-04 直接 SQL 负向测试|
|SC2-R04|多态引用无法目标 FK|白名单/Scope CHECK + Owner Port + Retention 反查|API/SC-04 悬空与跨项目测试|
|SC2-R05|无 RLS 时错误 Repository 查询遗漏 Project filter|ProjectAuthorizationService + 显式列/复合约束 + 查询测试|权限集成与代码审查规则|
|SC2-R06|Version child 仍可能在送审后被直接修改|Parent state guard trigger + Runtime Role 权限 + fingerprint|SC-04 绕过 ORM 测试|
|SC2-R07|JSONB 载荷失控或藏核心字段|核心列禁入 JSON-only、schema_version/type CHECK、应用限额|字段映射扫描 + Schema 测试|
|SC2-R08|NO ACTION 全量显式清理增加运维复杂度|Retention Service 生成依赖序列和预览，不做自动级联|SC-04 清理/回滚验证|

## SC-02 验收

- PostgreSQL 18 `uuidv7()` PK、UTC 时间、版本/计数、Hash、JSONB、文本和向量类型规则明确：PASS。
- M/V/A/R/SEC Profile 覆盖 65 个 Root，未增加、遗漏或合并 Root：PASS。
- PROJECT/GLOBAL_OR_PROJECT 的 ProjectId、Scope CHECK、复合 FK 与 RLS 边界明确：PASS。
- Version/current pointer、内容不可变、Review 锁定和乐观并发约束明确：PASS。
- FK 默认 NO ACTION、NOT DEFERRABLE，V1 不使用跨聚合 CASCADE：PASS。
- 状态采用 text + named CHECK，单行约束与跨行/Application 规则边界明确：PASS。
- 28 组核心唯一语义（含条件唯一）已登记并交接 SC-03：PASS。
- 多态引用标准列组、使用白名单、Scope 规则和无 object_registry 边界明确：PASS。
- Password/Session/Secret/License/File/AI/Plugin/Audit 敏感列规则明确：PASS。
- Migration/Runtime/Maintenance 角色与 Append-only/Version 写保护候选明确：PASS。
- 8 项无法只靠声明约束的规则和 8 项风险均有后续验证位置：PASS。
- 未创建 ORM、Migration、业务表或索引，正式业务编码仍由 Gate 2 阻塞：PASS。

## 下一步

SC-03：根据本文件冻结的字段与唯一语义，设计 PK/FK/授权查询、条件唯一、Job/Outbox、Audit/Trace、Retention、全文检索和 pgvector 索引及关键查询计划。
