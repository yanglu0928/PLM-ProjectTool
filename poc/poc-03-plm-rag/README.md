# POC-03 PLM RAG

## Status

`FAIL / BLOCKED_QUALITY_GATE`

## Objective

验证统一 RAG 链路：`ParsedDocument → Chunk → Metadata → PostgreSQL 18/pgvector + Full Text → Hybrid Retrieval → Reranker → Context Builder → AIService`，并以 100~200 条经人工确认的 Golden Dataset 量化 Top-5 Recall、分类准确率和来源引用准确率。

本目录全部实现属于 Phase 0 验证性脚手架，不是已冻结的数据模型、API Contract 或正式业务实现。

## Environment

- 当前执行环境：Windows 11 x86-64，Python 3.13.x。
- PostgreSQL 18 + pgvector：复用 POC-02 已验证制品和证据。
- Document Parser：复用 POC-05 的 PoC `ParsedDocument` 输出。
- AI：只能通过 POC-04 的统一 `AIService` 边界调用 DeepSeek。
- Windows Server 2025、Debian 13：本 PoC 尚未执行。

## Input

- 本地 `方案库/`：18 个文件，共 365,328,831 字节；17 个受支持文件生成 13,710 个内容块。
- 本地 `技术协议&合同/`：18 个文件，共 38,808,615 字节；4 个 DOCX 和 5 个扫描 PDF 生成 46,720 个内容块。
- 本地 `标准能力库/`：20 个 DOCX 全部解析通过；按用户明确的资料库用途确定性分区为 19 份 `STANDARD_CAPABILITY`、1 份 `SURVEY`。
- 三个目录均由 Git 忽略；当前四类候选输入为 29 个 ParsedDocument、79,842 个内容块。
- 历史方案不再用于补足锁定四类来源；`方案库/` 与 `技术协议&合同/` 中的 10 个旧版 `.doc` 仍不受支持。

## Steps

1. 从 POC-05 本地 `ParsedDocument` 生成带 `scope`、`project_id`、来源定位和内容 Hash 的确定性 Chunk。
2. 按文档轮询抽样 120 条候选评审记录，避免由大文档垄断样本。
3. 所有候选记录标记为 `PENDING_HUMAN_REVIEW`；规则或 AI 输出不得直接成为 Golden Dataset 真值。
4. 可先运行完全本地的规则生成器预填查询、分类、答案关键术语和引用定位，再由人工逐条或抽样修正；预填结果不得直接变成正式数据。
5. 使用 `scripts/import_review_workbook.py` 复核不可变来源字段，只导出人工 `APPROVED`、字段完整且引用仍在原候选定位范围内的记录。
6. 在 PostgreSQL 18 + pgvector 上验证 ProjectId 隔离、FTS、Vector、Hybrid、Reranker 和 Context Builder。
7. 通过统一 AIService 执行端到端回归，计算并留存质量指标。

## Result

P0.09 候选准备链已更新：用户指定的 `标准能力库/` 20 个 DOCX 全部解析通过，确定性分区为 19 份 `STANDARD_CAPABILITY` 和 1 份 `SURVEY`；连同 4 份合同、5 份技术协议，29 个 ParsedDocument 生成 1,695 个带 PROJECT/ProjectId 和来源定位的 Chunk，并轮询抽样 120 条候选，覆盖 29/29 个文档。R4 经严格导入得到 120 条 APPROVED、0 个问题，P03-A02 PASS。P03-A04 使用百炼 `qwen3.7-text-embedding` 实测请求/返回 1024 维，索引 `v1` 绑定 PASS。

P03-A11~A13 首轮真实质量验证完整执行但未达门槛：Top-5 Recall 72/120（60.00%）、分类准确率 17/120（14.17%）、来源引用准确率 61/120（50.83%），三项均 FAIL。120/120 次重排使用百炼 `qwen3-rerank`，GIN/HNSW 均实际命中，预测无缺失、越界引用为 0。精确 Chunk 召回 72 条而同文档召回 88 条；分类在已召回样本中仍只有 10/72 正确。R4 的最终分类多数继承候选阶段关键词启发式值，已登记 Golden 标签一致性风险；不得通过事后改标签或降低门槛掩盖失败。

P03-A05 已验证模型切换纪律：保留激活的 `qwen3.7-text-embedding` 1024 维 `v1`，拒绝对旧 index_id 原地更换模型；创建独立 `text-embedding-v4` 768 维 `v2`，使用 120 条固定非客户文本执行 12 批真实请求，120/120 全量重建完成，旧向量复用数为 0。`v2` 状态为验证通过但未激活，不替换当前绑定。

P03-A06 已在本地 PostgreSQL 18.6 + pgvector 0.8.6 实测 PROJECT 强制隔离：两个项目各 20 条合成记录，Vector、Full Text、Hybrid 各执行双项目 Top-5 查询；30 行结果跨项目泄漏为 0。缺失 ProjectId 在数据库调用前被拒绝，参数注入式 ProjectId 仅作为参数处理并返回 0 行。验证结束后临时 Schema 已删除。

P03-A07 已验证 PostgreSQL Full Text：使用 `simple` 配置和上游空格分词后的中文术语，建立表达式 GIN 索引；4 组查询、40 条合成记录的 Top-5 平均和最低 Recall 均为 100%，执行计划确认使用 GIN。该结论不代表 PostgreSQL 内置中文分词，正式链路必须保留上游术语规范化步骤。

P03-A08 已验证 pgvector HNSW：1,000 条合成三维向量、4 组已知近邻执行 cosine Top-5，平均与最低 Recall 均为 100%，执行计划确认使用 HNSW。该结果验证检索机制，不替代被 P03-A02 阻塞的真实 Golden Dataset 指标。

P03-A09 已验证 Hybrid Retrieval：Vector 0.6 + Full Text 0.4，每通道候选池为 Top-K 的 4 倍；HNSW 采用 `m=32`、`ef_construction=200`、`ef_search=200`。1,000 条合成记录和 4 组组合相关场景的 Top-5 平均与最低 Recall 均为 100%，执行计划同时命中 GIN 与 HNSW。首次默认 HNSW 参数测试暴露近邻漏召回，参数调整后通过；这些参数仍须由真实 Golden Dataset 做最终校准。

P03-A10 已验证外部可配置 Reranker：按[阿里云百炼官方 Rerank 文档](https://help.aliyun.com/en/model-studio/rerank)使用华北 2（北京）OpenAI-compatible `/reranks` 和 `qwen3-rerank`，以固定非客户文本完成真实 5→3 重排，两个预期相关项位列前二。适配层只依赖配置，不由业务模块直连厂商 SDK；HTTP 429、超时和无效响应均 fail-open 到原候选顺序，并仅记录脱敏错误码。

P03-A14 已验证 Context Builder 到统一 AIService：按相关度和字符预算生成带 ChunkId/来源定位的上下文，Prompt 以 `PromptId + Version + OutputSchema` 独立传入；实际调用链为 `RagAIOrchestrator → AIService → ModelRouter → ProviderAdapter`，结构化输出仍由 POC-04 AIService 校验。RAG 模块不包含 HTTP、厂商 SDK 或具体 ProviderAdapter 调用。

P03-A15 已验证异常与空结果：数据库不可用时返回可重试状态并在 AI 调用前停止；空结果或最高检索分低于 PoC 阈值 0.5 时返回 `NO_RELIABLE_MATCH`，不让模型凭空作答；Reranker 不可用时按原候选顺序 fail-open；AI 不可用时返回脱敏错误码和重试属性。异常消息、查询、候选正文和 AI 输出均不进入提交证据。

## Confirmation UX Prototype

R4 延续对用户体验的 Phase 0 验证，不是正式项目交接 `ActionItem` 模块。它验证“AI 发现 → 打开证据 → 人工确认/修改/退回”的交互方式：

- 主清单只显示问题、风险、AI 建议、需确认事项和人工决定。
- 每条记录可打开同目录本地证据页；PDF 携带页码，Office 文档显示精确段落、表格或幻灯片定位并可打开原文件。
- 人工输入列明确标色并说明需要维护的内容。
- 新候选的技术底稿不重复展示大段正文；完整上下文保存在本地证据定位器和候选 JSON 中。
- R4 的 120 条处理结果默认留空，不把规则建议预先写成人工决定。
- 用户更新后的 R4 为 120 条“修改后确认”，每条均包含实质性“人工复核”和明确“结论”；锁定任务中的查询、来源类型、答案术语和引用定位保持完整。严格导入得到 120 条 `APPROVED`、0 个校验问题。
- 对原分类为 `HUMAN_CONFIRMATION_REQUIRED` 的记录，只在人工结论含有明确判定短语时确定性映射为 `INSUFFICIENT_INFORMATION` 或 `NO_RELIABLE_MATCH`，其余保留原分类；覆盖审计最终包含六类允许结果。
- 详细边界和正式模块建议见 `confirmation-ux-prototype.md`。

## Local Review Prefill

预填过程不调用外部 AI 服务，候选正文和建议内容只写入 Git 忽略的本地输出：

```powershell
python scripts/generate_review_suggestions.py `
  --candidates <本地候选集.jsonl> `
  --local-output <本地建议.json> `
  --sanitized-report <脱敏报告.json>
```

生成器不会填写审核人或审核时间，审核状态固定为 `PENDING`。无法从锁定枚举诚实映射的来源类型保持空白，而不是自动伪造成其他类别。

## Review Import

仅检查工作簿，不生成正式数据：

```powershell
python scripts/import_review_workbook.py `
  --workbook <本地评审工作簿.xlsx> `
  --candidates <本地候选集.jsonl> `
  --report <本地脱敏报告.json> `
  --validate-only
```

正式导出还必须提供 `--output`、`--dataset-id`、`--embedding-provider`、`--embedding-model`、`--embedding-dimension` 和 `--index-version`。只有 100~200 条记录通过人工批准并满足 Schema 时才会写出文件；不完整或校验失败时不会生成正式集。

实际 Embedding 探测只从环境变量读取 Key，提交报告不含输入文本、向量值或 Secret：

```powershell
$env:PLM_POC_EMBEDDING_API_KEY = '<仅当前会话使用的百炼 Key>'
python scripts/probe_embedding_provider.py `
  --provider aliyun-model-studio-openai-compatible `
  --base-url <对应区域的 OpenAI-compatible Base URL> `
  --model qwen3.7-text-embedding `
  --dimension 1024 `
  --report <本地脱敏探测报告.json>
Remove-Item Env:PLM_POC_EMBEDDING_API_KEY
```

导出后必须执行脱敏覆盖审计；审计报告只包含数量和缺失类别：

```powershell
python scripts/audit_golden_dataset.py `
  --dataset <本地 Golden Dataset.json> `
  --report <本地脱敏覆盖报告.json>
```

## Metrics

|指标|目标|当前状态|
|---|---|---|
|候选评审记录|100~200 条|120 条，29/29 文档覆盖，四类来源均有候选，PASS|
|当前人工批准记录|100~200 条且字段完整|R4 严格导入 120 条 APPROVED、0 个问题，PASS|
|本地预填建议|辅助人工评审，不形成真值|120 条不同查询；120 条来源类型已确定；全部保持 PENDING|
|人工确认交互原型|证据可定位、输入有提示、原数据可追溯|R4 生成 120 个本地证据链接和 120 个原文件入口；公式错误 0；PASS_FOR_HUMAN_REVIEW|
|来源资格审计|不得将解决方案伪造为锁定来源类型|4 CONTRACT、5 TECHNICAL_AGREEMENT、19 STANDARD_CAPABILITY、1 SURVEY 文档；历史 SOLUTION 不进入本轮候选|
|Schema 合法数据集导出|100~200 条|R4 导出 120 条，Schema PASS|
|Gold Set 质量覆盖|查询、四类来源、六类分类可评估|120 个唯一查询、29 份文档、四类来源和六类结果，覆盖审计 PASS；标签一致性风险待重新评审|
|确定性 Chunk|可追溯且强制 PROJECT/ProjectId|1,695 个，PASS|
|单索引单 Embedding 模型|不可原地换模/换维度|`qwen3.7-text-embedding` 1024 维 live PASS|
|模型切换与全量重建|新 index_id、全量重建、旧向量复用 0|`text-embedding-v4` 768/v2，120/120 live rebuild，PASS；未激活|
|PostgreSQL Full Text|查询与 Top-K|4 场景、Top-5 平均/最低 Recall 100%、GIN 命中，PASS|
|pgvector 向量检索|查询与 Top-K|1,000 条、4 场景、Top-5 平均/最低 Recall 100%、HNSW 命中，PASS|
|Hybrid Retrieval|Vector + Full Text 融合与 Top-K|1,000 条、4 场景、0.6/0.4 加权融合、Top-5 平均/最低 Recall 100%、GIN/HNSW 命中，PASS|
|外部 Reranker|可配置请求、响应校验、错误与降级|百炼 `qwen3-rerank` 真实 5→3 PASS；429/超时/无效响应降级 PASS|
|Context Builder → AIService|统一网关、Prompt/Context/Trace|统一调用链与结构化输出 PASS；无 RAG 直连厂商|
|异常与空结果|DB/Reranker/AI 不可用、空结果、低可靠度|6 场景 PASS；空/低可靠度不调用 AI|
|Top-5 Recall|≥95%|60.00%（72/120），FAIL|
|分类准确率|≥90%|14.17%（17/120），FAIL|
|来源引用准确率|≥98%|50.83%（61/120），FAIL|
|PROJECT 跨项目泄漏|0|P03-A06：6 组查询、30 行结果，泄漏 0，PASS|

## Logs

- 可提交脱敏证据：`evidence/windows-11/`。
- 工作簿结构和操作边界：`review-workbook-spec.md`。
- 候选正文、原始映射和运行输出：`artifacts/poc-03/`，由 Git 忽略。
- 原始方案文件与文件名映射不进入 Git。

## Known Issues

1. P03-A11~A13 首轮真实指标均 FAIL；在用户确认标签复核与检索调优方案前不得进入下一 WBS。
2. R4 的自由文本结论没有逐条显式写回最终分类，多数标签仍继承候选阶段关键词启发式值；需重新打开标签 Gate，不能以模型输出自动改写真值。
3. 两个资料库共 10 个旧版二进制 `.doc` 尚不支持，不进入本轮候选池。
4. Windows Server 2025 与 Debian 13 尚未执行本 PoC。
5. 旧 R2/R3 历史工作簿不作为新四类来源基线；其人工填写记录被保留，但不会自动迁移成新候选的批准状态。
6. R4 是本地 UX 原型，不是正式交接待办；当前 Office 原件定位依赖“打开原文件 + 精确定位说明”，正式产品仍需内置证据查看器完成自动跳转与高亮。
7. 旧 R1 的 109 条批准记录只有 1 个唯一查询，且全部为 `SURVEY` / `STANDARD_SATISFIED`，不满足 Gold Set 覆盖要求，保留为历史失败证据。
8. P03-A04 已激活阿里云百炼 OpenAI-compatible `qwen3.7-text-embedding`、1024 维、索引 `v1` 的 PoC 绑定；它不代表正式架构冻结。
9. DeepSeek 官方资料本轮未找到 Embedding 端点；不得把现有 DeepSeek Chat Key 假定为向量服务凭据。
10. 用户指定的标准能力库已提供标准能力和调研来源；该目录用途只解决来源分类，不代表其中每条 AI 建议均已得到业务确认。

## Conclusion

POC-03 的基础链路与 Golden Dataset 覆盖已完成，但首轮真实质量门槛全部失败；当前不形成 RAG 质量通过结论。

## PASS / FAIL

`FAIL / BLOCKED_QUALITY_GATE`

## Alternative

- 推荐先在友好确认界面中新增明确的“最终分类”必填项，重新冻结 Golden Dataset 标签；随后对 Vector/FTS/融合/Reranker 各阶段做排名诊断和透明调优。
- 不得降低质量门槛、事后按模型输出改标签、泄露期望答案到 Prompt，或擅自引入独立向量库和本地模型。
