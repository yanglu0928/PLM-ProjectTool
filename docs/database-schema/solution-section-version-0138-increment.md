# SOL-01-A03-P02：SectionVersion Schema 0138 增量

日期：2026-10-08。依据冻结 DM-05、SC-01/02、API-04 和 CR-SOL-003；Gate 2 原冻结提交不改写。

|对象|表|数据库边界|
|---|---|---|
|SOL-05 章节版本|`plm.sol_section_versions`|同 Section 版本号唯一；Version/Section/Project 三元身份；同父替代链；标题、32 字节指纹、数组声明和计数；受控正文 DocumentVersion 或后续 OutputArtifact 二选一；DocumentVersion FK；Review 引用对|
|固定需求版本|`plm.sol_section_requirement_refs`|有序、版本内唯一、RequirementVersion/Requirement/Project 三元 FK|
|固定 Evidence|`plm.sol_section_evidence_refs`|有序、版本内唯一、Evidence 存在性 FK 与章节版本/项目复合 FK|

`sol_sections.current_approved_version_ref` 增加同 Section/Project 的可延迟 FK。FK 只证明归属，不证明实际 Review 批准。Evidence FK 只证明存在，不证明 GLOBAL/PROJECT 当下资格；Artifact 分支尚无 Output Owner FK，因此所有新表的 DML/TRUNCATE 仍由数据库拒绝。Spec 子表须在 SOL-06 真实 Owner 后补建；不把空表或 AI 草案当正式章节。

Win11 一次性 PG18.6：空/已有 User/Project 数据升级、空表降级重升、Alembic drift、正文二选一与真实 DocumentVersion/不存在版本、跨项目需求、Evidence 重复、跨 Section 指针、无效标题/指纹、Owner/TRUNCATE 闭锁、非空历史拒降 PASS；0137 旧验证复跑 PASS。后端全量 `3263 passed, 3 skipped, 4815 subtests passed`。合成上游夹具仅用于数据库 FK 测试，未被称为有效业务文档/Evidence。已有 pgvector/生成列反射警告非本增量造成。未验证真实业务 Owner、HTTP、Review、Server2025、性能或发行。

兼容性/升级：旧 API/权限/依赖不变；顺序运行 Alembic 0138，三张新表为空才允许降到 0137，旧 Outline/Section/目录版本历史保留。无客户数据外发。
