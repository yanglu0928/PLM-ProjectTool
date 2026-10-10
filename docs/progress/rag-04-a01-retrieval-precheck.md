# RAG-04-A01：RetrievalRun / ContextBundle 编码前核查

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_RETRIEVAL_PRECHECK_PASS`

## 编码前检查

|字段|结论|
|---|---|
|当前 Phase|Phase 2：Platform Core|
|当前 WBS|`RAG-04-A01`|
|输入基线|Gate 2 冻结 DM-04、SC-01～04、API-03、ADR-004/009；Schema0087、CR-RAG-001～003|
|前置任务|DocumentChunk/FTS、EmbeddingRecord/HNSW、Build/Validation/Quality/Activation 机制已实现；正式业务 ACTIVE Index 仍受独立质量证据阻塞|
|涉及模块|RAG、Jobs、Project、Auth、Audit、License、AI Egress；本项只核边界并拆分实施|
|涉及实体|RetrievalRun、RetrievalQueryContent、RetrievalCandidate、RetrievalScorePart、ContextBundle、ContextItem、Job|
|涉及 API|冻结 POST/GET/Result/Context/Cancel `/api/v1/projects/{project_id}/retrieval-runs...`；本项不改 API|
|涉及权限|创建：ProjectManager、ImplementationMember、CustomerManager；读取：创建者或受权项目角色；取消：创建者或 ProjectManager；Session/CSRF、当前 Membership、License 每次重验|
|验收标准|ProjectId 全链路失败关闭；只使用当前 ACTIVE 且已授权 Index；GLOBAL/PROJECT 分开召回后按版本化策略合并；候选不足只在同范围扩大或 exact/FTS 回退；结果/Context 不泄漏向量、Golden、人工答案、无权全文或其他项目存在性|
|风险|异步查询正文落入 Job/Audit；旧/合成 ACTIVE 被误当正式质量；任意 metadata key 变相注入；降级结果未标记；跨项目或旧 generation 混入；Context 保存无界正文|

## 现状与边界结论

仓库已具备 `rag_document_chunks` 的 `simple` FTS、精确 Chunk 来源、768/1024 pgvector HNSW、Embedding Index 状态及原子激活机制；尚无生产 RetrievalRun、Candidate、ScorePart、ContextBundle 或 Retrieval Worker。AI 执行计划已有完整 `RAG_CONTEXT` 引用合同，但仍正确地对 `project-documents.v1` 失败关闭，不能把未实现检索静默降级为空 Context。

正式环境没有通过新独立业务质量复验的 ACTIVE Index。后续可用明确标记的合成 ACTIVE fixture 验证机制，但不能把它写成正式检索质量、Gate 3 或 UAT 证据；没有 ACTIVE Index 的正式请求必须安全失败，不能退回旧 generation、PLANNED/READY Index 或跨项目内容。

冻结 POST 为异步 `202`，所以查询原文必须跨请求供 Worker 使用；但 Job `payload_refs`、Outbox、Audit、运行视图都不得保存或返回查询正文。实现采用 RAG 自有的专用加密 `RetrievalQueryContent`：Run/Job 只保存 QueryContent 引用和规范化查询 SHA-256，密文使用独立注入的数据加密端口、版本化 AAD 与外部密钥引用；明文只在当前受权 Worker 的短生命周期缓冲中存在并归零。它不复用 `plt_secret_*` 业务表，不把查询伪装成 API Secret，也不改变冻结 DTO。

首版 metadata filter 固定字段集合，不接收任意键：`document_category`、`source_type`、`document_version_ref`、`effective_from`、`effective_to` 以及由版本化 RetrievalPolicy 显式登记的业务白名单。输入先规范化为结构化 AST 和 SHA-256，再由仓储映射到参数化 SQL；不保存/解释 SQL、JSONPath、列名或表达式字符串。

候选生成必须先分别锁定/重验 GLOBAL 与同一 PROJECT 的 ACTIVE Index、Model、来源 Chunk/Record，再分别执行 FTS、vector 或 exact；每个 Candidate 固定 Index/Model/Policy generation、Chunk/DocumentVersion/Locator/source type、原始 rank 和分数组件。合并、Rerank 与 Context Builder 只消费这份受权快照，不能重新解析动态 current ref。外部 Query Embedding/Reranker 另走现有 Egress Preview/Authorization/发送栅栏；纯 FTS/exact 明确记录 `NOT_APPLICABLE`。

ContextBundle 是成功 Run 下不可变、有界、可复算的最小快照。Item 只保存受权 Chunk 引用、locator、字符截取范围、顺序、token count 与片段指纹；最小 snippet 由受权读取面按固定范围投影。首版不在 Context 表复制完整 Chunk 正文，以避免形成第二份无界客户内容。

## 后续最小实施拆分

- `RAG-04-A02-P01`：Schema0088/ORM，建立 Run、专用加密 QueryContent、Candidate/ScorePart、ContextBundle/Item 及提交期隔离/不可变守卫；状态转换暂时关闭。
- `RAG-04-A02-P02`：受权异步创建 Owner，把 Session/CSRF、Membership、License、Project、ACTIVE Index、策略、query/filter 指纹、加密正文、Job、Audit 与幂等回执原子创建。
- `RAG-04-A03`：单次 Retrieval Job claim、当前事实重验与 PROJECT/GLOBAL 分区的 FTS/vector/exact 候选生成；没有正式 ACTIVE 时失败关闭。
- `RAG-04-A04`：版本化 merge/rerank、外发授权与显式 degraded/fallback 证据；不因候选不足放宽 ProjectId 或 Index generation。
- `RAG-04-A05`：候选/分数、不可变最小 Context 和 Job/Run 终态原子提交，并接入 AI `RAG_CONTEXT` 读取合同。
- `RAG-04-A06`：冻结 Create/Get/Result/Context/Cancel HTTP、权限矩阵、Windows 11/PostgreSQL 18 组合与前端消费边界。

## 兼容、迁移与回滚

本分项仅增加文档和 `CR-RAG-004`，不修改代码、Schema、API、依赖、网络或外发。后续 Schema0088 采用追加表；空历史可降级，一旦存在加密查询、候选或 Context 历史则拒绝物理降级并向前修复。原冻结提交 `64cdf09`、Schema0087 和既有 RAG 历史不改写。

## 验证

- 静态交叉核对冻结 DM-04 的 RetrievalRun/Context 字段、Project 隔离、外发授权与降级要求。
- 静态交叉核对 API-03 的五个 RetrievalRun Operation、角色、DTO 禁止字段及 exact fallback。
- 静态核对 SC-01 的五张 RAG-04 物理表候选、现有 Schema0087/ORM、Job payload 安全边界和 AI `RAG_CONTEXT` 合同。
- `rg` 确认生产仓库没有现存 RetrievalRun/ContextBundle Owner；只有 AI 侧失败关闭引用和前端安全 DTO。

未运行新增程序测试。本项不代表 Retrieval、正式 ACTIVE、业务质量、性能、Gate 3、UAT、Windows Server 2025、Debian 13 或发行包通过。
