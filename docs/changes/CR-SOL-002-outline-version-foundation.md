# CR-SOL-002：SolutionOutlineVersion 分层持久化与来源闭锁

日期：2026-10-08；状态：依据 CR-EXEC-001 持续授权先记录后实施；Gate 2 冻结提交 `64cdf09` 保留。TraceLink：CR-SEQ-001 → SOL-01-A02/CR-SOL-001 → 本 CR → SOL-01-A03-P01。

## 来源与冲突

冻结 DM-05/SC-01/02 要求 SOL-03 不可变目录版本：固定章节顺序、需求版本、参考方案版本、缺失/冲突声明与独立 Review。A02 已建立 Outline/Section 身份，但尚无版本表。当前 SOL-01 ReferenceSolution 及其 Version 未实现，不能给 `sol_outline_reference_refs` 建立真实目标外键或受权来源证明；直接填裸 UUID 会留下跨项目/撤权漏洞。严格等所有 SOL-01 才建任何目录版本，会延迟已经可由现有 Section/Requirement 证明的结构基础。

## 方案比较与选择

- 不选一次性实现参考/目录/章节/专项/全部 API：会跨多个 Owner 与 Review 边界，难以证明当前性与权限。
- 不选在 ReferenceSolution 表缺席时存无外键、可写的参考 UUID：会把未知参考当固定来源。
- 选择先实施 `SOL-01-A03-P01`：`sol_outline_versions`、有序 `sol_outline_sections`、固定 `sol_outline_requirement_refs`，对现有 Section/Requirement 使用同项目复合外键；Outline 的批准指针补同身份复合 FK。参考方案关联留待 SOL-01 身份/版本落地后单独增量；当前 DML 全拒，不能创建不完整正式版本。缺失/冲突声明以 JSONB 数组保存，业务结构校验留给后续 Owner。此为施工顺序与逐列约束细化，不减少冻结产品功能或改写 API。

## 影响、迁移、回滚与验证

- `20261008_0137` 在 0136 后新建三个空表并为 `sol_sections` 增加 `(section_id,outline_id,project_id)` 唯一键；无旧 Solution 数据转移，不修改其他模块表/正式 API/权限/依赖。版本根含 SHA-256 指纹、同 Outline 版本号唯一、同父版本替代 FK、独立 Review 引用与固定声明。未装配 Owner 的写入及 TRUNCATE 失败关闭。
- 空库与已有 Project/User 的库升级、Schema drift、空表降级重升及已有版本历史拒降均需验证；若后续有记录，不得通过降级删除。回滚本阶段只适用于三表无记录；保留 A02 身份数据。
- PostgreSQL 18 必测同项目 Section/Requirement FK、跨项目拒绝、顺序唯一、重复目标、无效声明/指纹、未装配写入口、批准指针跨 Outline 拒绝；后端全量回归。未形成 ReferenceSolution/SectionVersion/Review/Workflow 事实前，Gate 3 仍 OPEN。

## SOL-03-A02：参考版本关联前向补齐计划（实施前）

2026-10-09 复核：SOL-04 Section 身份已形成可验证真实 Owner，REQ-01 有当前 APPROVED RequirementVersion 证明端口，SOL-01-A16 双 Scope Reference 资格/修订失效及 Win11 Edge/PG 合成链已验。0137 的 `sol_outline_versions`、章节和需求引用仍由写 Guard 全拒；`sol_outline_reference_refs` 仍不存在。因此前述“等待 SOL-01 后再补参考关联”的前置已满足到可安全设计 Schema，但不等于 OutlineVersion CREATE 可直接开放。

选择后续独立线性迁移先补封闭结构：新增 `sol_outline_reference_refs`，固定 OutlineVersion/Outline/Project、ReferenceVersion/ReferenceRoot/Scope、序号，版本内序号和目标唯一；PROJECT 来源须同目标 Project，GLOBAL 来源须无来源 Project。对现有 ReferenceVersion 增加用于 PROJECT 复合归属 FK 的唯一键，并同时保留 `(ReferenceVersion,Root,Scope)` 基础 FK 覆盖 GLOBAL；新表 `INSERT/UPDATE/DELETE/TRUNCATE` 默认全拒。OutlineVersion 增 `declared_reference_count >= 0`（既有版本初值 0），但不凭计数字段单独证明引用闭合。此增量不解锁旧 0137 Guard，也不新增默认 HTTP。当前版本、`ELIGIBLE` 状态、Document/Evidence/脱敏确认现时性及 Project 授权仍必须由之后独立 Owner 在同事务证明；数据库 FK 只证明固定身份/归属，不证明资格。

不选裸 UUID、仅前端过滤或直接开放 0137 DML。迁移先验空库/已有 Project、Section、Reference 根与版本的升级；有新参考关联历史时拒降并保留数据，空历史 down 后重升；Drift、跨项目/伪 GLOBAL、错 Root/Version、序号重复、直接 DML/TRUNCATE 负例必须通过。回滚优先保持写入口关闭，不能静默删除业务历史。若实现中发现复合 FK 对 GLOBAL NULL 语义与此计划不闭合，先追加本 CR 的差异与可验证替代，不放宽 Scope；Gate2 原冻结提交和 0137 历史保留。此计划不变更冻结 `/api/v1` 合同或产品授权边界。

## SOL-03-A03：封闭结构实施记录

2026-10-09 以线性 `0154` 完成上述结构：基础三元 FK 在 GLOBAL 的 nullable Project 情况下仍验证目标版本/根/Scope，PROJECT 四元 FK 加同 Project CHECK 验证归属；新表沿用 0137 Owner/截断拒绝。空/既有版本行升降重升、Alembic drift、双 Scope 正例、跨项目和伪 GLOBAL 等负例、两类历史拒降已在 Win11 隔离 PostgreSQL 18.6 验证。此项无新偏差，不开放版本写；Owner/资格重证属于后续 SOL-03-A04。具体命令与边界见 `docs/progress/sol-03-a03-outline-reference-schema.md`。
