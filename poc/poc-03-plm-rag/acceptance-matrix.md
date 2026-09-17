# POC-03 PLM RAG 验收矩阵

|ID|验收项|Windows 11|Windows Server 2025|Debian 13|证据要求|
|---|---|---|---|---|---|
|P03-A01|POC-02/04/05 前置证据可用|PASS|NOT_RUN|NOT_RUN|数据库、AI Gateway、ParsedDocument 证据|
|P03-A02|100~200 条人工确认 Golden Dataset|IN_PROGRESS|NOT_RUN|NOT_RUN|109 条人工 APPROVED 且 Schema 导出 PASS；覆盖审计 FAIL：唯一查询/来源类型/分类均为 1|
|P03-A03|确定性 Chunk 与来源定位|PASS|NOT_RUN|NOT_RUN|Chunk、页/章节/表格定位、内容 Hash|
|P03-A04|Index 绑定单一 Embedding 模型|PASS|NOT_RUN|NOT_RUN|百炼 `qwen3.7-text-embedding`、1024 维、索引 `v1`；live probe 与不可变绑定 PASS|
|P03-A05|更换模型新建索引与全量重建|NOT_RUN|NOT_RUN|NOT_RUN|索引版本和重建记录|
|P03-A06|PROJECT 强制 ProjectId 隔离|NOT_RUN|NOT_RUN|NOT_RUN|跨项目泄漏为 0|
|P03-A07|PostgreSQL Full Text 检索|NOT_RUN|NOT_RUN|NOT_RUN|查询与 Top-K|
|P03-A08|pgvector 向量检索|NOT_RUN|NOT_RUN|NOT_RUN|查询与 Top-K|
|P03-A09|Hybrid Retrieval|NOT_RUN|NOT_RUN|NOT_RUN|融合策略和 Top-K|
|P03-A10|外部可配置 Reranker|NOT_RUN|NOT_RUN|NOT_RUN|请求、错误和降级记录|
|P03-A11|Top-5 Recall ≥95%|NOT_RUN|NOT_RUN|NOT_RUN|Golden Dataset 指标|
|P03-A12|分类准确率 ≥90%|NOT_RUN|NOT_RUN|NOT_RUN|六类允许结果的混淆统计|
|P03-A13|来源引用准确率 ≥98%|NOT_RUN|NOT_RUN|NOT_RUN|引用与来源定位核对|
|P03-A14|Context Builder → AIService|NOT_RUN|NOT_RUN|NOT_RUN|不绕过统一 AI Gateway|
|P03-A15|异常与空结果|NOT_RUN|NOT_RUN|NOT_RUN|AI/Reranker/DB 不可用及无可靠匹配|

## 状态定义

- `PASS`：已执行且证据满足要求。
- `IN_PROGRESS`：已启动但尚未满足验收要求。
- `NOT_RUN`：未执行，不得视为通过。
- `DEFERRED_BY_USER`：用户已明确批准暂缓并登记独立例外，不得描述为通过。
- `FAIL`：已执行但未达到门槛，必须补充失败分析。

POC-03 只有质量指标、隔离、异常链路和目标平台范围全部通过，或未执行范围取得独立用户例外后，才能收口。
