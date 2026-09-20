# POC-03 Windows 11 候选数据准备证据

## Scope

2026-09-17 至 2026-09-18 在 Windows 11 上只读处理本地历史方案、技术协议/合同和用户指定的标准能力库。原文件、原文件名、Hash、解析正文、OCR 正文、候选正文和本地映射均未提交 Git。

## Source Corpus

- 历史方案：18 个文件，17 个受支持文件解析通过，1 个旧版 `.doc` 不支持；共 13,710 个内容块。
- 技术协议/合同：18 个文件，4 个 DOCX 和 5 个扫描 PDF 解析通过，9 个旧版 `.doc` 不支持；共 46,720 个内容块。
- 5 个扫描 PDF：105 页，Tesseract 产生 45,145 个 OCR 行，Schema 错误为 0。
- 两个资料库原件不变性：36/36 PASS。
- 合并可用输入：26 个 ParsedDocument，60,430 个内容块。

## Candidate Dataset

- 确定性 Chunk：655 个，全部使用 `PROJECT` scope 和显式 ProjectId。
- 候选评审记录：120 条，覆盖 26/26 个已解析文档。
- 候选状态：全部为 `PENDING_HUMAN_REVIEW`。
- 合同/技术协议资料产生 192 个 Chunk；历史方案产生 463 个 Chunk。
- 候选正文仅保存在 `artifacts/poc-03/candidate-dataset/2026-09-17-r2/`。

## Human Review Workbook

- 已从 120 条候选生成本地 Excel 评审工作簿，包含“评审总览”和“候选评审”两张工作表。
- 工作簿初始状态为 120 条 `PENDING`、0 条 `APPROVED`、0 条可转正式集。
- 3 组下拉规则、完备性公式、冻结窗格、筛选表和条件格式已写入导出文件。
- 已渲染并检查两张工作表；导出后重新载入成功，公式错误扫描为 0。
- 工作簿含候选正文，只保存在 Git 忽略的本地 `artifacts/`；仓库仅提交 `review-workbook-result.json` 的脱敏结论。
- R2 新版本使用完全本地的确定性规则预填 120 条不同查询、答案术语、建议分类和原始引用定位，没有调用外部 AI 服务，也没有覆盖 R1。
- R2 生成时全部 120 行重置为 `PENDING`，审核人和审核时间为空；45 条 `CONTRACT` 可直接映射，75 条 `SOLUTION` 因不在锁定来源类型枚举中保持空白并高亮。
- R2 生成时导入复核为 120 行、0 条 APPROVED、0 个来源一致性问题；用户随后已完成填写，最新复核结果见“Confirmation UX Prototype”。

## Review Import Gate

- 新增本地评审表导入器，逐行核对候选编号、ProjectId、文档/Chunk、来源定位、正文和正文 Hash，不允许人工修改来源证据。
- 只转换 `APPROVED` 且查询、来源类型、分类、答案术语、确认引用、审核人和审核时间完整的记录。
- 确认引用必须来自原候选的来源定位；工作簿公式显示不作为导出依据，导入器独立重算 Gate。
- R1 历史工作簿曾得到 109 条 `APPROVED`、11 条 `PENDING` 和 0 个导入问题，但后续覆盖审计失败，该版本不作为当前评审基线。
- 25/25 单元测试通过；除原有评审导入和覆盖审计外，新增本地建议的来源映射、不可伪造 `SOLUTION` 类型、查询去重和脱敏报告测试。

## Index Binding

- P03-A04 已验证索引身份包含 provider、model、dimension 和 index_version。
- 同一 index_id 重复注册相同绑定是幂等操作；更改模型或维度会被拒绝，必须使用新 index_id。
- 已激活 PoC 绑定：阿里云百炼 OpenAI-compatible `qwen3.7-text-embedding`、1024 维、索引 `v1`。
- 使用固定非客户文本完成真实探测，请求与返回均为 1024 维；Key、输入文本、向量值和厂商响应正文均未提交。
- 安全探测合同通过模拟验证：Key 不写入报告、返回维度必须匹配、HTTP 错误不透传厂商响应正文。
- P03-A05 使用 `text-embedding-v4` 768 维创建独立 `v2` index identity；旧 `v1` 原地换模被拒绝。
- 120 条固定非客户文本通过 12 批真实调用完成 120/120 重建，返回维度均为 768，旧向量复用 0。
- `v2` 仅验证未激活；报告不含 Key、输入文本、向量值或厂商响应正文。

## Project Isolation

- Windows 11 本地 PostgreSQL 18.6 + pgvector 0.8.6 建立临时隔离 Schema，写入两个项目共 40 条合成记录。
- PROJECT 请求必须包含非空 ProjectId；缺失值在进入数据库前被拒绝。
- Vector、Full Text、Hybrid 对两个项目各执行 Top-5，共 6 个场景、30 行结果，跨项目泄漏为 0。
- 所有 SQL 使用参数化 ProjectId；注入式字符串返回 0 行，没有扩大结果范围。
- 验证结束后临时 Schema 删除，未保留合成行，也未使用客户内容。

## PostgreSQL Full Text

- PostgreSQL 18.6 使用 `simple` text search configuration；中文术语由上游以空格完成确定性规范化。
- 4 组中文合成查询、40 条记录分别执行 Top-5；平均及最低 Recall 均为 100%。
- `EXPLAIN` 确认命中表达式 GIN 索引。
- 该 PoC 不宣称 PostgreSQL 原生具备中文分词能力；不带上游术语规范化的中文检索尚未验证。
- 临时 Schema 已删除，查询文本和合成行未提交。

## pgvector Vector Retrieval

- PostgreSQL 18.6 + pgvector 0.8.6 建立 HNSW `vector_cosine_ops` 索引。
- 1,000 条合成三维向量、4 组已知近邻分别执行 Top-5；平均和最低 Recall 均为 100%。
- `EXPLAIN` 确认命中 HNSW 索引。
- 该结果只验证机制，不代表真实 PLM 语料的 P03-A11 Recall；向量值未提交，临时 Schema 已删除。

## Hybrid Retrieval

- Vector 与 Full Text 固定权重分别为 0.6 和 0.4，每通道候选池为最终 Top-K 的 4 倍。
- HNSW 使用 `m=32`、`ef_construction=200`、`ef_search=200`；默认参数首轮出现近邻漏召回，调整后 4 场景 Top-5 平均与最低 Recall 均为 100%。
- 1,000 条合成记录的执行计划同时命中表达式 GIN 与 HNSW 索引。
- 合成 ID 可提交，查询文本、向量值和合成数据库行未提交；临时 Schema 已删除。真实语料指标仍受 P03-A02 阻塞。

## External Configurable Reranker

- 官方协议：<https://help.aliyun.com/en/model-studio/rerank>；华北 2（北京）业务空间专属 `compatible-api/v1/reranks`。
- `qwen3-rerank` 使用 5 条固定非客户候选真实返回 Top-3，两个预期相关项位列前二。
- 外部服务 HTTP 429、超时、无效响应分别记录 `HTTP_429`、`NETWORK_ERROR`、`INVALID_RESPONSE`，并 fail-open 保留原始候选顺序。
- API Key 仅在进程环境变量中短暂存在；提交证据不包含 Key、查询、候选正文或响应正文。

## Context Builder to AIService

- 调用链：`RagAIOrchestrator → AIService → ModelRouter → ProviderAdapter`；验证脚本使用确定性 RecordingProvider，不重复调用真实模型。
- Context 按相关度排序，带 ChunkId 和来源定位，并受字符预算约束；PromptId、PromptVersion、ProjectId 和实际 ChunkIds 写入请求元数据。
- 结构化结果由 POC-04 AIService 按 JSON Schema 校验；RAG Context 模块不含 HTTP、厂商 SDK 或具体 ProviderAdapter。
- 提交证据不包含查询、上下文或 AI 输出正文。

## Failure and Empty-result Handling

- 数据库不可用：`RETRIEVAL_UNAVAILABLE`、可重试、AI 未调用。
- 空结果或最高检索分低于 PoC 阈值 0.5：`NO_RELIABLE_MATCH`、AI 未调用，避免无依据生成。
- Reranker 不可用：保留原检索顺序，标记 `RERANKER` 降级并继续统一 AI 链路。
- AI 不可用：`AI_UNAVAILABLE`，保留引用 ID，只输出脱敏错误码和是否可重试。
- 正常链路与上述 5 类异常/边界场景共 6 项全部 PASS；证据不含内容或异常原文。

## Dataset Export and Coverage

- 当前 R4 的 120 条 APPROVED 记录已按 `poc-03.golden.v1` 完成 Schema 合法导出；数据集只保存在 Git 忽略的本地 `artifacts/`。
- 脱敏覆盖审计：120 条记录、120 个唯一问题、29 个文档、120 个 Chunk、1 个项目。
- 来源分布为合同 20、技术协议 20、标准能力 76、调研 4；六类允许结果均有覆盖，质量覆盖判定为 `PASS`。
- 旧 R1 的 109 条导出仍只作为历史证据，不替代当前 R4。

## Privacy

- `方案库/`、`技术协议&合同/`、`标准能力库/` 和 `artifacts/` 均由 Git 忽略。
- 提交证据不含原文件名、客户名称、原始 Hash、解析正文、OCR 正文或候选正文。
- 仓库只保存脱敏文档编号、数量、类型、状态和质量边界。

## Confirmation UX Prototype

- 用户已在 R2 填写 120 行 `APPROVED`、审核人和日期；原值在 R3 技术审计页逐单元格保留，差异为 0。
- 严格 Gate 重新计算后，45 行字段完整，75 行仍缺锁定来源类型；“已批准”不能绕过必填规则。
- R3 主清单移除大段候选正文，生成 120 个“打开证据”链接和 120 条逐项维护提示。
- 本地证据定位器包含 120 个候选锚点和 120 个原文件入口；PDF 链接携带页码，Office 文件显示精确段落、表格或幻灯片定位。
- 浏览器实测 `#GD-C-0010` 可直接跳到对应证据卡；工作簿公式回读为 120 个相对 `HYPERLINK`。
- R3 阶段 POC-03 单元测试为 30/30 通过，包含“APPROVED 状态不得绕过其他必填字段”的回归用例；当前完整计数见 R5 章节。
- 该结果仅为 `PASS_FOR_UX_REVIEW`，不代表正式交接 ActionItem 模块或 P03-A02 通过。

## Source Type Eligibility Audit

- 审计脚本按原文件标题的显式“合同”或“技术协议”标识进行确定性分类，不读取 AI 推断作为正式来源类型。
- 120 条候选中，20 条合同已验证，25 条需从 `CONTRACT` 纠正为 `TECHNICAL_AGREEMENT`。
- 75 条来自历史解决方案，均不属于锁定的 `STANDARD_CAPABILITY`、`CONTRACT`、`TECHNICAL_AGREEMENT`、`SURVEY`，已标记排除而非伪造映射。
- 该历史 R2 审计当时只有 45 条合格来源，距最低 100 条差 55 条，并缺少标准能力和调研两类真实语料。
- 该历史审计本身 PASS，当时 P03-A02 状态为 `BLOCKED_MISSING_SOURCE_CORPORA`；后续状态见下节 R4 证据。

## Standard Capability Library and R4 Review Package

- 用户明确将新增目录指定为系统用户手册、标准接口文档、部署手册和调研业务表单的标准能力库。
- 20 个 DOCX 全部通过 POC-05 结构解析和 Schema 校验，原件 20/20 未改变；其中 1 个 OOXML 包含指向 `word/NULL` 的无效内部关系，解析器仅在临时副本中移除该关系后成功解析。
- 确定性分区结果为 19 份 `STANDARD_CAPABILITY`、1 份 `SURVEY`；与 4 份 `CONTRACT`、5 份 `TECHNICAL_AGREEMENT` 合并后共有 29 份合格文档。
- 新候选集含 1,695 个 Chunk、120 条候选，覆盖 29/29 文档；候选分布为合同 20、技术协议 20、标准能力 76、调研 4。
- R4 本地确认包含 120 条待确认项、120 个证据链接和 120 个原文件入口；工作簿两张表均已渲染检查，导出回读后公式错误为 0。
- 初始新候选均为 `PENDING_HUMAN_REVIEW`；工作簿、证据定位器、候选正文和原文件均在 Git 忽略目录内。
- 用户更新后的 R4 为 120 条“修改后确认”，每条均包含“人工复核”和明确“结论”，审核人和日期完整；严格导入得到 120 条 APPROVED、0 个校验问题。
- 对原分类为 `HUMAN_CONFIRMATION_REQUIRED` 的记录，导入器只依据人工结论中的明确短语做确定性覆盖：38 条转为 `INSUFFICIENT_INFORMATION`、8 条转为 `NO_RELIABLE_MATCH`，其余保留原分类。

## R5 Lightweight Label Review

- R1 失败证据保留不变；根据已批准修复路线重新打开 P03-A02 标签一致性 Gate。
- R4 人工说明中有 62 条可确定性识别的最终分类，且全部与 R4 已导出标签一致；这些记录在 R5 中只读保留，不要求重复填写。
- 剩余 58 条按 `R4 分类 × 本次 AI 分类` 归并为 7 组；主表支持一次批量确认，冲突页支持单条最终分类覆盖。
- 四张表均已导出、回读、公式扫描和渲染检查，公式错误 0；用户完成全局确认后严格导入为 120/120、问题 0。
- 严格导入器独立重算分组和生效分类；最终数据集只允许五类业务结论，`HUMAN_CONFIRMATION_REQUIRED` 仅作为工作流态且最终计数为 0。
- R5 检查点时 POC-03 全量单元测试 103/103 通过；加入 R6 严格导入校验后为 107/107；P03-A11-R4 检索契约完成后为 113/113。提交证据不含查询、审核人、客户正文、向量或逐条模型响应。

## R6 Six-case Query and Citation Review

- 用户批准方案 A；R6 范围固定为 6 条低区分度样本，只允许修订问题与引用，全部分类和其余 114 条记录保持不变。
- 三表工作簿包含一次批量确认、单条例外、36 条原核定/Top-5 对照和本地证据跳转；三张表均已渲染、导出回读，公式错误扫描为 0。
- 严格导入器对范围、只读字段和引用白名单失败关闭；当前未确认复验为 6 条 PENDING、0 个问题、不输出 R6 数据集。
- 工作簿、问题、客户文件名、内容和证据定位器只保存在 Git 忽略的 `artifacts/`；仓库仅保存脱敏状态与数量。
- 用户确认后严格导入为 120/120、待确认 0、问题 0；覆盖审计 PASS，R6 数据集继续只保存在本地忽略目录。
- 本地 OCR 规范化检索 Top-5 为 116/120（96.67%），但仅是诊断路径；用户明确授权后完成正式百炼/DeepSeek 复验，端到端 Top-5 为 72/120（60.00%），P03-A11 按正式口径 FAIL。

## Live Golden Dataset Quality

- 120 条真实质量验证完整执行：`qwen3.7-text-embedding` 1024 维、PostgreSQL 18.6/pgvector 0.8.6 Hybrid 0.6/0.4、120/120 次 `qwen3-rerank`、统一 DeepSeek AIService。
- R6 P03-A11 Top-5 Recall 为 72/120（60.00%），FAIL；精确 Chunk 命中 72 条，同文档命中 88 条。
- R6 P03-A12 分类准确率为 57/120（47.50%），FAIL；精确召回样本中 29/72 分类正确。
- R6 P03-A13 来源引用准确率为 62/120（51.67%），FAIL；越界引用 0。
- R6 分层诊断：Vector Top-20 69/120、Full Text Top-20 78/120、融合 Top-20 80/120、Reranker Top-5 72/120；瓶颈为通道召回缺失 25、融合丢失 15、重排丢失 8，另有重排恢复 9。
- 查询、正文、向量、逐条响应和 case-level 结果未提交；仓库只保留脱敏聚合指标和失败分析。

## P03-A11-R4 Retrieval Contract

- 正式候选链现按 ProjectId 与来源类型过滤，合并 Vector Top-20、Full Text Top-20、OCR 规范化词法 IDF Top-20；Vector/Full Text 继续使用 0.6/0.4。
- 检索缓存必须包含 `r4-source-filter-lexical-idf-v1` 与来源类型，旧 R6 排名不会被复用。
- Windows 11 本地 PostgreSQL 18.6/pgvector 0.8.6 回放 120 条：精确候选池 119/120（99.17%）、同文档 120/120、来源越界 0，GIN/HNSW 均命中，外部调用 0。
- 候选池规模最少 13、最多 59、平均 42.275；它不是 Reranker Top-5，P03-A11 正式状态保持 FAIL，等待获批后的新百炼重排。
- 新增 `--retrieval-only --embedding-cache <完整本地缓存>` 模式；缓存缺失或 Hash 过期时失败关闭，确保下一轮只调用 Reranker，不重新调用 Embedding，也不调用 DeepSeek。

## Result

R6 Golden Dataset 已完成严格导入、覆盖审计和真实端到端复验。P03-A11-R4 已将本地诊断能力接回统一候选链，候选池达到 119/120（99.17%）；新的真实 Reranker Top-5 尚未执行，因此 P03-A11~A13 仍保持 FAIL。

## Known Issues

1. 两个资料库共 10 个旧版二进制 `.doc` 尚不支持。
2. P03-A11~A13 已执行且全部 FAIL，不得用合成指标、同文档命中或事后改标签描述为通过。
3. Tesseract 扫描件结果尚未完成语义准确率人工标注。
4. 旧 R2/R3 是历史评审基线，不自动转化为新四类候选的人工批准状态。
5. R4 的本地证据定位器是 PoC；Office 文件尚不能从浏览器自动跳到精确段落并高亮，正式产品需由内置 Evidence Viewer 实现。
6. P03-A11-R4 候选池仍有 1 条精确 Chunk 未进入池；同文档已命中，但正式验收不能用同文档命中替代精确 Chunk。新 Reranker Top-5 未验证前不得宣称 P03-A11 通过。
