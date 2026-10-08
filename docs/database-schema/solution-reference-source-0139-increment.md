# SOL-01-A03-P03：ReferenceSolution 来源 Schema 0139 增量

日期：2026-10-08；依据冻结 DM-05/SC-01/02/API-04 与 CR-SOL-004，原 Gate 2 提交 `64cdf09` 不改写。

|对象|表|数据库边界|
|---|---|---|
|SOL-01 参考身份|`plm.sol_reference_solutions`|GLOBAL/PROJECT 二选一、Project FK、名称/Eligibility、当前版本同身份/Scope FK|
|固定参考版本|`plm.sol_reference_versions`|同身份版本号唯一、同父/Scope FK、SHA-256 指纹、适用性对象、来源项目类别、脱敏类别、文档/Evidence 声明数与同父替代 FK|
|固定文档版本|`plm.sol_reference_document_refs`|有序/不重复、版本归属 FK、DocumentVersion 存在性 FK|
|固定 Evidence|`plm.sol_reference_evidence_refs`|有序/不重复、版本归属 FK、Evidence 存在性 FK|

四表 DML/TRUNCATE 在真实 Owner 装配前失败关闭。现有 FK 不能证明 PROJECT Version 的 ProjectId 等于 Parent、GLOBAL/PROJECT 文档/Evidence 的实际授权、脱敏与当前性；也不能证明 Document 文件本体 Hash。后续 Owner 必须以锁定的 Application Port 同事务验证，不能只取消触发器。当前版本状态固定 DRAFT，根的 `REFERENCE_ONLY` 默认不构成项目正式方案；Eligibility 变更及 Outline 的真实参考引用后续实现。

Win11 一次性 PG18.6 通过空/已有 User/Project/Document 数据升级、空表降级重升、drift、GLOBAL/PROJECT Scope、错误来源/重复/不存在文档与 Evidence、跨身份指针、Owner/TRUNCATE 闭锁、非空历史拒降；0138 旧验证同实例复跑通过。后端全量 `3263 passed, 3 skipped, 4815 subtests passed`。首次新验证用例版本号重复先于 Scope FK 拒绝，调整夹具版本号后重新验证通过；非生产缺陷。已有 pgvector/生成列反射警告不属于本增量。

兼容性/升级：无公开 API、权限或依赖变化；线性迁移至 0139，四表为空才可降回 0138，既有方案数据保留。无客户数据外发。真实参考 Owner/Eligibility/目录引用、Review/Trace/Workflow、Server2025、性能和发行均未验。
