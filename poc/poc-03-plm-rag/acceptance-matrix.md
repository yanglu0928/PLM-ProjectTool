# POC-03 PLM RAG 验收矩阵

|ID|验收项|Windows 11|Windows Server 2025|Debian 13|证据要求|
|---|---|---|---|---|---|
|P03-A01|POC-02/04/05 前置证据可用|PASS|NOT_RUN|NOT_RUN|数据库、AI Gateway、ParsedDocument 证据|
|P03-A02|100~200 条人工确认 Golden Dataset|PASS|NOT_RUN|NOT_RUN|R5 全局确认后严格导入 120/120，问题 0；覆盖 29 份文档、120 个唯一问题、四类来源和五类最终业务标签；工作流态不进入最终数据集|
|P03-A03|确定性 Chunk 与来源定位|PASS|NOT_RUN|NOT_RUN|Chunk、页/章节/表格定位、内容 Hash|
|P03-A04|Index 绑定单一 Embedding 模型|PASS|NOT_RUN|NOT_RUN|百炼 `qwen3.7-text-embedding`、1024 维、索引 `v1`；live probe 与不可变绑定 PASS|
|P03-A05|更换模型新建索引与全量重建|PASS|NOT_RUN|NOT_RUN|旧 `qwen3.7-text-embedding` 1024/v1 原地换模被拒绝；新建 `text-embedding-v4` 768/v2，以 120 条固定非客户文本真实调用 12 批完成 120/120 重建，旧向量复用 0；v2 未激活|
|P03-A06|PROJECT 强制 ProjectId 隔离|PASS|NOT_RUN|NOT_RUN|PostgreSQL 18.6 + pgvector 0.8.6；2 项目/40 条合成记录，Vector/FTS/Hybrid 共 6 组 Top-5、30 行结果，跨项目泄漏 0；缺失 ProjectId 被拒绝，参数注入返回 0|
|P03-A07|PostgreSQL Full Text 检索|PASS|NOT_RUN|NOT_RUN|PostgreSQL 18.6 `simple` + 上游中文术语空格规范化；4 场景/40 条合成记录，Top-5 平均及最低 Recall 100%，GIN 执行计划命中|
|P03-A08|pgvector 向量检索|PASS|NOT_RUN|NOT_RUN|PostgreSQL 18.6 + pgvector 0.8.6，1,000 条合成三维向量、4 场景 HNSW cosine Top-5，平均/最低 Recall 100%，HNSW 执行计划命中|
|P03-A09|Hybrid Retrieval|PASS|NOT_RUN|NOT_RUN|PostgreSQL 18.6 + pgvector 0.8.6，Vector 0.6 + Full Text 0.4；每通道候选池为 Top-K 的 4 倍，HNSW `m=32`、`ef_construction=200`、`ef_search=200`；1,000 条合成记录、4 场景 Top-5 平均/最低 Recall 100%，GIN/HNSW 均命中|
|P03-A10|外部可配置 Reranker|PASS|NOT_RUN|NOT_RUN|百炼华北 2 `qwen3-rerank` OpenAI-compatible `/reranks` 真实 5→3 调用 PASS；相关项位列前二；HTTP 429、超时、无效响应均 fail-open 保留原顺序并记录脱敏错误码|
|P03-A11|Top-5 Recall ≥95%|PASS|NOT_RUN|NOT_RUN|R5 真实 120 条：中文 OCR 字间空白规范化 + 来源过滤 + 确定性词法 IDF 为 114/120（95.00%）；同数据探索调优，正式生产声明仍需独立留出集|
|P03-A12|分类准确率 ≥90%|FAIL|NOT_RUN|NOT_RUN|R5 对 R1 既有预测重评分为 69/120（57.50%）；方案 A 的 R6 人工确认完成前，尚未启动 Prompt v2 新增外部调用|
|P03-A13|来源引用准确率 ≥98%|IN_PROGRESS|NOT_RUN|NOT_RUN|方案 A 已获批；R6 已为 6 条低区分度样本生成明确问题、原核定引用与 Top-5 对照，114 条及全部分类锁定不变。当前等待人工批量确认，确认前不重跑指标|
|P03-A14|Context Builder → AIService|PASS|NOT_RUN|NOT_RUN|`RagAIOrchestrator → AIService → ModelRouter → ProviderAdapter` 实测 PASS；Context 保留 Chunk/来源引用和字符预算，PromptId/Version、ProjectId、ChunkIds 可追溯；RAG 模块无 HTTP 或厂商适配代码|
|P03-A15|异常与空结果|PASS|NOT_RUN|NOT_RUN|6 场景 PASS：DB 不可用停止且不调用 AI；空结果/最高分 <0.5 返回无可靠匹配且不调用 AI；Reranker 不可用按原顺序降级；AI 不可用返回脱敏可重试状态；正常链路保留引用 ID|

## 状态定义

- `PASS`：已执行且证据满足要求。
- `IN_PROGRESS`：已启动但尚未满足验收要求。
- `BLOCKED`：已有可重复证据表明必须先完成 L3 决策，受影响任务暂停。
- `NOT_RUN`：未执行，不得视为通过。
- `DEFERRED_BY_USER`：用户已明确批准暂缓并登记独立例外，不得描述为通过。
- `FAIL`：已执行但未达到门槛，必须补充失败分析。

POC-03 只有质量指标、隔离、异常链路和目标平台范围全部通过，或未执行范围取得独立用户例外后，才能收口。
