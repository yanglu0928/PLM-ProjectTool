# CR-SOL-004：ReferenceSolution 固定来源先于正式目录引用

日期：2026-10-08；状态：依据 CR-EXEC-001 持续授权先记录后实施。Gate 2 原冻结提交 `64cdf09` 不改写。TraceLink：CR-SEQ-001 → CR-SOL-001/002/003 → SOL-01-A03-P03 → 本 CR。

## 来源、冲突与方案

冻结 DM-05/SC-01/02/API-04 要求 SOL-01 的 GLOBAL/PROJECT 参考身份、不可变参考版本、固定 DocumentVersion/Evidence、适用性/来源项目类别/脱敏分类和 Eligibility；SOL-03 目录版本必须能固定引用合格的 ReferenceVersion。当前仅有目录/章节结构，既无 ReferenceSolution Owner，也无可验证的版本目标。直接为目录补可写裸 UUID 会跨项目引用或误将参考内容当正式承诺。

- 不选把 ReferenceVersion 混入 OutlineVersion 或自动形成正式 Solution：违反参考/正式隔离。
- 不选用无目标 FK 的自由 UUID 或仅用 JSONB 保存来源：无法证明固定版本与反向追溯。
- 选择先建 `sol_reference_solutions`、`sol_reference_versions`、`sol_reference_document_refs`、`sol_reference_evidence_refs` 四张闭锁表。DocumentVersion/Evidence 存在性由 FK 证明；Scope/Project、脱敏适用性、当前/合格来源须由后续真实 Owner 同事务验证。此增量不开放 API/权限，不把新表行认作业务事实。后续再为 `sol_outline_reference_refs` 建真实复合 FK。

## 差异、影响、迁移与回滚

这是冻结表映射的实施排序/字段约束细化，不增删产品 Scope 或修改冻结 `/api/v1`。Reference root 使用 M-SCP，版本使用 V-SCP，来源子表有有序固定引用；根 Eligibility 初始 `REFERENCE_ONLY`，版本为 `DRAFT` 来源快照，状态变更/Review/Trace 不由本增量开放。来源材料的 GLOBAL/PROJECT 资格不能单靠单列 FK 证明，故所有四表 DML/TRUNCATE 拒绝，后续 Owner 必须在开放前验证。

Alembic `20261008_0139` 只新增空表和根的当前版本归属 FK，不迁移客户数据。空库/已有项目库升级、空表降级重升、drift、Scope/Project 约束、固定引用/顺序/重复、Owner/历史拒绝、后端全量回归必测；任一新表非空拒降。回滚仅限四表均空，原 0136～0138 历史不变。剩余风险：Reference 文档内容完整性/脱敏、Evidence 当前性及目录实际引用需后续 Owner/Review/Trace 验收；Gate 3/正式 Solution 仍 OPEN。
