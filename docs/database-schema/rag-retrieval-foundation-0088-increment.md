# Schema0088：RAG RetrievalRun 与最小 Context 基础增量

日期：2026-10-04

状态：`WINDOWS11_POSTGRESQL18_VERIFIED`

## 物理对象

|表|职责|正文边界|
|---|---|---|
|`rag_retrieval_runs`|固定 Scope/Project/Actor、query/filter 指纹、实际 ACTIVE Index、Policy、Job、状态与追踪|不保存 query/snippet/vector|
|`rag_retrieval_query_contents`|专用加密 query 内容、密钥引用、保留时间|只保存密文和最小加密元数据|
|`rag_retrieval_candidates`|固定受权 Index/Model/Chunk/DocumentVersion/Locator、通道、rank 与最终分数|不保存向量或完整 Chunk 正文|
|`rag_retrieval_score_parts`|确定性微分值 score breakdown 与策略引用|不保存模型正文|
|`rag_context_bundles`|Context policy、指纹、item/token 边界|不保存正文|
|`rag_context_items`|Candidate/Chunk/DocumentVersion、locator、截取范围、token 与 snippet/access 指纹|不保存 snippet 正文|

## 约束与状态

- Run 与 `rag/RAG_RETRIEVAL` PENDING Job 必须同 Scope/Project/Actor/trace，Job payload 只能是 `retrieval_run_id`。
- PROJECT Run 必须绑定同 Project 的 ACTIVE Index；GLOBAL Index 如使用必须为 GLOBAL ACTIVE。Schema0088 首步只允许初始 `RUNNING/v0`，UPDATE/DELETE/TRUNCATE 关闭。
- QueryContent 必须与 Run 同事务、同 Project/query fingerprint/transaction id；密文 17～65536 bytes、明文计数 1～16384 bytes，并有有限的未来保留时间。提交期 deferred trigger 拒绝缺 QueryContent 的 Run。
- metadata filter 顶层只允许 document category、source type、DocumentVersion、effective date 和 `business`；`business` 内部字段由后续版本化 Policy Owner 进一步白名单验证。
- Candidate 必须来自 Run 绑定的 ACTIVE Index、精确 source snapshot、ACTIVE Chunk 和 AVAILABLE EmbeddingRecord；GLOBAL/PROJECT 身份与 Run 逐层核对。
- Score 使用整数微分值避免浮点 NaN/Infinity 与跨平台序列化漂移。
- ContextBundle 只允许成功 Run，由后续完成 Owner 开放；Schema0088 保持关闭。Item 固定最多 8192 字符的范围且只存指纹，不复制正文。
- 六张表均保留历史；有任何 Retrieval/Context 历史时拒绝降级到0087。

## 迁移、回滚与验证

升级为追加表，不回填既有 Chunk/Embedding/Index，也不产生 Retrieval Job。空历史可降0087并重升；有历史采用停止新作业、备份和向前修复。Windows 11/PostgreSQL 18.6 已验证空库/已有 User+Project 数据升级、Alembic drift、空历史降级重升、有历史拒降，以及合成 ACTIVE 下的 Run+密文 QueryContent、Candidate/Score 正向绑定、缺 QueryContent/Run 更新/提前 Context 负例。

Schema PASS 不代表创建 Owner、Worker、Rerank、Context finalizer、HTTP、正式业务 ACTIVE、质量、性能、Gate 3 或 UAT 通过。
