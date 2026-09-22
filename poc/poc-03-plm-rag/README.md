# POC-03 PLM RAG

## Status

`CLOSED_WITH_APPROVED_ALTERNATIVE / HOLDOUT_QUALITY_FAIL_RETAINED`

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

P0.09 候选准备链已更新：用户指定的 `标准能力库/` 20 个 DOCX 全部解析通过，确定性分区为 19 份 `STANDARD_CAPABILITY` 和 1 份 `SURVEY`；连同 4 份合同、5 份技术协议，29 个 ParsedDocument 生成 1,695 个带 PROJECT/ProjectId 和来源定位的 Chunk，并轮询抽样 120 条候选，覆盖 29/29 个文档。R5 经全局人工确认和严格导入得到 120 条 APPROVED、0 个问题，Schema 与覆盖审计 PASS；最终只保留五类业务分类，工作流态不进入 Golden 真值。P03-A04 使用百炼 `qwen3.7-text-embedding` 实测请求/返回 1024 维，索引 `v1` 绑定 PASS。

P03-A11~A13 首轮真实质量验证完整执行但未达门槛：Top-5 Recall 72/120（60.00%）、分类准确率 17/120（14.17%）、来源引用准确率 61/120（50.83%），三项均 FAIL。120/120 次重排使用百炼 `qwen3-rerank`，GIN/HNSW 均实际命中，预测无缺失、越界引用为 0。精确 Chunk 召回 72 条而同文档召回 88 条；分类在已召回样本中仍只有 10/72 正确。R4 的最终分类多数继承候选阶段关键词启发式值，已登记 Golden 标签一致性风险；不得通过事后改标签或降低门槛掩盖失败。

用户已批准按“先复核标签、再分层调优”继续。R5 轻量确认包从 R4 人工说明中确定性识别出 62 条明确最终分类，其余 58 条按 7 组规则完成全局人工确认；严格导入和防篡改校验均通过。R5 分层诊断后，扩展候选池命中 115/120（95.83%），120/120 次真实百炼重排得到 Top-5 89/120（74.17%）。进一步定位到扫描件逐字换行造成的中文术语破碎；加入 OCR 字间空白规范化和确定性词法 IDF 后，Top-5 达到 114/120（95.00%），P03-A11 达标。

剩余 6 条问题的唯一目标 Chunk 排名为 8、11、24、27、41、117；用户批准并确认方案 A 后，R6 只更新这 6 条的问题与引用，其余 114 条和全部 R5 分类保持不变。严格导入、覆盖审计均 PASS；本地确定性 Top-5 提升到 116/120（96.67%）。用户随后明确授权真实外发复验，百炼重排与 DeepSeek 预测均完成 120/120；正式端到端 Top-5、分类和引用分别为 60.00%、47.50%、51.67%，三项均 FAIL。

R6 分层诊断显示：Vector Top-20 为 69/120、Full Text Top-20 为 78/120、0.6/0.4 融合 Top-20 为 80/120，Reranker Top-5 恢复至 72/120。瓶颈包括 25 条通道召回缺失、15 条融合丢失、8 条重排丢失；同时有 9 条由重排恢复。差异说明本地 96.67% 结果所用的来源类型过滤与确定性词法 IDF 尚未进入正式端到端检索链，因此本地诊断不得覆盖正式失败结论。

P03-A11-R4 已把该诊断路径接回统一链：Vector、Full Text 和词法 IDF 各保留 Top-20，全部强制 ProjectId 与来源类型过滤；Vector/Full Text 仍按 0.6/0.4 排序，三通道稳定去重后再交给 Reranker。无外部调用的 120 条 PostgreSQL 回放候选池覆盖 119/120（99.17%），同文档覆盖 120/120，来源越界 0，候选数为 13~59。该结果只证明 Reranker 前的召回上限，正式 Top-5 仍以新百炼重排为准。

用户明确授权后，R4 对上述候选池完成 120/120 条百炼 `qwen3-rerank` 真实调用，纯语义 Top-5 为 91/120（75.83%），同文档为 107/120（89.17%）。失例表明纯语义重排会覆盖 OCR 规范化后的高置信标识符和字面证据。R5 因此采用无标签保护性融合：百炼第 1 名 + 确定性词法前 4 名；复用同批真实重排缓存后精确 Top-5 为 114/120（95.00%），同文档 118/120（98.33%），P03-A11 PASS。融合不读取金标、答案术语或 ChunkId；结果恰好达到门槛且来自同集探索调优，仍需独立留出集验证。

P03-A12-R2 已在用户明确授权后完成 Prompt v2 真实复验。120/120 条预测完整返回，Embedding 外部调用 0、当前轮 Reranker 外部调用 0，复用 120 条已获批真实重排结果；两个瞬时空/非约束响应通过逐条缓存断点续跑恢复。分类正确 51/120（42.50%），低于 90%；47 条 `INSUFFICIENT_INFORMATION` 中 30 条仍被判为 `STANDARD_SATISFIED`，6 条 `NON_STANDARD` 正确数为 0。部分抽取式问题本身未携带“满足/非标/资料不足”的业务判定目标，继续在同一验收集上调 Prompt 存在把 Golden 反向编码进规则的风险，因此 P03-A12 保持 FAIL，等待 R6 可判定性 Gate。

用户随后批准重新评审。R6 保留为历史基线，R7 对 120 条样本重新预填可判定的业务目标、五类分类建议、分类理由和可接受引用集合；工作簿包含 120 条主确认项、五类业务说明、836 条证据候选和技术底稿，原文定位 120/120。AI 建议改分类 73 条、改引用 58 条；合同、技术协议和调研材料缺少标准能力交叉证据时保守建议为资料不足，而不直接采纳失败的 Prompt v2 满足程度结论。未确认预检为 120 条 PENDING、0 个问题且不生成数据集，129/129 单元测试 PASS。本轮没有新增外部调用。R7 使用过 Prompt v2 的诊断结果，只能作为校准集；即使人工确认，也不能在同一 120 条上关闭 P03-A12/P03-A13，后续必须另建独立留出集。

独立留出集已由 49 份新增实际调研记录与既有合格来源锁定并完成严格确认：50/50 APPROVED、0 个问题，独立 `poc-03.holdout.v1` Schema 与 12/12 覆盖/隔离检查 PASS。用户明确授权后完成真实复验：2,106 个唯一 Embedding 向量、50/50 条百炼重排和 50/50 条 DeepSeek Prompt v2 预测完成，GIN/HNSW 均命中，缺失预测与越界引用均为 0。Top-5 为 49/50（98.00%）并 PASS；分类为 24/50（48.00%）、引用为 37/50（74.00%），均 FAIL。

首次数据库装载发现 17 个重复 ChunkId、22 行冗余记录。核验确认这些记录逐字段完全一致；验证器现只合并完全一致记录，同 ID 不同内容仍失败关闭。模型在 50 条中预测 44 条 `STANDARD_SATISFIED`，13 条资料不足只识别正确 1 条，10 条非标功能没有识别正确；检索命中 49 条而精确引用命中 37 条，说明下一轮主要处理业务分类语义和已召回候选中的精确证据选择。本轮留出集已成为已见测试集，后续调优不得再次用它形成未见集通过声明。

R10 本地分层诊断进一步确认：17 条合同/调研/技术协议样本检索命中 16 条而分类仅命中 1 条，能力适配标签所需的标准能力对照没有进入同来源上下文；模型 46/50 次引用第 1 名，正确证据位于第 2～5 名时只命中 2/12。13 条严格引用失例中，8 条模型引用包含全部人工答案术语，提示未来数据冻结前必须完整审查可接受引用集合。当前分数、标签和门槛均未修改。

用户同意修复方向并要求不重复本轮真实复验后，R11 完成纯离线实现：Prompt v3 显式区分文档事实确认与能力适配判断，能力适配必须同时装配需求/约定证据和标准能力证据；Evidence Selector 使用查询支持度比较候选，原始检索名次只作同分规则。所有输入继续强制 PROJECT Scope 和 ProjectId 一致，Golden Dataset 标签、答案术语、期望 Chunk、期望引用和评审信息不得进入 Prompt。10 项新增测试全部使用合成数据，本轮外部调用 0，50 条留出集未重新运行。

项目准备成果新增实施 WBS 草案 R7 和管理层汇报 R9。WBS 覆盖 5 个项目、60 项任务，其中 40 项需求交付任务保留 Requirement/Solution/Delivery/Evidence 追溯，20 项为基线、联调、验收和交接控制；不填写实名、日期或承诺工期，状态为 `NOT_FORMAL_WBS`。管理汇报共 8 页，如实呈现独立留出集 98.00%/48.00%/74.00% 与总体 FAIL。POC-03 全量 203/203 单元测试 PASS。

P03-A05 已验证模型切换纪律：保留激活的 `qwen3.7-text-embedding` 1024 维 `v1`，拒绝对旧 index_id 原地更换模型；创建独立 `text-embedding-v4` 768 维 `v2`，使用 120 条固定非客户文本执行 12 批真实请求，120/120 全量重建完成，旧向量复用数为 0。`v2` 状态为验证通过但未激活，不替换当前绑定。

P03-A06 已在本地 PostgreSQL 18.6 + pgvector 0.8.6 实测 PROJECT 强制隔离：两个项目各 20 条合成记录，Vector、Full Text、Hybrid 各执行双项目 Top-5 查询；30 行结果跨项目泄漏为 0。缺失 ProjectId 在数据库调用前被拒绝，参数注入式 ProjectId 仅作为参数处理并返回 0 行。验证结束后临时 Schema 已删除。

P03-A07 已验证 PostgreSQL Full Text：使用 `simple` 配置和上游空格分词后的中文术语，建立表达式 GIN 索引；4 组查询、40 条合成记录的 Top-5 平均和最低 Recall 均为 100%，执行计划确认使用 GIN。该结论不代表 PostgreSQL 内置中文分词，正式链路必须保留上游术语规范化步骤。

P03-A08 已验证 pgvector HNSW：1,000 条合成三维向量、4 组已知近邻执行 cosine Top-5，平均与最低 Recall 均为 100%，执行计划确认使用 HNSW。该结果验证检索机制，不替代被 P03-A02 阻塞的真实 Golden Dataset 指标。

P03-A09 已验证 Hybrid Retrieval：Vector 0.6 + Full Text 0.4，每通道候选池为 Top-K 的 4 倍；HNSW 采用 `m=32`、`ef_construction=200`、`ef_search=200`。1,000 条合成记录和 4 组组合相关场景的 Top-5 平均与最低 Recall 均为 100%，执行计划同时命中 GIN 与 HNSW。首次默认 HNSW 参数测试暴露近邻漏召回，参数调整后通过；这些参数仍须由真实 Golden Dataset 做最终校准。

P03-A10 已验证外部可配置 Reranker：按[阿里云百炼官方 Rerank 文档](https://help.aliyun.com/en/model-studio/rerank)使用华北 2（北京）业务空间专属 `compatible-api/v1/reranks` 和 `qwen3-rerank`，以固定非客户文本完成真实 5→3 重排，两个预期相关项位列前二。适配层只依赖配置，不由业务模块直连厂商 SDK；HTTP 429、超时和无效响应均 fail-open 到原候选顺序，并仅记录脱敏错误码。R6 复验确认通用 `compatible-mode/v1` 不适用于该 Reranker，返回 404 后未继续处理，并改回官方业务空间端点。

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
- R5 主表只需确认 7 组规则；62 条 R4 明确结论只读保留，58 条冲突可在独立页逐条覆盖。全局确认未选择时，导入器不会把 AI 建议转成业务真值。
- R5 导入器独立重算分组和生效分类，不信任公式缓存；查询、来源类型、R4/AI 分类组合或分组被改动时失败关闭。
- R6 主表仅有 6 条低区分度样本；选择一次“确认全部AI建议”并填写确认人/日期即可完成常规确认，单条例外才需要维护黄色列。
- R6 证据页同时展示原核定 Chunk 和 Top-5 对照，并提供原始文件入口。严格导入器只允许使用已展示的引用，逐对象验证其余 114 条未变化。
- R7 主表覆盖 120 条，可一次确认全部 AI 建议；只有例外项需要在黄色列维护人工判定目标、最终分类、引用和说明。五类业务含义单独成表，避免仅凭技术代码选择。
- R7 的证据候选页提供 836 条证据卡与原文件入口；严格导入器锁定 AI 建议字段，人工引用只能从已展示候选中选择。未确认、退回、缺少人工说明或越界引用均失败关闭。
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

R5 标签复核使用单独入口。未选择全局批量确认时命令正常生成脱敏的等待状态报告，但不会写出数据集：

```powershell
python scripts/import_r5_label_review.py `
  --workbook <本地R5轻量确认工作簿.xlsx> `
  --r4-workbook <本地R4工作簿.xlsx> `
  --golden <本地R4 Golden Dataset.json> `
  --quality <本地R1逐条质量结果.json> `
  --dataset-id poc-03-golden-2026-09-18-r5 `
  --output <本地R5 Golden Dataset.json> `
  --report <本地脱敏导入报告.json>
```

R6 六项问题与引用复核同样默认失败关闭；未选择全局或逐条确认时只生成等待状态报告：

```powershell
python scripts/import_r6_citation_review.py `
  --workbook <本地R6确认工作簿.xlsx> `
  --golden <本地R5 Golden Dataset.json> `
  --package <本地R6复核包.json> `
  --dataset-id poc-03-golden-2026-09-18-r6 `
  --output <本地R6 Golden Dataset.json> `
  --report <本地脱敏导入报告.json>
```

R7 全量语义与引用重新评审保留 R6 不变。工作簿未确认、存在退回项、人工例外缺字段或引用不在证据候选内时均不输出数据集：

```powershell
python scripts/import_r7_semantic_review.py `
  --workbook <本地R7确认工作簿.xlsx> `
  --golden <本地R6 Golden Dataset.json> `
  --package <本地R7复核包.json> `
  --dataset-id poc-03-golden-2026-09-20-r7 `
  --output <本地R7校准数据集.json> `
  --report <本地脱敏导入报告.json>
```

R7 是 AI 辅助校准集。即使导入成功，也必须另建未被 Prompt v1/v2 使用的独立留出集，才能重新执行 P03-A12/P03-A13 验收。

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

P03-A11-R4 的本地检索契约回放不调用外部模型，只复用内容 Hash 一致的本地向量缓存：

```powershell
python scripts/validate_r4_retrieval_contract.py `
  --dataset <本地R6 Golden Dataset.json> `
  --parsed-root <本地四类ParsedDocument目录> `
  --embedding-cache <本地R6向量缓存.jsonl> `
  --report <本地脱敏汇总.json> `
  --case-report <本地逐条结果.json>
```

取得明确数据外发授权后，可用现有真实质量入口的 `--retrieval-only --embedding-cache <完整本地缓存>` 模式只验证百炼 Reranker。该模式要求所有 Chunk 和查询的向量 Hash 完整匹配，缺失或过期时失败关闭，不调用 Embedding，也不向 DeepSeek 发送数据。

R5 可通过 `--reranker-cache <已获批真实R4重排缓存>` 在零外部调用下复算保护性融合。缓存只记录 case、pipeline version、来源类型和排序 ID，不保存查询、候选正文、向量或厂商响应正文；报告分别记录当前运行调用数和复用的真实结果数。

Prompt v2 本地 payload 与审计可重复生成：

```powershell
python scripts/prepare_prompt_v2_offline.py `
  --dataset <本地R6 Golden Dataset.json> `
  --parsed-root <本地四类ParsedDocument目录> `
  --retrieval-cache <本地R5检索缓存.jsonl> `
  --payload-output <Git忽略的本地payload.jsonl> `
  --report-output <本地脱敏审计.json>
```

取得当轮 DeepSeek 数据外发授权后，真实质量入口使用 `--prediction-only --embedding-cache <完整缓存> --reranker-cache <完整R5缓存>`。任一缓存缺失、版本不匹配或 Hash 过期时失败关闭，确保本轮不调用百炼 Embedding/Reranker，只调用 DeepSeek。

## Metrics

|指标|目标|当前状态|
|---|---|---|
|候选评审记录|100~200 条|120 条，29/29 文档覆盖，四类来源均有候选，PASS|
|当前人工批准记录|100~200 条且字段完整|R6 已严格导入 120/120、问题 0；114 条及全部 R5 分类保持不变|
|本地预填建议|辅助人工评审，不形成真值|120 条不同查询；120 条来源类型已确定；全部保持 PENDING|
|人工确认交互原型|证据可定位、输入有提示、原数据可追溯|R5 四表轻量确认包：62 条明确结论、58 条冲突/7 组、单条例外覆盖；公式错误 0；全局确认与严格导入 PASS|
|来源资格审计|不得将解决方案伪造为锁定来源类型|4 CONTRACT、5 TECHNICAL_AGREEMENT、19 STANDARD_CAPABILITY、1 SURVEY 文档；历史 SOLUTION 不进入本轮候选|
|Schema 合法数据集导出|100~200 条|R4 导出 120 条，Schema PASS|
|Gold Set 质量覆盖|查询、四类来源、五类最终业务分类可评估|120 个唯一查询、29 份文档、四类来源和五类结果；R5 Schema/覆盖审计 PASS|
|确定性 Chunk|可追溯且强制 PROJECT/ProjectId|1,695 个，PASS|
|单索引单 Embedding 模型|不可原地换模/换维度|`qwen3.7-text-embedding` 1024 维 live PASS|
|模型切换与全量重建|新 index_id、全量重建、旧向量复用 0|`text-embedding-v4` 768/v2，120/120 live rebuild，PASS；未激活|
|PostgreSQL Full Text|查询与 Top-K|4 场景、Top-5 平均/最低 Recall 100%、GIN 命中，PASS|
|pgvector 向量检索|查询与 Top-K|1,000 条、4 场景、Top-5 平均/最低 Recall 100%、HNSW 命中，PASS|
|Hybrid Retrieval|Vector + Full Text 融合与 Top-K|1,000 条、4 场景、0.6/0.4 加权融合、Top-5 平均/最低 Recall 100%、GIN/HNSW 命中，PASS|
|外部 Reranker|可配置请求、响应校验、错误与降级|百炼业务空间专属 `compatible-api/v1` + `qwen3-rerank` 真实 5→3 PASS；429/超时/无效响应降级 PASS|
|Context Builder → AIService|统一网关、Prompt/Context/Trace|统一调用链与结构化输出 PASS；无 RAG 直连厂商|
|异常与空结果|DB/Reranker/AI 不可用、空结果、低可靠度|6 场景 PASS；空/低可靠度不调用 AI|
|Top-5 Recall|≥95%|R4 真实百炼纯重排 91/120（75.83%）；R5 保护性融合 114/120（95.00%），同文档 118/120（98.33%），P03-A11 PASS；独立留出集待验证|
|分类准确率|≥90%|Prompt v2 DeepSeek 51/120（42.50%），FAIL；120/120 预测完整，越界引用 0|
|来源引用准确率|≥98%|Prompt v2 真实引用 62/120（51.67%），FAIL；R5 检索精确命中 114/120，但模型选择唯一期望 Chunk 仅 62 条|
|PROJECT 跨项目泄漏|0|P03-A06：6 组查询、30 行结果，泄漏 0，PASS|

## Logs

- 可提交脱敏证据：`evidence/windows-11/`。
- 工作簿结构和操作边界：`review-workbook-spec.md`。
- 候选正文、原始映射和运行输出：`artifacts/poc-03/`，由 Git 忽略。
- 原始方案文件与文件名映射不进入 Git。

## Independent Holdout Source Lock

- 49 份新增资料按“实际客户调研记录”处理：本地解析 506 个内容块、282,819 字符，文件 Hash 与解析正文 Hash 均未与历史语料重复。
- 调研记录是客户需求与结论的主要事实证据；调研业务表单只用于问题清单、字段和覆盖范围参考，不作为客户事实，也不能满足独立留出集的调研配额。
- 50 条来源锁按标准能力/合同/技术协议/调研 33/7/8/2 完成；历史暴露 Chunk、相邻 Source Locator、重复正文和 13 个表单参考块均被排除。
- 调研类 2/2 均来自新的实际客户调研记录。锁文件、候选正文、源文件名、Hash 和客户资料仍只保存在 Git 忽略的 `artifacts/`。
- 来源锁不等于质量 Gate 通过；仍需生成问题/分类/引用建议、完成人工确认，并在当轮明确授权后执行真实外部模型复验。

## Independent Holdout AI Review R1

- 用户明确授权后，仅将 50 条锁定候选编号、来源类型、证据角色和候选正文发送至 DeepSeek；未发送原文件名、本地路径或 Hash，Embedding/Reranker 调用 0。
- AI 建议 50/50 完成，问题 50/50 唯一，五类分类全部覆盖；分布为标准满足 23、部分满足 3、非标准 10、资料不足 13、无可靠匹配 1。
- DeepSeek V4 默认开启思考模式，首轮结构化输出会因预算消耗返回空正文；统一 AIService 新增显式 `thinking="disabled"` 后走受约束 JSON 恢复。累计请求尝试 227，所有失败请求均未写入建议。
- 9 条证据摘录和 9 条关键词存在模型同义改写，系统未接受改写文本，而是从本地候选正文确定性截取连续原文，并在技术底稿中标记修复。
- R1 工作簿包含“确认清单、分类说明、技术底稿”三表。主表不展示大段正文；支持一次批量确认、单条修改/退回和“打开证据”。原文件定位 50/50，三表渲染、公式错误扫描和交互回归均通过。
- 用户已完成全局人工确认；确认结果须经下述严格导入和覆盖审计后才形成独立留出集真值。

## Independent Holdout Strict Import R1

- 严格导入器独立重算 50 行生效状态，不信任工作簿公式缓存；结果为 50 APPROVED、0 PENDING、0 RETURNED、0 问题，人工例外 0。
- 新增独立 `poc-03.holdout.v1` Schema。留出集保持为单独的 50 条验收集，不与已经参与 Prompt/检索调优的 120 条 R7.1 校准集合并。
- 12 项覆盖与隔离检查全部 PASS：50 个唯一问题、候选和 Chunk，四类来源配额 33/7/8/2，五类分类分布 23/3/10/13/1，全部 PROJECT 隔离且引用与来源锁一致。
- POC-03 全量 151/151 单元测试 PASS。本轮只执行本地导入和审计，Embedding、Reranker、DeepSeek 外部调用均为 0。
- 工作簿、审核人、问题、答案术语、客户正文、源文件名和完整留出集继续只保存在 Git 忽略的 `artifacts/`；仓库仅保存脱敏数量、状态和检查结果。

## Local Project Analysis Confirmation Package R1

- 新增通用本地分析包生成器 `scripts/build_project_analysis_package.py` 和 Artifact Tool 工作簿生成器 `scripts/build_project_analysis_workbook.mjs`，按项目组织标准功能、非标功能、差异项、待确认项和推荐调研大纲。
- 证据优先级固定为：实际调研记录 > 合同/技术协议 > 风险评估 > 既有方案 > 调研业务表单；调研业务表单只作提问参考，不能替代客户实际表达。
- 主工作簿不复制大段原文。每条 AI 建议提供本地“打开证据”入口，证据页再链接原始本地文件；用户先在“项目总览”做项目级判断，只有需要调优时才逐条维护黄色列。
- 客户项目名、原文件名、摘录、确认工作簿、证据定位页和分析 JSON 全部保存在 Git 忽略的 `artifacts/project-analysis/`，仓库只提交通用程序、测试和脱敏说明。
- 本轮未调用外部模型；任何分析结论在人工确认前均为 `AWAITING_HUMAN_CONFIRMATION`，不得转成正式需求、正式方案或合同事实。
- 旧版 `.doc` 通过本机 Microsoft Word 生成不修改原件的本地 DOCX 分析副本，再复用 POC-05 ParsedDocument 解析链。该辅助路径不改变 POC-05 对 `.doc` 直接解析仍不支持的结论。
- 工作簿 8/8 页签完成渲染、回读、公式错误扫描和输入交互回归；POC-03 全量 155/155 单元测试 PASS。

## Local Survey Execution Package R2

- 用户已整体确认 R1 项目分析包。确认记录绑定 R1 指纹，仅表示可作为下一步调研执行基线；不把 AI 建议自动转成正式需求/方案，也不构成独立留出集数据外发授权。
- 新增通用执行包生成器 `scripts/build_survey_execution_package.py`，按资料成熟度将 12 个项目分为 4 批，形成 60 条调研任务、39 条 P0 任务和 24 条待决策记录。
- 新增 Artifact Tool 工作簿生成器 `scripts/build_survey_execution_workbook.mjs`。工作簿包含“执行看板、调研任务、决策追踪、使用说明”四页；黄色列明确提示负责人、日期、状态、最终决策和备注等人工维护项。
- 调研任务和决策记录均保留本地“打开证据”入口，回到 R1 证据定位页和原始文件。第 3/4 批项目必须先补真实业务调研，不得直接用既有方案替代客户事实。
- 4/4 页签完成渲染、回读、公式错误扫描和输入交互回归；任务完成与决策关闭会同步更新看板统计。POC-03 全量 160/160 单元测试 PASS，本轮外部模型调用 0。
- 客户项目名、任务内容、工作簿、证据页和确认记录继续只保存在 Git 忽略的 `artifacts/project-analysis/`；仓库仅同步通用脚手架、测试和脱敏说明。

## Local Desktop Discovery and Requirement Candidates R3

- 因第一批暂时无法安排客户访谈，将 R2 第 1 批的 5 个项目转换为“基于现有资料的桌面调研”；每条结果均标注证据等级、资料局限和是否需要后续确认，不把资料推断写成客户已确认事实。
- 新增通用包生成器 `scripts/build_desktop_discovery_requirements.py`，校验 R1/R2 指纹后形成 25 条桌面调研结论、40 条需求候选和 10 条未关闭前置假设。
- 需求候选按证据与类型分为 29 条 `DRAFT_READY`、1 条 `DRAFT_WITH_ASSUMPTION` 和 10 条 `BLOCKED_BY_DECISION`；其中待确认项始终转成前置决策，不因缺少访谈而自动关闭。
- 新增 Artifact Tool 工作簿生成器 `scripts/build_desktop_discovery_workbook.mjs`，提供结果总览、桌面调研结果、需求候选、前置假设和使用说明五页，并保留本地证据跳转与黄色可选评审区。
- 5/5 页签完成渲染、回读、公式错误扫描和输入交互回归；POC-03 全量 165/165 单元测试 PASS，本轮外部模型调用 0。
- 客户项目名、原文件名、结论、候选正文、工作簿和证据页继续只保存在 Git 忽略的 `artifacts/project-analysis/`。R3 仅进入需求候选准备，不构成正式 Requirement、需求冻结或 Phase 6 开始；正式 Phase 0 Gate 与独立留出集外发授权要求不变。

## Delegated Requirement Review R4

- 用户授权 AI 代为处理普通确认、资料补充和可回滚方案选择。新增通用生成器 `scripts/build_delegated_requirement_review.py`，按证据优先、保守默认、最小影响和可回滚原则处理 R3 的 10 条前置假设。
- 10 条事项分别形成软件兼容、分期范围、项目/产品/报价版本关系、报价验收样例、PLM/SAP 主数据边界、文档迁移与下发、受控业务定义、未知外部接口、合同优先级和定制交付责任的工作基线；每条都包含纳入范围、明确排除、验收依据、风险和证据链接。
- 40 条候选全部转为 `INTERNAL_REVIEW_DRAFT`，其中 P0 30 条、P1 10 条、高风险 6 条；全部固定为 `NOT_FORMAL_REQUIREMENT`，不存在由 AI 直接升级为正式需求的路径。
- 新增 Artifact Tool 工作簿生成器 `scripts/build_delegated_requirement_review_workbook.mjs`，提供评审总览、代决策结果、需求评审稿和使用边界四页。工作簿无需用户逐条填写，并保留 50 个本地证据入口。
- 4/4 页签完成视觉检查和导出回读，50/50 证据链接公式存在，公式错误 0；POC-03 全量 170/170 单元测试 PASS，本轮外部模型调用 0。
- 客户项目名、资料依据、需求正文、工作簿和证据页继续只保存在 Git 忽略的 `artifacts/project-analysis/`。R4 解除内部分析阻塞，但不替代客户确认、Review Engine 或正式 Gate，也不改变当前 Phase 0 状态。

## Internal Solution Draft R5

- 新增通用生成器 `scripts/build_solution_draft.py`，严格接收带指纹的 R4 非正式需求评审包，并拒绝把任何正式 Requirement 混入本地草案生成链。
- 40 条需求评审稿全部形成唯一 `RequirementSolution` 草案映射：10 条标准配置、10 条非标实现、10 条差异处理和 10 条代决策工作基线专项。每条方案包含实现方式、涉及组件、方案摘要、接口/迁移/权限设计、验收方案、排除项、依赖和 Trace。
- 按 V2.1 的结构化专项划分出 11 条 `InterfaceSpec`、7 条 `MigrationSpec` 和 3 条 `PermissionDesign` 草案；接口统一经过适配层，迁移按可校验/可重跑批次执行，权限保持 ProjectId 隔离和默认拒绝。
- 新增 Artifact Tool 工作簿生成器 `scripts/build_solution_draft_workbook.mjs`，提供方案总览、需求方案映射、专项设计和使用边界四页。4/4 页签完成视觉和导出回读检查，61/61 证据链接公式存在，公式错误 0。
- POC-03 全量 176/176 单元测试 PASS，本轮外部模型调用 0。所有方案保持 `SOLUTION_DRAFT_INTERNAL / NOT_FORMAL_SOLUTION`，不得跳过 Requirement Review、Solution Review 或正式 Gate。
- 客户项目名、需求与方案正文、工作簿和证据页继续只保存在 Git 忽略的 `artifacts/project-analysis/`；仓库只同步通用生成器、测试和脱敏说明。

## Final Requirement and Solution Delivery R6

- 新增通用生成器 `scripts/build_final_delivery_package.py`，同时验证 R4/R5 指纹绑定、需求—方案一一对应关系和非正式状态；不匹配、重复、缺项或正式对象混入时失败关闭。
- 5 个项目的 40 条需求—方案被整理为 W0 范围与决策收敛、W1 标准能力配置、W2 差异验证与治理、W3 非标与专项实现、W4 验收/交接/正式化五段实施路线。每条记录包含进入条件、完成证据、排除项、依赖、专项类型和 Trace。
- 汇总 21 项 `InterfaceSpec` / `MigrationSpec` / `PermissionDesign` 草案、10 条 AI 工作基线正式化待办和 30 个推荐调研主题。调研大纲以实际调研记录、需求和证据为主，业务表单只作参考。
- 新增 Artifact Tool 工作簿生成器 `scripts/build_final_delivery_workbook.mjs`，提供交付总览、需求与方案、实施路线、专项清单、正式化待办和调研大纲六页。6/6 页签完成视觉和导出回读检查，71/71 证据链接公式存在，公式错误 0。
- POC-03 全量 183/183 单元测试 PASS，本轮外部模型调用 0。R6 仅用于内部交接和项目准备，所有 Requirement、Solution 及专项仍须经过 Phase、Review 和对应冻结 Gate 才能正式化。
- 客户项目名、需求与方案正文、工作簿和证据页继续只保存在 Git 忽略的 `artifacts/project-analysis/`；仓库只同步通用生成器、测试和脱敏说明。

## Known Issues

1. R6 Golden Dataset 已确认并严格导入；P03-A11 已由 R5 保护性融合达到 114/120（95.00%）并 PASS。Prompt v2 真实分类只有 51/120（42.50%），引用 62/120（51.67%）；P03-A12/A13 仍 FAIL，并依据 `EXC-P0-006` 保留为后续质量 Gate 风险。
2. 50 条独立留出集已人工确认并完成真实 Embedding/Reranker/DeepSeek 复验；Top-5 98.00% PASS，分类 48.00% 与引用 74.00% FAIL，结果已冻结为已见测试集。
3. POC-05 仍不直接支持两个资料库中的 10 个旧版二进制 `.doc`；项目分析辅助包已用本机 Word 生成本地只读分析副本补齐内容覆盖，但该路径依赖已安装的 Microsoft Word，不属于跨平台解析能力。
4. 完整端到端质量复验只在 Windows 11 执行；Windows Server 2025 与 Debian 13 未执行 POC-03 全链，不形成对应平台质量结论。
5. 旧 R2/R3 历史工作簿不作为新四类来源基线；其人工填写记录被保留，但不会自动迁移成新候选的批准状态。
6. R4 是本地 UX 原型，不是正式交接待办；当前 Office 原件定位依赖“打开原文件 + 精确定位说明”，正式产品仍需内置证据查看器完成自动跳转与高亮。
7. 旧 R1 的 109 条批准记录只有 1 个唯一查询，且全部为 `SURVEY` / `STANDARD_SATISFIED`，不满足 Gold Set 覆盖要求，保留为历史失败证据。
8. P03-A04 已激活阿里云百炼 OpenAI-compatible `qwen3.7-text-embedding`、1024 维、索引 `v1` 的 PoC 绑定；它不代表正式架构冻结。
9. DeepSeek 官方资料本轮未找到 Embedding 端点；不得把现有 DeepSeek Chat Key 假定为向量服务凭据。
10. 标准能力库中的调研业务表单仅作参考；客户事实应优先来自实际访谈、现场交流和调研结论记录。
11. R3 桌面调研用于在无法安排访谈时形成可追溯的需求候选，不替代客户/项目经理确认；10 条前置假设保持未关闭，正式需求状态不得据此自动升级。
12. R4 已用 AI 工作基线处理上述 10 条假设并允许内部分析继续，但工作基线不是合同正式解释或客户确认；40 条需求评审稿仍须在正式 Gate 后才能版本化为正式 Requirement。
13. R5 的 40 条解决方案及 21 条专项设计均为内部草案；接口、迁移、权限和正式方案必须在资料、样例、联调/试迁移证据与对应 Review Gate 齐备后才能冻结。
14. R6 已形成可内部交接的实施路线和正式化待办，但它不等于项目实施计划冻结、正式需求/方案批准或客户签字；W0-W4 只能在相应 Phase 与 Review Gate 满足后转为正式基线。

## Conclusion

POC-03 的基础链路已完成；50 条独立留出集证明 P03-A11 Top-5 为 98.00% 并 PASS。P03-A12 分类为 48.00%、P03-A13 引用为 74.00%，仍未达到 90%/98% 门槛。R11 已完成双来源证据、Prompt v3 结构化判定与 Evidence Selector 的离线合同和合成测试。用户依据 `EXC-P0-006` 批准以 R11 + 强制人工确认作为 Phase 0 替代控制，因此允许 Gate 1 收口；历史质量 FAIL 不变，真实质量转为 Gate 3/UAT 阻塞项。

## PASS / FAIL

`CLOSED_WITH_APPROVED_ALTERNATIVE / QUALITY_METRICS_REMAIN_FAIL`

## Alternative

- 批准的 Phase 0 替代方案：冻结本轮 50 条及其 98.00%/48.00%/74.00% 结果；采用双来源证据、Prompt v3、Evidence Selector 和强制人工确认；在 Gate 3/UAT 使用全新独立留出集复验。
- 不得降低质量门槛、事后按模型输出改标签、泄露期望答案到 Prompt，或擅自引入独立向量库和本地模型。
