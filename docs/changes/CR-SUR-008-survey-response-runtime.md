# CR-SUR-008：Survey Assignment/Response 运行时与 Round 完整性边界

日期：2026-10-06。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09`、SRV-04 Root、四张物理表、五态枚举和七个 Assignment/Response Operation 均保留；本 CR 只补齐冻结基线未定义的物理字段、状态细节和 Owner 事务边界，不表示任何客户答复、客户确认、Round 完成、Gate 3 或 UAT 已通过。

## 来源与冲突

冻结基线规定 `srv_assignments`、`srv_responses`、`srv_answers`、`srv_answer_evidence_refs`，以及 `ASSIGNED/IN_PROGRESS/SUBMITTED/VALIDATED/RETURNED`、追加式更正、`FACILITATED_RECORD` 和 `UNIQUE NULLS NOT DISTINCT` 的 Round target；但没有固定以下实现要素：部门级 Assignment 的可空受访人语义、Response 与 Answer 的一对一边界、结构化值存储、RETURNED 后如何更正重提、条件题/必答/Evidence 的权威计算、面对面记录如何与 Round source 原子关联，以及 CLOSE 如何拒绝空 Assignment 集。

当前 Alembic head `20261006_0107` 只到 SRV-03；仓库没有四张 SRV-04 表、Owner、Router 或页面。直接把 PROJECT_RECORD 当 Answer、覆盖旧答复、让客户端上送“完整”布尔值，或把空 Assignment 集视为完整，都会伪造业务事实。一次性实现 Schema、七个命令、HTTP 和 UI 又会跨越多个独立问题。

## 选择

### Assignment Root

- `srv_assignments` 固定 Round/Survey/SurveyVersion/Project、目标 `department_id`、可空 `assignee_user_id`、状态/生命周期 actor-time、最近退回意见、创建更新事实和强 `lock_version`。
- `department_id` 必须是固定 SurveyVersion 的 target department；非空 assignee 必须是该项目、该部门的当前有效成员。空 assignee 表示部门级 Assignment，不表示匿名或无需答复。
- 以 `(survey_round_id, department_id, assignee_user_id) NULLS NOT DISTINCT` 保证同一 Round target 全历史唯一。Assignment 只可在 OPEN Round 创建；CLOSED/CANCELLED 拒绝新建和新答复。
- 读取/录入主体每次重新验证：显式 assignee 仅本人；部门级 Assignment 为该部门当前有效成员；ProjectManager/ImplementationMember 按冻结 Operation 角色执行管理或受权录入。不得只信创建时角色快照。

### Response、Answer 与 Evidence

- 一个 `srv_responses` 是一次针对单个固定 Question 的追加式回答事实；它固定 Assignment/Round/Version/Question、`response_source`、记录人/时间、可空 `correction_of_response_id`，并拥有且仅拥有一个 `srv_answers` typed/raw value。
- V1 `response_source` 只允许 `SELF_SERVICE`、`FACILITATED_RECORD`。`SELF_SERVICE` 只能由当前受访主体产生；`FACILITATED_RECORD` 只能由受权 ImplementationMember 录入，并必须在同一事务调用 Round source append Owner，固定返回的 PROJECT_RECORD source ref。原始记录不能自行成为结构化 Answer。
- 每个 Assignment/Question 只允许一个无前驱根 Response；每个旧 Response 最多一个直接更正后继，后继必须属于同一 Assignment/Question。Response、Answer、Evidence ref 均不可 UPDATE/DELETE/TRUNCATE；当前有效回答由唯一无后继链尾计算，不能覆盖历史。
- `srv_answers` 使用受控 JSON typed value 与可空 raw answer；类型必须按固定 Question 的 `TEXT/SINGLE_CHOICE/MULTIPLE_CHOICE/DATE/NUMBER/ATTACHMENT` 解释，Choice 只能引用固定选项。`srv_answer_evidence_refs` 固定 PROJECT Evidence 的 DocumentVersion、观测 lock/fingerprint、记录序号；`evidence_required` 与 ATTACHMENT 不能由客户端布尔值满足。

### 状态与完整性

- 首次 Response 使 `ASSIGNED -> IN_PROGRESS`；后续追加保持 IN_PROGRESS。`IN_PROGRESS -> SUBMITTED -> VALIDATED`；`SUBMITTED -> RETURNED`；RETURNED 追加更正后进入 IN_PROGRESS，再次 SUBMIT。VALIDATED 为 Assignment 终态，不能追加或返回。
- SUBMIT 在同一事务锁定 Assignment、固定 Version Questions/Options、全部 Response/Answer/Evidence，计算条件题、必答、类型、ValidationRule、EvidenceRequired 和更正链；缺失或非法时返回冻结错误，不能写 SUBMITTED。
- VALIDATE/RETURN 只接受 SUBMITTED。RETURN 保存受控意见并保留所有历史；VALIDATE 必须重新复算当前完整性，避免提交后 Evidence 失效或来源漂移。
- Round completeness Owner 必须证明：Round 为 OPEN；至少存在一个 Assignment；固定 SurveyVersion 的每个 target department 至少有一个 Assignment；所有 Assignment 均为 VALIDATED；每个 Assignment 的当前回答仍满足条件、必答、类型、ValidationRule、Evidence 和 facilitated source。任一空集、RETURNED/非终态、漂移或冲突均失败关闭。
- Round CLOSE 在同一调用方事务先锁 Round，再按稳定顺序锁 Assignment/Response/Evidence 并调用 completeness Owner，保存确定性的完整性报告 fingerprint 后原子关闭。不得让客户端上传报告、PASS 或计数。

## 实施拆分

1. `SUR-03-A01`：本 CR、冻结基线/现状核查和任务拆分。
2. `SUR-03-A02`：四表 ORM 与 Migration `20261006_0108`；完成 up/down、空库/有数据、drift、唯一、更正链、不可变和历史拒降。
3. `SUR-03-A03`：Assignment create/list/get、目标与当前角色 Owner、授权/Audit/幂等和稳定 cursor。
4. `SUR-03-A04`：Response/Answer/Evidence 追加 Owner；类型值、固定 Evidence 与 facilitated Round source 同事务。
5. `SUR-03-A05`：SUBMIT 当前回答/条件/必答/ValidationRule/Evidence 完整性 Owner。
6. `SUR-03-A06`：VALIDATE/RETURN、退回更正重提和状态全矩阵。
7. `SUR-03-A07`：Round completeness caller-transaction Owner 与真实 PostgreSQL 漂移/并发验证。
8. `SUR-02-A06`：在 A07 证明后接通 Round CLOSE 与七个 Round HTTP；随后按 `SUR-03-A08/A09` 接 Assignment/Response HTTP、Windows 组合、前端和真实浏览器。若冻结请求无法无损表达 typed value、Evidence 或退回意见，先登记独立 API Change Request，不静默猜测 JSON。

## 迁移、兼容、回滚与验证

0108 只新增冻结已有的四张 SRV-04 表，不修改 SRV-01～03、现有 `/api/v1` JSON、技术栈、依赖或 Scope。空历史可降至0107；存在 Assignment/Response/Answer/Evidence、相关 Audit/receipt 或已关闭 Round 历史时拒绝物理降级，只允许向前修复或恢复备份。应用回滚可停止 Owner/Router 注入，但不得删除答复历史。

验证至少覆盖：部门/assignee唯一、跨项目/部门/撤权、Round状态、强ETag、同Key并发、Audit/receipt回滚、六种 answer type、固定选项、条件题、必答/Evidence、单根单后继更正链、RETURNED更正重提、VALIDATED终态、PROJECT_RECORD来源同事务回滚、Evidence版本/指纹漂移、空Assignment与缺目标部门拒绝CLOSE，以及历史拒降。Windows 11/PostgreSQL 18.6 为当前实际环境；Windows Server 2025 留发行复验，Debian 13 按用户指令跳过实机但仍保持正式兼容目标。

## 实施记录

- 2026-10-06 / `SUR-03-A02`：完成四表 ORM 与 Migration0108，数据库强制OPEN Round/固定target、NULLS NOT DISTINCT、单根单后继更正、一Response一Answer、facilitated source、Evidence快照、不可变及历史拒降。Windows 11/PostgreSQL18.6、后端全量和wheel通过；多表触发器字段分支及head/inventory断言偏差已修复并重跑，详见`docs/progress/sur-03-a02-response-schema.md`。
- 2026-10-06 / `SUR-03-A03`：完成Assignment create/list/get、当前target/assignee证明、管理角色全量与显式assignee/部门成员动态可见性、稳定cursor、Audit和持久幂等。Windows 11/PostgreSQL18.6的并发、回滚、撤权、隔离与drift通过，详见`docs/progress/sur-03-a03-assignment-owner.md`。
- 2026-10-06 / `SUR-03-A04`：完成Response/Answer/Evidence原子追加、六类型基础规范、更正链、固定Evidence及ImplementationMember面对面代录与Round PROJECT_RECORD source同事务固定；Windows 11/PostgreSQL18.6的并发幂等、Audit整笔回滚、授权/CSRF/License及drift通过，详见`docs/progress/sur-03-a04-response-record.md`。
- 2026-10-06 / `SUR-03-A05`：完成Assignment SUBMIT当前回答完整性Owner；ConditionRule、required、六类型ValidationRule、EvidenceRequired/漂移和facilitated来源均在同事务失败关闭。为执行附件`allowed_extensions`，内部Document/Evidence固定证明透传原始显示名，不改公开API/Schema，详见`docs/progress/sur-03-a05-assignment-submit.md`。
- 2026-10-06 / `SUR-03-A06`：完成VALIDATE/RETURN、人工退回意见与RETURNED追加更正后重新SUBMIT/VALIDATE状态闭环；VALIDATE重新执行A05完整性。首轮角色集合偏差已按冻结PM+Implementation修正并重跑，详见`docs/progress/sur-03-a06-assignment-review.md`。
- 2026-10-06 / `SUR-03-A07`：完成caller-transaction Round完整性Owner；非空Assignment、全部目标部门覆盖、全VALIDATED及当前Answer/Evidence重证后生成稳定报告指纹，不自行commit。Windows 11/PostgreSQL18.6锁、空集/非终态/漂移拒绝通过，详见`docs/progress/sur-03-a07-round-completeness.md`。
