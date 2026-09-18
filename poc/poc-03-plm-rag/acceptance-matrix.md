# POC-03 PLM RAG 验收矩阵

|ID|验收项|Windows 11|Windows Server 2025|Debian 13|证据要求|
|---|---|---|---|---|---|
|P03-A01|POC-02/04/05 前置证据可用|PASS|NOT_RUN|NOT_RUN|数据库、AI Gateway、ParsedDocument 证据|
|P03-A02|100~200 条人工确认 Golden Dataset|IN_PROGRESS|NOT_RUN|NOT_RUN|R4 历史导入 120 条并通过 Schema/覆盖审计；R1 质量失败后重新打开标签一致性 Gate。R5 已保留 62 条明确人工结论，并将 58 条归并为 7 组，当前等待全局人工确认，尚未导出 R5 数据集|
|P03-A03|确定性 Chunk 与来源定位|PASS|NOT_RUN|NOT_RUN|Chunk、页/章节/表格定位、内容 Hash|
|P03-A04|Index 绑定单一 Embedding 模型|PASS|NOT_RUN|NOT_RUN|百炼 `qwen3.7-text-embedding`、1024 维、索引 `v1`；live probe 与不可变绑定 PASS|
|P03-A05|更换模型新建索引与全量重建|PASS|NOT_RUN|NOT_RUN|旧 `qwen3.7-text-embedding` 1024/v1 原地换模被拒绝；新建 `text-embedding-v4` 768/v2，以 120 条固定非客户文本真实调用 12 批完成 120/120 重建，旧向量复用 0；v2 未激活|
|P03-A06|PROJECT 强制 ProjectId 隔离|PASS|NOT_RUN|NOT_RUN|PostgreSQL 18.6 + pgvector 0.8.6；2 项目/40 条合成记录，Vector/FTS/Hybrid 共 6 组 Top-5、30 行结果，跨项目泄漏 0；缺失 ProjectId 被拒绝，参数注入返回 0|
|P03-A07|PostgreSQL Full Text 检索|PASS|NOT_RUN|NOT_RUN|PostgreSQL 18.6 `simple` + 上游中文术语空格规范化；4 场景/40 条合成记录，Top-5 平均及最低 Recall 100%，GIN 执行计划命中|
|P03-A08|pgvector 向量检索|PASS|NOT_RUN|NOT_RUN|PostgreSQL 18.6 + pgvector 0.8.6，1,000 条合成三维向量、4 场景 HNSW cosine Top-5，平均/最低 Recall 100%，HNSW 执行计划命中|
|P03-A09|Hybrid Retrieval|PASS|NOT_RUN|NOT_RUN|PostgreSQL 18.6 + pgvector 0.8.6，Vector 0.6 + Full Text 0.4；每通道候选池为 Top-K 的 4 倍，HNSW `m=32`、`ef_construction=200`、`ef_search=200`；1,000 条合成记录、4 场景 Top-5 平均/最低 Recall 100%，GIN/HNSW 均命中|
|P03-A10|外部可配置 Reranker|PASS|NOT_RUN|NOT_RUN|百炼华北 2 `qwen3-rerank` OpenAI-compatible `/reranks` 真实 5→3 调用 PASS；相关项位列前二；HTTP 429、超时、无效响应均 fail-open 保留原顺序并记录脱敏错误码|
|P03-A11|Top-5 Recall ≥95%|FAIL|NOT_RUN|NOT_RUN|真实 120 条：72/120，60.00%；同文档命中 88/120；120/120 实时 `qwen3-rerank`，GIN/HNSW 均命中|
|P03-A12|分类准确率 ≥90%|FAIL|NOT_RUN|NOT_RUN|真实 120 条：17/120，14.17%；已召回样本仅 10/72 正确；Golden 标签一致性风险已登记|
|P03-A13|来源引用准确率 ≥98%|FAIL|NOT_RUN|NOT_RUN|真实 120 条：61/120，50.83%；越界引用 0，引用合法但未达到期望精确 Chunk|
|P03-A14|Context Builder → AIService|PASS|NOT_RUN|NOT_RUN|`RagAIOrchestrator → AIService → ModelRouter → ProviderAdapter` 实测 PASS；Context 保留 Chunk/来源引用和字符预算，PromptId/Version、ProjectId、ChunkIds 可追溯；RAG 模块无 HTTP 或厂商适配代码|
|P03-A15|异常与空结果|PASS|NOT_RUN|NOT_RUN|6 场景 PASS：DB 不可用停止且不调用 AI；空结果/最高分 <0.5 返回无可靠匹配且不调用 AI；Reranker 不可用按原顺序降级；AI 不可用返回脱敏可重试状态；正常链路保留引用 ID|

## 状态定义

- `PASS`：已执行且证据满足要求。
- `IN_PROGRESS`：已启动但尚未满足验收要求。
- `NOT_RUN`：未执行，不得视为通过。
- `DEFERRED_BY_USER`：用户已明确批准暂缓并登记独立例外，不得描述为通过。
- `FAIL`：已执行但未达到门槛，必须补充失败分析。

POC-03 只有质量指标、隔离、异常链路和目标平台范围全部通过，或未执行范围取得独立用户例外后，才能收口。
