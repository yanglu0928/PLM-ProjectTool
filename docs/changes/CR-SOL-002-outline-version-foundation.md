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
