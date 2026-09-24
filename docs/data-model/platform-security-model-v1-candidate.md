# 平台与安全数据模型 V1 候选

## 状态

`GATE_2_FROZEN_AT_64cdf09 / AMENDED_BY_CR-LIC-001 / NOT_PHYSICAL_SCHEMA`

本文件细化 Platform、Auth、Project、Workflow、Review、Audit、Secret 与 License 的实体关系、字段语义、状态机和不变量。字段名称表示领域语义，不代表 PostgreSQL 列名或 API DTO；类型、长度、索引、物理外键和 Migration 留待 Database Schema V1。

## 设计结论

1. `auth.User` 只负责部署身份和凭据；项目身份由 `project.ProjectMember` 独立拥有。
2. Deployment Role 与 Project Role 分离：`DeploymentAdmin` 是部署级角色，四个项目角色只存在于 ProjectMember。
3. 当前项目阶段只由 `workflow.ProjectWorkflow` 拥有；Project 不保存可写 `current_stage` 副本。
4. Review 是逻辑评审流；每个 ReviewRound 绑定一个不可变 Subject Version。送审锁锁定逻辑主题，退回修改创建新版本和新 Round。
5. Secret 查询永不返回明文；SecretRecord 只通过 `secret_ref` 被使用，解密限于授权 Adapter 的单次调用。
6. License 私钥不属于客户数据模型；客户侧只保存签名 License、公钥引用、机器指纹 Hash、验证结果和可信时间状态。
7. AuditEvent 是追加式安全/业务记录，不作为其他聚合的事务真相来源，也不允许普通业务删除或改写。

## Identity 与认证

### User Aggregate

|语义字段|要求|
|---|---|
|user_id|稳定部署级身份；不复用已删除/停用 ID|
|username_display|供界面显示的用户名|
|username_canonical|用于部署内唯一性；trim + Unicode NFC + invariant case-fold|
|account_state|`ENABLED / DISABLED`|
|deployment_role|`NONE / DEPLOYMENT_ADMIN`|
|credential_version|凭据变化时单调增加，用于 Session 失效|
|created_at / updated_at|UTC 领域时间语义|

`PasswordCredential` 作为 User 内部实体，包含 password_hash、algorithm_id、parameter_set、changed_at 和 credential_version。不得保存明文、可逆密码、密码提示或原始登录输入。

不变量：

- username_canonical 在部署内唯一；显示值变化不得绕过唯一性。
- User 只能有一个有效 PasswordCredential；换密创建新凭据版本并使旧 credential_version 的 Session 失效。
- `DISABLED` 用户不能创建 Session，现有 Session 全部撤销。
- DeploymentAdmin 不等于免认证主体，不能绕过 License、Session、对象状态和 Audit。

### Session Aggregate

|语义字段|要求|
|---|---|
|session_id|服务端记录标识，不作为浏览器 Bearer 值|
|session_token_hash|只保存 Cookie 中不透明 Token 的不可逆摘要|
|user_id|必须指向 ENABLED User|
|credential_version|创建 Session 时的凭据版本|
|csrf_binding_hash|绑定该 Session 的 CSRF 材料摘要|
|created_at / last_seen_at|UTC；last_seen 只能前移|
|absolute_expires_at / idle_expires_at|任一到期即失效|
|revoked_at / revoke_reason|撤销后不可恢复|

状态由时间和撤销事实派生为 `ACTIVE / EXPIRED / REVOKED`，不允许客户端写状态。

不变量：

- 原始 Session Token 和 CSRF Token 不持久化、不写日志、不进入 Audit。
- 登录成功后生成新 Session；权限提升或认证边界变化必须轮换 Token。
- User 被停用、密码变更、管理员撤销或绝对/空闲超时后，Session 失败关闭。
- Session 只证明身份，不携带可长期缓存的项目授权快照；每次 PROJECT 操作重新查询 ProjectAuthorizationService。

## Project、成员与角色

### Project Aggregate

|语义字段|要求|
|---|---|
|project_id|稳定项目身份|
|project_code|部署内唯一、不可静默复用|
|name|项目显示名称|
|project_state|`ACTIVE / ARCHIVED`|
|created_by / created_at|DeploymentAdmin 与 UTC 时间|

Project 不保存 `current_stage`。阶段与 Gate 由 ProjectWorkflow 唯一拥有，通过 WorkflowService 查询。

状态规则：

```text
ACTIVE → ARCHIVED
```

- Archived Project 禁止新建/修改业务对象、成员和 Job，只允许受权只读、审计、导出和恢复流程。
- V1 不定义普通业务“反归档”；如 Release 前需要，必须增加受控命令、理由和 Audit，不得直接改状态。

### ProjectMember Aggregate

|语义字段|要求|
|---|---|
|project_member_id|稳定成员身份|
|project_id / user_id|必须同时存在，且成员 Scope 等于 Project|
|project_role|`PROJECT_MANAGER / IMPLEMENTATION_MEMBER / CUSTOMER_MANAGER / CUSTOMER_MEMBER`|
|department_id|必须属于同一 Project|
|membership_state|`ACTIVE / SUSPENDED / REMOVED`|
|effective_at / ended_at|成员有效期语义|

`RoleAssignment` 是 ProjectMember 内的当前角色及变更历史值对象/实体，不单独形成跨模块可写聚合。

不变量：

- 一个 User 同时最多有一个未 REMOVED 的 ProjectMember，满足普通用户只属于一个项目。
- 一个 ProjectMember 同时只有一个 Project Role 和一个 Department。
- DeploymentAdmin 的部署级能力与 ProjectMember 独立；Admin 可无项目成员记录。执行项目操作时仍按动作策略授权并审计。
- `SUSPENDED` 成员不能执行项目业务操作，但历史引用保留；`REMOVED` 不物理删除。
- 角色、部门和成员状态变化立即影响后续授权，不复制进 Session。

### Department Aggregate

|语义字段|要求|
|---|---|
|department_id / project_id|部门只属于一个 Project|
|department_code / name|code 在项目内唯一|
|department_state|`ACTIVE / INACTIVE`|

Department 停用前必须保证没有 ACTIVE/SUSPENDED ProjectMember 继续引用，或在同一受控命令中完成迁移。

### 权限判定关系

```text
User + active Session
  ├─ deployment_role → DeploymentAdmin policy
  └─ ProjectMember(project_id, role, department, state)
       → ProjectAuthorizationService(resource owner + action)
```

- Client 提供的 project_id 只作为定位输入，最终 ProjectId 必须从目标资源归属反查并交叉校验。
- 普通用户的“资源不存在”和“无权限”使用相同外部语义；Audit 保留内部原因。
- SystemActor 必须包含 actor_type、system_purpose、original_actor_id、project_id 和 trace_id；不能作为跨项目通配符。

## Workflow 与 Gate

### ProjectWorkflow Aggregate

|语义字段|要求|
|---|---|
|workflow_id / project_id|一个 Project 恰有一个当前 Workflow|
|workflow_version|Workflow 定义变更时增加|
|workflow_state|`NOT_STARTED / ACTIVE / COMPLETED`|
|current_stage_key|只由合法 StageTransition 更新|
|lock_version|乐观并发语义|

`Stage` 包含 stage_key、order、state 和 GatePolicy；`StageChecklist` 包含 ChecklistItem、required 标记、EvidencePolicy、ReviewPolicy 和状态。

候选状态：

- Stage：`NOT_STARTED / ACTIVE / BLOCKED / COMPLETED`。
- ChecklistItem：`PENDING / PASS / FAIL / WAIVED`。
- `WAIVED` 必须记录受权 actor、理由、影响和依据；不得用 Waiver 把 POC-03 质量指标改写为通过。

不变量：

- 同一 Workflow 最多一个 ACTIVE Stage；current_stage_key 与 ACTIVE Stage 一致。
- Stage 完成前，全部 required ChecklistItem 必须 PASS 或具备已批准 Waiver。
- GatePolicy 只引用 EvidenceRef、ReviewStatusRef、质量结果或明确例外 ID，不复制正文。
- Workflow 不直接修改 Review/Evidence；通过公开 Query/Application Port 读取状态。

### StageTransition Aggregate

StageTransition 是追加式记录，至少表达 workflow_id、from_stage、to_stage、transition_type、actor_ref、reason、gate_snapshot_ref、occurred_at 和 trace_id。

不变量：

- from_stage 必须等于事务开始时的 current_stage；expected_version 不匹配则拒绝。
- 非法跳级、缺少 Gate 证据或目标 Project 已归档时拒绝。
- 失败尝试写 Audit，但不创建成功 StageTransition。
- 已提交 Transition 不修改；纠正通过后续受控 Transition 表达。

## Review 与锁定

### Review Aggregate

|语义字段|要求|
|---|---|
|review_id / scope / project_id|逻辑评审流身份；PROJECT 时 project_id 必填，GLOBAL 时显式为空|
|subject_identity_ref|目标 Domain 的逻辑对象，不指向可变正文|
|review_policy|发起角色、处理人数与允许决定|
|review_state|`DRAFT / IN_REVIEW / APPROVED / RETURNED / WITHDRAWN`|
|active_round_id|IN_REVIEW 时恰有一个|
|lock_version|并发控制|

Review 绑定一个逻辑主题身份；每个 ReviewRound 绑定该主题的一个不可变 Version。这样允许退回后升版并在同一逻辑评审流中开启下一 Round。Review 的 Scope 必须与 Subject Scope 一致；GLOBAL 评审当前只允许明确的 DeploymentAdmin 策略，不能借用任意项目角色。

### ReviewRound Aggregate

|语义字段|要求|
|---|---|
|review_round_id / review_id|Round 只属于一个 Review|
|round_no|在 Review 内从 1 单调增加|
|review_subject_version_ref|本轮唯一不可变主题版本，对应 DM-01 的 ReviewSubjectVersionRef|
|started_by / started_at|必须由 ProjectManager 或明确全局 Owner 发起|
|round_state|`PENDING / IN_REVIEW / APPROVED / RETURNED / WITHDRAWN`|

`ReviewAssignment` 绑定 reviewer_id，状态为 `PENDING / DECIDED`；`ReviewDecision` 为 `APPROVE / RETURN`，并记录 decided_at 和 comment。

不变量：

- ReviewerSet 为 1～N 个互不重复、对该 PROJECT/GLOBAL 主题有资格的主体。
- 所有 Assignment 都 DECIDED 后才汇总；任一 `RETURN` 则 Round=`RETURNED`，否则 `APPROVED`。
- `RETURN` 的 comment 必填且必须有实质内容；APPROVE comment 可选。
- 一个 Reviewer 每轮只能形成一个最终 Decision；更正通过撤回/新 Round，不能覆盖旧决定。
- Round=`IN_REVIEW` 时，ReviewService 对 subject_identity_ref 建立锁；目标 Owner 不得修改该 Version 或创建替代 Draft。
- Returned 后修改创建新 Domain Version 和新 ReviewRound；不得复用旧 version 或旧 Assignment。
- ReviewCompleted 只授权主题 Owner 更新 current approved version；Review 模块不直接写业务表。

## Config 与 Secret

### SystemConfiguration Aggregate

|语义字段|要求|
|---|---|
|config_key|部署内唯一，命名空间化|
|value_type / value|仅允许非敏感值|
|config_version|修改时单调增加|
|config_state|`ACTIVE / INACTIVE`|
|changed_by / changed_at|必须审计|

Secret、密码、Token、License 私钥和客户正文不得存入 SystemConfiguration。

### SecretRecord Aggregate

|语义字段|要求|
|---|---|
|secret_id / purpose|稳定标识与限定用途|
|secret_state|`ACTIVE / DISABLED / RETIRED`|
|current_version_ref|最多一个 ACTIVE SecretVersion|
|allowed_consumer|受控 Adapter/Integration 能力标识|

`SecretVersion` 表达 version_no、encrypted_payload、encryption_metadata、key_provider_ref、created_by、created_at、activated_at 和 retired_at。

不变量：

- 数据库只保存密文、算法/版本元数据和外部 key reference；加密主材料不在同一数据库、YAML、Git 或日志。
- 创建/轮换 Secret 产生新 Version；旧 Version 先 Retired 后才能销毁，历史使用只保留版本引用和审计，不保留明文。
- 业务、Job、Event、Audit 与 Plugin 只持 SecretRef；只有 allowed_consumer 在单次调用内解密。
- 查询、列表、错误和 Audit 不返回 encrypted_payload 全文，更不返回明文。
- Secret 解密失败、用途不匹配或 Record Disabled 时失败关闭，不回退到环境中的同名明文变量。

## License 与可信时间

### LicenseInstallation Aggregate

|语义字段|要求|
|---|---|
|license_installation_id|每次导入生成新记录|
|license_document|版本化确定性 Payload + Ed25519 Signature|
|public_key_ref|客户侧验签公钥引用|
|imported_by / imported_at|必须为已认证 DeploymentAdmin|
|installation_state|`IMPORTED / ACTIVE / SUPERSEDED / REJECTED`|
|validation_result_ref|指向对应验证事实|

不变量：

- 私钥不属于任何客户运行聚合或字段。
- 导入失败仍保留脱敏验证结果和 Audit，但无效 License 不成为 ACTIVE。
- 同一时间最多一个 ACTIVE LicenseInstallation；新 License 激活后旧记录变为 SUPERSEDED，不覆盖。

### LicenseValidationState Aggregate

|语义字段|要求|
|---|---|
|active_license_ref|可为空，指向当前 Active 安装|
|machine_fingerprint_hash|只保存规范化 MAC 的 SHA-256，不保存原始 MAC|
|validation_code|分类安全结果|
|entitlement_snapshot|CR-LIC-001 后只保存本产品全功能整体授权的最小派生状态与有效期；不承载按产品/功能区分的权益|
|validated_at|UTC 验证时间|

validation_code 至少区分：`VALID / NOT_INSTALLED / MALFORMED / SIGNATURE_INVALID / MACHINE_MISMATCH / NOT_YET_VALID / EXPIRED / TIME_ROLLBACK`。

不变量：

- 只有受信任的本产品专用公钥引用、签名、Schema、机器、有效期和可信时间全部通过时为 VALID；不执行七字段载荷无法支持的细分产品/功能权益验证（CR-LIC-001）。
- 验证结果不能由客户端提交；由 LicenseService 根据签名材料和 TrustedTimeState 计算。
- 无效状态只允许最小存活、登录和已认证 DeploymentAdmin 的 License 恢复面，其他许可业务失败关闭。

### TrustedTimeState Aggregate

|语义字段|要求|
|---|---|
|trusted_time_state_id|部署级单例身份|
|last_successful_time|最近一次成功许可验证的 UTC 时间|
|state_version|每次成功前移时增加|
|integrity_metadata|由 TrustedTimeStatePort 生成/校验，不在本阶段固定算法|
|updated_at|UTC；不得早于 last_successful_time 的业务语义|

不变量：

- 更新使用 expected_version 原子比较，last_successful_time 只能前移。
- 当前系统时间低于策略允许的回拨边界时，License=`TIME_ROLLBACK`，状态不向后写。
- 状态损坏、完整性失败或并发冲突时失败关闭并 Audit。
- TrustedTimeState 不是在线授时证明；V1 不引入网络时间服务依赖或可信硬件要求。

## Audit 模型

### AuditEvent Aggregate

|语义字段|要求|
|---|---|
|audit_event_id|全局唯一、不可复用|
|occurred_at|服务端 UTC 事件时间|
|actor_ref|User 或 SystemActor；SystemActor 保留 original_actor_id|
|project_id|PROJECT 操作必填；部署操作显式为空|
|action / outcome|受控动作与 SUCCESS/DENIED/FAILED|
|object_ref / object_version_ref|最小稳定引用|
|before_after_summary|只含关键状态，不含正文/Secret|
|trace_id|贯穿请求、Job、Provider 和 Plugin|

不变量：

- AuditEvent 为 Append-only；只有 AuditService 可追加，无普通 Update/Delete Command。
- 登录失败等无法解析 User 的事件使用安全的主体提示摘要，不保存密码、Token 或完整输入。
- AuditEvent 不能替代目标聚合状态；业务重放不得仅依赖 Audit。
- Secret 明文、密码 Hash、Session Token/Hash、CSRF、文件正文、完整 Prompt/响应和 License 私钥禁止进入 Audit。
- 导出 Audit 仍需 DeploymentAdmin/项目权限、用途和范围审计；保留期与归档在 DM-06/Release 设计中明确。

## 关系与基数

|关系|基数|约束|
|---|---|---|
|User → Session|1 : 0..N|同一 User 可多会话；CredentialVersion/停用统一失效|
|User → active ProjectMember|1 : 0..1|满足普通用户只属于一个项目；历史 Removed 记录可多条但不能同时有效|
|Project → ProjectMember|1 : 0..N|Member.project_id 必须一致|
|Project → Department|1 : 0..N|Department Code 项目内唯一|
|Department → active ProjectMember|1 : 0..N|成员部门与项目一致|
|Project → ProjectWorkflow|1 : 1|Workflow 唯一拥有 current stage|
|ProjectWorkflow → Stage/Checklist|1 : 1..N|定义版本内有序且 key 唯一|
|ProjectWorkflow → StageTransition|1 : 0..N|Transition 追加式|
|Review → ReviewRound|1 : 1..N|round_no 单调，最多一个 Active|
|ReviewRound → ReviewAssignment|1 : 1..N|reviewer 唯一|
|ReviewAssignment → ReviewDecision|1 : 0..1|决定不可覆盖|
|SecretRecord → SecretVersion|1 : 1..N|最多一个 Active Version|
|LicenseInstallation → ValidationResult|1 : 1..N|导入与后续验证均可追加记录|
|Deployment → active LicenseInstallation|1 : 0..1|最多一个 Active|
|Deployment → TrustedTimeState|1 : 1|初始化后单例、原子前移|
|任意强制审计命令 → AuditEvent|1 : 1..N|状态改变与 Audit 在同一事务边界提交|

## 状态转换摘要

|Aggregate|允许转换|禁止示例|
|---|---|---|
|User|ENABLED ↔ DISABLED（受权命令）|客户端直接写状态|
|Session|ACTIVE → REVOKED；ACTIVE → EXPIRED（派生）|REVOKED → ACTIVE|
|Project|ACTIVE → ARCHIVED|普通命令 ARCHIVED → ACTIVE|
|ProjectMember|ACTIVE ↔ SUSPENDED；ACTIVE/SUSPENDED → REMOVED|REMOVED → ACTIVE|
|Workflow|NOT_STARTED → ACTIVE → COMPLETED|无 Gate 跳级|
|ChecklistItem|PENDING → PASS/FAIL/WAIVED|无理由 WAIVED|
|ReviewRound|PENDING → IN_REVIEW → APPROVED/RETURNED；IN_REVIEW → WITHDRAWN|终态覆盖 Decision|
|SecretVersion|CREATED → ACTIVE → RETIRED|RETIRED → ACTIVE|
|LicenseInstallation|IMPORTED → ACTIVE/REJECTED；ACTIVE → SUPERSEDED|REJECTED → ACTIVE|
|TrustedTimeState|时间与版本单调前移|写入更早成功时间|

## 失败关闭规则

- username canonical 冲突、User Disabled、Session 过期/撤销/credential_version 不符。
- project_id 与资源 Owner 不一致、成员非 ACTIVE、Role/Department 不属于项目。
- Stage Gate 缺少必需 Evidence/Review、expected_version 冲突或项目已 Archived。
- Review 无处理人、Reviewer 越权、退回无意见、主题版本变化或主题被锁。
- Secret 用途不匹配、主材料不可用、解密失败或访问主体不是 allowed_consumer。
- License 签名/Schema/机器/时间失败、原始 MAC 与持久 Hash 规则不一致、可信时间倒退。
- 强制审计命令无法形成最小 Audit 上下文。

失败关闭不得通过“管理员”“系统任务”或“稍后补审计”绕过；只允许架构中明确的 License 恢复面。

## 与 DM-01 的边界修正

1. `PRJ-01 Project` 不再包含 CurrentStageRef；当前阶段由 `WFL-01 ProjectWorkflow.current_stage_key` 唯一拥有，避免 project → workflow 反向依赖。
2. `RVW-01 Review` 绑定 Subject Identity；`RVW-02 ReviewRound` 绑定具体不可变 Subject Version，支持升版重审且保留同一逻辑评审流。

上述修正不改变 Aggregate Root 数量、技术栈或业务 Scope。

## 延后事项

- PostgreSQL 类型、长度、唯一/检查约束、索引和物理外键：Schema V1。
- Cookie 名、CSRF Header 名、Session TTL、锁定阈值和限速参数：API/基础工程安全配置。
- 密码 Hash 具体算法参数、Secret 加密算法和 SecretKeyProvider 平台实现：基础工程/Release 安全设计，须满足本模型语义。
- Workflow 的正式阶段清单和每个 Gate Checklist：业务配置/Workflow 设计，不在数据模型中硬编码。
- Audit 保留期、归档介质和受权导出格式：DM-06/Release。

## DM-02 验收

- User、PasswordCredential、Session 的身份、凭据版本和失效语义完整：PASS。
- DeploymentAdmin 与四个 Project Role 分离，单项目/单角色/单部门规则完整：PASS。
- Project 与 Workflow 阶段所有权无重复，Gate/Transition 追加与并发规则完整：PASS。
- Review Identity、Round Version、1～N Reviewer、锁定、退回和升版重审语义完整：PASS。
- SystemConfiguration 与 SecretRecord 分离，SecretRef、轮换和单次解密边界完整：PASS。
- License、MAC Hash、Ed25519 客户侧验签和 TrustedTime 单调状态未改变：PASS。
- AuditEvent 追加、脱敏、Actor/Project/Trace 与不可删除边界完整：PASS。
- 未定义物理 Schema、REST Contract 或正式业务代码，未触发 L3 变更：PASS。

## 下一步

DM-03：Document、FileObject、ParseRecord、Evidence、Trace 与版本保留数据模型。
