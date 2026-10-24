# RAG-03-A05-P01：EmbeddingIndex 验证与 READY/ACTIVE 边界核查

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_EMBEDDING_INDEX_VALIDATION_PRECHECK_PASS`

## 编码前检查

|字段|结论|
|---|---|
|当前 Phase|Phase 2：Platform Core|
|当前 WBS|`RAG-03-A05-P01`|
|输入基线|冻结 DM-04、API-03、SC-03/04、ADR-009、CR-RAG-003、Schema0084|
|前置任务|A04-P06 单次 Batch Worker 已通过；成功、已知失败和 UNKNOWN 边界已关闭|
|涉及模块|RAG、Jobs、AI；本项只做边界核查|
|涉及实体|EmbeddingIndex、EmbeddingBuild、EmbeddingBuildBatch、EmbeddingRecord；拟新增 IndexValidation|
|涉及 API|不修改；冻结 Index Validation/Activation 合同作为后续输入|
|涉及权限|不修改；激活仍须受权主体、License、Audit 和项目隔离|
|验收标准|明确完整性、HNSW、技术查询冒烟、独立业务质量以及 READY/ACTIVE 的非等价边界|
|风险|小样本 HNSW、历史 50 条质量集或 Schema PASS 被误写为生产质量/Gate 3 PASS|

## 核查结论

冻结数据模型要求 Index 在激活前完成来源 Scope、模型/维度、Chunk/Embedding 数量、缺失率、最小查询冒烟和质量检查；冻结 API 又要求 Validation 可查询、ACTIVE 只能从 READY 切换。现有 Schema0084 已能证明单个 Batch 的成功记录集，但尚无不可变的 Index 级验证事实，也没有 Build 完成、READY 或 ACTIVE 的合法状态转换。因此不能从“所有已处理 Batch 均成功”推断整个 Index 已完整，更不能从 HNSW 物理命中推断业务质量通过。

后续按两个互不替代的证据层实施：

1. **技术就绪证据**：精确来源集合与 AVAILABLE EmbeddingRecord 一一对应，缺失/额外/重复/错绑均为 0；所有计划 Batch 均 SUCCEEDED；Build、Index、模型、维度、Chunk profile、source/build fingerprint 一致；受控维度 HNSW 物理对象存在；同一 Scope/Project/Index 的 HNSW 查询计划与 exact cosine 对照完成有界技术冒烟。该层通过后才允许 Build SUCCEEDED、Index READY 和 Job 成功原子提交。
2. **业务质量证据**：使用未参与 Prompt、规则或标签调优的新独立留出集，按冻结门槛验证分类不低于 90%、精确引用不低于 98%，并保留 ProjectId 隔离、越界引用与失败关闭检查。只有有效业务质量证据与当前来源/模型/授权事实同时成立，才允许 READY→ACTIVE。

SC-04 的 1,001 条 32 维向量 Top-5 exact Recall 100% 和 POC-02 的 100k 合成性能只证明既有机制可行，不是当前 768/1024 维生产候选的正式性能或业务质量证据。POC-03 已见 50 条数据的 98% Top-5、48% 分类、74% 引用保持原始结论；它不得重复充当独立质量通过集。

## 后续最小实施拆分

- `RAG-03-A05-P02`：Schema0085 新增不可变 `EmbeddingIndexValidation` Owner，保存计数、指纹、受控 HNSW catalog/plan、exact 对照及技术结论；不得保存查询正文、客户正文或 Golden 答案。该任务仍不开放 READY/ACTIVE。
- `RAG-03-A05-P03`：实现技术验证服务和 Windows 11/PostgreSQL 18.6 实库冒烟；只有完整技术 PASS 才原子完成 Build/Job 并推进 Index READY，失败则关闭聚合且保留证据。
- `RAG-03-A05-P04`：实现独立业务质量证明登记和原子激活服务；同 `(scope, project_id, index_purpose)` 旧 ACTIVE 在同事务退役。没有新的独立达标证据时，真实 ACTIVE、Gate 3 和 UAT 保持阻塞。

## 兼容、迁移与回滚

本项没有代码、Schema、Migration、公开 API、依赖、网络调用或数据外发变化。后续 Schema 使用追加式不可变验证表，不把可变 JSON 摘要塞回 Index 根；历史 Index/Build/Batch/Record 不改写。Schema0085 计划为空表可降级，存在验证历史时拒绝物理降级并向前修复。READY/ACTIVE 转换在相应 Owner 与数据库提交期守卫完成前继续关闭。

## 验证

- 静态交叉核对 DM-04 EmbeddingIndex 状态机与激活前条件。
- 静态交叉核对 API-03 Index Validation/Activation 合同及质量错误边界。
- 静态交叉核对 SC-03 HNSW/exact 同 Scope 对照和代表数据性能要求。
- 静态交叉核对 SC-04 小样本计划证据的适用范围。
- 静态交叉核对 ADR-009 的独立留出集、90%/98% 门槛和 Gate 3/UAT 阻塞。

本项为文档前置核查，未运行新的程序测试；不代表多批循环、Build 完成、READY、ACTIVE、正式性能、业务质量、Windows Server 2025、Debian 13、Gate 3 或 UAT 通过。
