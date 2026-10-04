# RAG-04-A03-P01：Retrieval 执行链编码前核查

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_RETRIEVAL_EXECUTION_PRECHECK_PASS`

## 编码前检查

|字段|结论|
|---|---|
|当前 Phase|Phase 2：Platform Core|
|当前 WBS|`RAG-04-A03-P01`|
|输入基线|Gate 2 冻结 DM-04、SC-01～04、API-03、ADR-004/009；CR-RAG-004、Schema0088、DEC-811～813|
|前置任务|A02-P02 已能受权创建仅 FTS/无 Rerank 的 RetrievalRun、密文 QueryContent 与单次 Job；正式业务 ACTIVE Index 仍受独立质量证据阻塞|
|涉及模块|RAG、Jobs、Project、Auth、Audit、License；本项只核执行边界并拆分实现|
|涉及实体|Job、JobLease、JobAttempt、RetrievalRun、RetrievalQueryContent、EmbeddingIndex、IndexSourceChunk、DocumentChunk、EmbeddingRecord|
|涉及 API|本项不修改冻结 `/api/v1`；执行链为内部 Worker Owner|
|涉及权限|认领后、解密前必须重验当前 License、Project、请求 Actor/Membership、ACTIVE Index/Model/来源；SYSTEM Worker 身份不能替代原请求主体授权|
|验收标准|通用 Worker 不得认领或过期终结 Retrieval Job；专属 claim 只接收精确 payload/单次 generation；查询密文只在当前受权短生命周期缓冲解密并校验 fingerprint；FTS SQL 完全参数化且只扫描 Run 固定 Index 的当前精确来源；候选计算不提前形成部分数据库快照|
|风险|通用 claim 抢占；Job/Run 过期状态分裂；撤权后仍解密；任意 metadata 变相 SQL；FTS 扫描非选定 generation；计算中途写入部分 Candidate；合成 ACTIVE 被误报为业务质量|

## 现状证据与差异

`JobLeaseRepository` 目前只把 `rag/RAG_INDEX_BUILD` 排除在通用 claim 和通用过期处理之外，尚无 `RAG_RETRIEVAL` 专属入口。因此 A02-P02 创建的 `rag/RAG_RETRIEVAL` 会被 `claim_next()` 选中；若租约过期，通用逻辑还能只修改 Job/Lease/Attempt。由于 RetrievalRun 的状态转换尚被 Schema0088 关闭，这不是可接受的临时实现，而是必须先修复的 Owner 路由缺口。

现有 `DocumentChunk.search_vector` 是 `to_tsvector('simple', search_body)` 的 stored 列并有 GIN；`IndexSourceChunk` 固定 Index 到精确 Chunk/文本指纹；`EmbeddingRecord` 固定同一 Index/Model/Chunk。首个已开放策略只有 `fts.project.v1 + none.v1`，因此本阶段先实现 PROJECT FTS，不为尚未授权的 Query Embedding 或 Reranker 建立旁路。

Schema0088 已允许当前 RUNNING Run 下写 Candidate/Score，但 Run、Job、候选和最终 Context 的完整终态 Owner 尚未安装。为避免 Worker 在搜索循环中留下部分候选，A03 只生成有界、不可变的内存候选计划；数据库 Candidate/Score、Run/Job 终态与最小 Context 仍由 A05 在单一短事务发布。

## 锁定执行边界

1. 新增 `RAG_RETRIEVAL` 专属 claim DTO/Repository/Service，固定 `owner_module=rag`、`job_type=RAG_RETRIEVAL`、`scope=PROJECT`、`max_attempts=1`、`attempt_no=1`、`fencing_token=1`，并严格解析唯一 payload `retrieval_run_id`。
2. 通用 claim 和通用过期处理必须同时排除 `RAG_RETRIEVAL`；过期 Retrieval 后续由专属 Reconciler 在一事务关闭 Job、Lease、Attempt、Run 并写 Audit。专属 claim 不自动接管过期 generation。
3. 每个执行检查点都通过当前 lease 重新锁定 Job/Run；以 Run 的 `requested_by` 重验用户有效状态、当前 Project/Membership/角色、License、Run 固定 ACTIVE Index/Model、精确 IndexSourceChunk 和可用来源。SYSTEM Worker 只负责执行，不获得业务访问权。
4. 解密在上述检查通过后发生。AAD、key provider ref、密文元数据、run/project/query fingerprint/retention 必须一致；解密后重新规范化并计算 SHA-256，与 Run/QueryContent 双重 fingerprint 相等才可使用，所有可变明文缓冲在成功或异常路径归零。
5. FTS 只由仓储把固定 filter AST 映射为预定义 SQLAlchemy 谓词；查询文本作为 bind parameter 进入与 stored `simple` 配置一致的 `websearch_to_tsquery`/受控等价表达式，禁止调用方提供 SQL、列名、regconfig、排序或 JSONPath。
6. FTS 候选必须连接 Run 固定的 PROJECT ACTIVE Index、精确 `IndexSourceChunk`、同 fingerprint 的 ACTIVE `DocumentChunk` 和 AVAILABLE `EmbeddingRecord`，并限定相同 ProjectId/Model；排名稳定使用量化整数分数、固定次级顺序和有界 Top-K。
7. A03 输出只包含后续发布所需的最小不可变 DTO：Index/Model、Chunk、DocumentVersion、ParseResult、source type/locator、channel、原始量化分数、授权快照 fingerprint；不返回向量、不携带完整正文、不写日志或 Job payload。
8. metadata 首版仅支持已登记字段/操作符；无法由当前 Schema 不歧义证明的 `effective_from/effective_to` 保持关闭，不能从任意 metadata JSON 猜测。

## 后续最小实施拆分

- `RAG-04-A03-P02`：专属单次 claim 与通用队列/过期隔离，包含 payload、scope、attempt/fencing 和 current claim 负例。
- `RAG-04-A03-P03`：当前事实重验、受控 QueryContent 解密和 fingerprint/归零边界；只返回执行准备证明。
- `RAG-04-A03-P04`：参数化 PROJECT FTS 与有界内存候选计划；固定 Index generation、Project、来源、metadata AST 和稳定排名。
- Retrieval Job 过期原子收敛在 Run 状态 Owner 开放时与 A05 一并实现；在此之前专属 claim 不重领过期 Job，避免拆分聚合。
- vector/exact Query Embedding、GLOBAL 合并、Rerank 外发和 degraded/fallback 继续由 A04 按显式 Egress 授权实现；当前 FTS 策略不伪装这些能力。

## 兼容、迁移与回滚

本项仅增加文档和更新 `CR-RAG-004`，不修改代码、Schema、API、依赖、网络或外发。P02 是内部队列路由收紧：停止 Retrieval Worker 即可回滚运行行为，但已认领或过期历史必须由专属对账向前修复，不能重新交给通用 Worker。P03/P04 不新增外部协议；A05 前不持久化候选。

## 验证

- 静态确认通用 `claim_next()` 只排除 `RAG_INDEX_BUILD`，当前不存在 `claim_next_rag_retrieval`。
- 静态确认 A02-P02 Job payload 只有 `retrieval_run_id`、`max_attempts=1`，QueryContent 与 Run 分离。
- 静态确认 stored `simple` FTS/GIN、IndexSourceChunk 精确来源及 AVAILABLE EmbeddingRecord 绑定可支撑同 generation FTS。
- 静态确认 Schema0088 的 Run 状态仍关闭、Context 仍关闭，候选最终发布必须留给后续原子完成 Owner。

未运行新增程序测试。本项不代表 Retrieval Worker、候选持久化、vector/exact、Rerank、正式 ACTIVE、业务质量、性能、Gate 3、UAT、Windows Server 2025、Debian 13 或发行包通过。
