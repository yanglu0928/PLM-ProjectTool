# RAG-04-A04-P01：Retrieval 合并、Rerank 与降级边界核查

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_RETRIEVAL_MERGE_PRECHECK_PASS`

## 编码前检查

|字段|结论|
|---|---|
|当前 Phase|Phase 2：Platform Core|
|当前 WBS|`RAG-04-A04-P01`|
|输入基线|Gate 2 冻结 DM-04/API-03/ADR-004/009；CR-RAG-004、Schema0088、DEC-811～817|
|前置任务|A03 已完成专属claim、当前事实锁定/受控解密和参数化PROJECT FTS内存候选；尚无候选持久化或Run终态|
|涉及模块|RAG、AI Egress、Jobs；本项仅核策略与实施拆分|
|涉及实体|RetrievalRun、Candidate、ScorePart、Context、Egress Authorization；本项不改Schema|
|涉及 API|冻结Retrieval API不变；当前只开放`fts.project.v1 + none.v1`|
|涉及权限|沿用A03当前Actor/Project/License/Index授权快照；任何新增外发必须另有逐次Egress Authorization|
|验收标准|当前策略不假装vector/rerank；同分稳定排序；只在同范围处理不足；失败、shortfall、degraded语义可区分；无授权不得外发|
|风险|把“未启用通道”误报为降级；候选不足跨项目/旧Index补齐；零候选生成非法空Context；浮点排序跨平台漂移；默认外发query|

## 结论

当前 `fts.project.v1 + none.v1` 是一个完整、零外发的版本化策略，而不是 hybrid 策略的降级模式。它只消费 A03 的 FTS 候选：按量化整数分数降序，再按既有 candidate ordinal/ChunkId 稳定决胜，截取 Top-K；每条 Candidate 记录 FTS 与 FINAL 两个整数 ScorePart。未启用 vector、GLOBAL、Rerank 不产生 degraded 或 fallback 标记，`egress_state/rerank_state` 保持 `NOT_APPLICABLE`。

候选数量在 `1..top_k-1` 时允许成功，但写入显式 `CANDIDATE_SHORTFALL` quality flag；不能跨 Project、改用旧/READY Index、放宽 metadata 或扩大到 GLOBAL 来补齐。零候选不能创建最小 ContextBundle（Schema要求至少1项），因此以 `RAG_NO_AUTHORIZED_CANDIDATES` 失败关闭并原子终结，不伪造空 Context。

同一通道不需要归一化后再与其他通道比较，FTS raw micros 可直接成为当前策略的 final micros；避免用候选集合最大值动态归一化导致同一文档分数随其他候选变化。A05 持久化时同时保留 `FTS` raw/normalized/weight/weighted 和 `FINAL` 分量，固定策略引用，确保可复算。

vector/exact query embedding、GLOBAL合并和外部Rerank属于新的明确策略版本，必须先补 Query Embedding Envelope、Egress Preview/Authorization、发送栅栏、响应绑定和同范围 exact fallback。它们未完成前入口保持关闭；不得因“候选不足”自动触发外发。当前可用 FTS 路径不以未实现扩展能力为阻塞。

## 后续最小实施拆分

- `RAG-04-A04-P02`：纯应用层 FTS-only merge/final score/quality plan，稳定Top-K、shortfall和零候选失败语义；无数据库写入。
- `RAG-04-A05-P01`：Schema0089开放 Candidate/Score/最小Context与Job/Run成功/失败原子提交，包含零候选和过期generation专属收敛。
- `RAG-04-A05-P02`：完成Owner把A03 Preparation + FTS + A04 plan + A05发布组合为单次Worker，并接入AI `RAG_CONTEXT`读取。
- GLOBAL/vector/exact/rerank作为后续版本化策略任务保留在A04扩展，不阻塞首个明确FTS策略的可用闭环；开放前必须有独立CR/验证证据。

## 兼容、迁移与回滚

本项仅文档，无代码、Schema、API、依赖、网络或外发。当前创建入口已拒绝扩展策略，因此不会改变合法请求。P02为纯内存决策；A05再通过追加Migration开放终态，空历史可降、有结果历史向前修复。

## 验证

静态交叉核对冻结API允许版本化retrieval/rerank policy、Schema0088整数分数/quality flags/degraded/NOT_APPLICABLE字段、A03当前唯一策略与Context至少1项约束。未运行新增程序测试；不代表终态发布、Context、业务质量、性能、Gate 3、UAT或发行包通过。
