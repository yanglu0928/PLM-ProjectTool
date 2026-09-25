# 自主决策记录

## DEC-20260917-001

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-001|
|Date|2026-09-17|
|WBS|Repository Governance|
|Decision|启用“默认自主执行 + Gate 确认 + 异常升级”；自动执行批次和 WBS 边界检查周额度，剩余低于 20% 时保存检查点并停止新任务；允许在正确分支内自主同步 GitHub。|
|Reason|落实用户最新明确规则，减少普通确认和聊天消耗，同时保留重大变更、资源和远端安全边界。|
|Impact|后续 L1 任务自动执行，L2 记录后继续，L3/Gate 才请求确认；新增 `STATUS.md`、最小 Session 入口和额度保护。|
|Rollback|回退本决策对应提交，并恢复原有逐任务启动方式；不影响业务数据或正式技术基线。|

## DEC-20260917-002

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-002|
|Date|2026-09-17|
|WBS|P03-A02|
|Decision|来源资格审计只接受文件标题中明确的“合同”或“技术协议”作为确定性分类证据；历史解决方案不自动映射为标准能力或调研。|
|Reason|保持来源语义真实，避免为满足覆盖率把 AI 推断或目录名称写成已验证业务事实。|
|Impact|确认 20 条 CONTRACT、25 条 TECHNICAL_AGREEMENT；75 条 SOLUTION 排除。P03-A02 需要补充至少 55 条合格记录，并补齐 STANDARD_CAPABILITY、SURVEY。|
|Rollback|删除审计映射和证据，恢复全部记录为待确认；不会修改原始资料或用户工作簿。|

## DEC-20260917-003

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-003|
|Date|2026-09-17|
|WBS|P03-A05|
|Decision|使用百炼 `text-embedding-v4` 768 维作为换模重建验证目标，创建独立 `v2` index identity；保持当前 `v1` 激活，不自动切换。|
|Reason|官方文档和当前华北 2 工作区均支持该模型与维度，可同时验证模型和维度变化；独立索引满足既定不可原地换模规则。|
|Impact|120 条非客户合成记录完成真实全量重建；新增验证制品，不改变正式架构或当前激活绑定。|
|Rollback|删除 `v2` 验证制品即可；`v1` 未被修改。|

## DEC-20260917-004

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-004|
|Date|2026-09-17|
|WBS|P03-A06|
|Decision|所有 PROJECT Vector、Full Text、Hybrid SQL 在各自最内层查询强制使用参数化 `project_id = %(project_id)s`；缺失 ProjectId 在 Repository 调用前拒绝。|
|Reason|只在外层过滤可能让候选集、排序或中间结果接触其他项目数据；参数化内层过滤能同时控制隔离和注入风险。|
|Impact|6 个双项目检索场景跨项目泄漏为 0；形成后续 RetrievalService/Repository 的 PoC 约束。|
|Rollback|回退 PoC 查询实现和证据；不影响正式数据库，因为临时 Schema 已删除。|

## DEC-20260917-005

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-005|
|Date|2026-09-17|
|WBS|P03-A07|
|Decision|PoC Full Text 使用 PostgreSQL `simple` 配置和上游空格分词后的中文术语，并为相同表达式建立 GIN 索引。|
|Reason|PostgreSQL 内置配置不提供可靠中文分词；上游规范化无需引入新第三方组件，且能验证锁定的 PostgreSQL FTS 链路。|
|Impact|4 组 Top-5 Recall 100%，但正式链路必须保留术语规范化，不得把结果解释为数据库原生中文分词。|
|Rollback|删除 PoC FTS 脚本与证据；临时 Schema 已删除。|

## DEC-20260917-006

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-006|
|Date|2026-09-17|
|WBS|P03-A08|
|Decision|pgvector PoC 使用 HNSW + `vector_cosine_ops`，以 1,000 条合成向量和 4 组确定性近邻验证 Top-5。|
|Reason|与 POC-02 已验证索引方法一致，可隔离验证 RAG Repository 的向量 Top-K 行为和执行计划。|
|Impact|合成 Top-5 平均/最低 Recall 100%；不改变当前 1024 维真实索引绑定，也不形成真实语料质量结论。|
|Rollback|删除向量验证脚本与证据；临时 Schema 已删除。|

## DEC-20260917-007

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-007|
|Date|2026-09-17|
|WBS|P03-A09|
|Decision|Hybrid PoC 使用 Vector 0.6 + Full Text 0.4 的固定加权融合；每通道候选池取 Top-K 的 4 倍，并将 HNSW 基线设为 `m=32`、`ef_construction=200`、`ef_search=200`。|
|Reason|直接用最终 Top-K 作为候选池会截断并列结果；默认 HNSW 构建/搜索参数在组合数据上出现近邻漏召回。扩大候选池并提高索引构建与搜索深度后，4 组场景稳定召回全部组合相关项。|
|Impact|合成数据 Top-5 平均/最低 Recall 达到 100%，GIN 与 HNSW 均被使用；参数只是 PoC 基线，正式值仍需真实 Golden Dataset 校准。|
|Rollback|回退 Hybrid 查询、验证脚本和证据；临时 Schema 已删除，不影响正式数据库。|

## DEC-20260917-008

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-008|
|Date|2026-09-17|
|WBS|P03-A10|
|Decision|Reranker 采用可配置 provider/base URL/model/timeout，并通过统一适配层调用；PoC 选择百炼华北 2 的 `qwen3-rerank` OpenAI-compatible `/reranks`。外部失败默认 fail-open，保留检索原顺序并记录脱敏错误码。|
|Reason|官方文档将 `qwen3-rerank`列为当前文本 RAG 排序模型；可配置适配与 fail-open 能避免厂商绑定，并在限流或暂时不可用时保持基础检索可用。|
|Impact|真实 5→3 重排通过；429、超时和响应异常降级通过。业务模块仍不得直接调用厂商 SDK，正式启用策略需在 API/架构冻结时确认。|
|Rollback|移除 PoC Reranker 适配、脚本和证据；没有持久化业务数据或厂商响应正文。|

## DEC-20260917-009

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-009|
|Date|2026-09-17|
|WBS|P03-A14|
|Decision|Context Builder 只负责排序、预算、引用封装和 Trace 元数据；LLM 调用必须通过 POC-04 `AIService → ModelRouter → ProviderAdapter`。Prompt 以版本化定义传入，不写散落的业务内 Prompt 或厂商条件分支。|
|Reason|落实统一 RAG 和 AI Gateway 边界，并确保每次回答可追溯 ProjectId、Prompt 版本与实际 Chunk 来源。|
|Impact|Context 到统一 AIService 的确定性链路通过，结构化输出由 AIService 校验；该 PoC 不冻结正式 API Contract。|
|Rollback|移除 Context Builder/Orchestrator PoC、测试和证据；不影响 POC-04 网关。|

## DEC-20260917-010

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-010|
|Date|2026-09-17|
|WBS|P03-A15|
|Decision|PoC 将最高检索分 0.5 设为“可进入 AI”的最低可靠度；空结果或低于阈值时禁止调用 AI。数据库失败直接停止，Reranker 失败 fail-open，AI 失败返回脱敏错误码和重试属性。|
|Reason|无证据仍调用模型会产生不可追溯答案；Reranker 是增强步骤，可降级，而检索数据库和最终 AI 的失败语义不同，应分别处理。|
|Impact|6 个成功/异常场景全部通过；0.5 只是合成 PoC 阈值，必须由真实 Golden Dataset 校准后才能成为正式配置。|
|Rollback|移除异常编排 PoC、测试和证据；不改变 POC-04 或数据库。|

## DEC-20260918-001

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-001|
|Date|2026-09-18|
|WBS|P03-A02|
|Decision|将用户明确指定的 `标准能力库/` 中名称含“调研”的业务表单归为 `SURVEY`，其余用户手册、标准接口和部署资料归为 `STANDARD_CAPABILITY`；历史方案不用于补齐四类来源。|
|Reason|目录用途由用户明确提供，文件类型与名称可形成确定性来源证据；继续使用历史方案映射会违反来源真实性约束。|
|Impact|20 份新增文档分为 19 份 STANDARD_CAPABILITY、1 份 SURVEY；与合同/技术协议合并后形成 120 条四类候选，P03-A02 从缺少语料转为等待人工确认。|
|Rollback|删除本地分区和 R4 候选输出，恢复 P03-A02 来源缺口；不修改用户原文件或旧 R2/R3 历史制品。|

## DEC-20260918-002

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-002|
|Date|2026-09-18|
|WBS|POC-05 / P03-A02|
|Decision|DOCX 解析遇到指向 `word/NULL` 的无效内部关系时，仅在临时副本删除该无效关系后重试；不得改写来源文件，其他异常继续失败关闭。|
|Reason|该关系不是有效 OOXML 内容，但会使 python-docx 中止整个文档；限定异常文本和关系目标的最小修复可恢复结构解析，同时保护原件与未知异常边界。|
|Impact|标准能力库 20/20 DOCX 解析通过，原件 20/20 未改变；新增关系过滤回归测试和警告记录。|
|Rollback|移除临时副本修复逻辑并恢复该文档 FAIL_PARSE；用户原文件始终未被修改。|

## DEC-20260918-003

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-003|
|Date|2026-09-18|
|WBS|P03-A02|
|Decision|R4 的“修改后确认”只有在补充说明不少于 20 个字符且同时包含“人工复核：”和“结论：”，并且锁定任务的查询、来源类型、分类、答案术语、引用定位、审核人和日期完整时，才转为 APPROVED。原分类为 HUMAN_CONFIRMATION_REQUIRED 时，仅依据人工结论中的明确短语确定性映射为 INSUFFICIENT_INFORMATION 或 NO_RELIABLE_MATCH；其余分类保持不变。|
|Reason|用户更新后的 120 条记录均已形成逐项复核和明确结论，继续统一视为 PENDING 会违背“修改后确认”的业务语义；同时必须防止空泛说明绕过 Golden Dataset 必填 Gate，并避免 AI 自行扩大人工结论。|
|Impact|120 条记录通过严格导入；38 条明确证据不足的记录映射为 INSUFFICIENT_INFORMATION，8 条明确无可靠业务匹配的记录映射为 NO_RELIABLE_MATCH，最终覆盖四类来源和六类结果。人工原文和数据集仍只保存在 Git 忽略的本地目录。|
|Rollback|恢复“修改后确认”统一 PENDING 的映射并删除当前 R4 导出；不修改用户工作簿、来源文件或历史 R1~R3 证据。|

## DEC-20260918-004

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-004|
|Date|2026-09-18|
|WBS|P03-A11~A13|
|Decision|将首轮 120 条真实 Golden Dataset 指标按原始门槛判定为 FAIL，保留脱敏失败证据；在用户确认 Quality Gate 前不降低门槛、不按模型输出事后改标签、不改变 Hybrid 0.6/0.4 或更换模型。|
|Reason|Top-5 Recall、分类准确率、来源引用准确率分别为 60.00%、14.17%、50.83%，均显著低于 95%、90%、98%；同时发现多数最终分类仍继承候选阶段关键词启发式值，需先验证标签一致性再调优。|
|Impact|POC-03 状态转为 `FAIL / BLOCKED_QUALITY_GATE`；建议先用明确的最终分类字段重新冻结 Golden Dataset，再分层诊断 Vector、FTS、融合与 Reranker 排名。|
|Rollback|无数据回滚；本决策仅记录已发生的验证事实。后续获批方案必须新建数据集/配置版本并保留本轮 R1 失败证据。|

## DEC-20260918-005

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-005|
|Date|2026-09-18|
|WBS|P03-A02-R5|
|Decision|在保留 R1 质量失败证据的前提下重新打开 Golden 标签 Gate。R5 只复用 R4 文字中可确定性识别且与已导出标签一致的 62 条明确结论；其余 58 条按“R4 分类 × 本次 AI 分类”归并为 7 组。工作簿默认保持未确认，只有人工选择全局批量确认后才按建议规则生效，单条最终分类优先于分组规则。|
|Reason|R4 的自由文本已包含部分明确人工结论，但要求用户重新逐条填写 120 条不友好；同时不能让 AI 自动把自身预测写成 Golden 真值。分组确认既保留人工 Gate，又将必要操作压缩为一次批量确认和少量例外。|
|Impact|新增四表 R5 工作簿、严格导入器和防篡改校验；当前 62 条无需重复确认，58 条等待 7 组规则确认。全局确认前不生成 R5 数据集，原始质量门槛、模型与 Hybrid 参数均不变。|
|Rollback|删除 R5 本地工作簿和导入脚手架，恢复到 R4/R1 失败检查点；不修改 R4 工作簿、R1 失败证据或用户源文件。|

## DEC-20260918-006

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-006|
|Date|2026-09-18|
|WBS|P03-A02-R5|
|Decision|R5 人工全局确认生效后，最终 Golden Dataset 只允许五类业务结论；`HUMAN_CONFIRMATION_REQUIRED` 是评审工作流态，不得作为最终分类。单条例外优先于分组规则，所有锁定来源字段继续失败关闭。|
|Reason|人工确认已将 58 条冲突记录归并为明确业务结论；把“需要确认”继续作为最终答案会混淆流程状态与业务事实，并使质量评估无法闭合。|
|Impact|R5 严格导入 120/120、问题 0，Schema 与覆盖审计 PASS；历史 R4/R1 证据保持不变。|
|Rollback|删除 R5 本地导出并恢复到等待确认状态；不修改用户工作簿或历史数据集。|

## DEC-20260918-007

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-007|
|Date|2026-09-18|
|WBS|P03-A11-R2|
|Decision|检索前对相邻中文字符之间由 OCR 插入的空白进行规范化，并增加来源类型过滤下的确定性词法 IDF 通道；保留原始 Chunk 文本、ChunkId 和来源定位，不改写证据原文。|
|Reason|扫描合同存在逐字换行，旧分词只能得到孤立单字；规范化后可恢复“合同的有效组成部分”等连续术语，同时不影响审计原文和引用身份。|
|Impact|R5 Top-5 Recall 从首轮 60.00% 提升到 95.00%（114/120），达到 P03-A11 门槛；该结果来自同一数据集的探索调优，生产声明仍需独立留出集。|
|Rollback|移除 OCR 字间空白规范化与词法通道；Chunk 和 Golden 数据无需迁移。|

## DEC-20260918-008

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-008|
|Date|2026-09-18|
|WBS|P03-A11~A13-R3|
|Decision|用户批准方案 A：对 6 条低区分度 Golden 样本生成 R6 问题与引用复核包。只允许修改这 6 条的问题和经证据页展示的引用集合；其余 114 条及全部 R5 分类逐对象保持不变。AI 建议在人工全局或单条确认前不得写入 R6 数据集。|
|Reason|6 条原问题由通用短语或 OCR 片段构成，缺少文档和业务场景，唯一目标 Chunk 排名为 8、11、24、27、41、117；修订问题比降低 98% 门槛或扩大 Context 更能保持验收语义和可追溯性。|
|Impact|新增三表 R6 轻量确认工作簿、本地证据定位器、严格导入器、防篡改与 114 条保留校验。当前状态为等待人工确认，P03-A12/A13 尚未重跑。|
|Rollback|删除 R6 本地输出和导入脚手架，恢复 R5/L3 检查点；不修改 R5 数据集、历史质量证据或用户源文件。|

## DEC-20260918-009

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-009|
|Date|2026-09-18|
|WBS|P03-A11~A13-R3 / P03-A11-R4|
|Decision|正式验收以 R6 端到端 `Hybrid → Reranker → AIService` 结果为准；本地来源过滤、OCR 空白规范化和确定性词法 IDF 的 116/120 结果仅作为诊断，不得覆盖真实链路 72/120 的失败结论。下一 WBS 在保持模型、0.6/0.4 基线权重、门槛和 R6 标签不变的前提下，把已验证的来源类型过滤与确定性词法候选通道接入端到端检索链。|
|Reason|R6 真实复验三项分别为 60.00%、47.50%、51.67%；分层诊断显示 25 条通道召回缺失、15 条融合丢失和 8 条重排丢失，而本地确定性路径为 96.67%。当前差异属于检索实现路径不一致，不能以离线旁路结果宣称正式 Gate 通过。|
|Impact|P03-A11~A13 保持 FAIL，POC-03 保持 `FAIL / BLOCKED_QUALITY_GATE`。先完成无外部调用的检索契约对齐、回归和本地排名验证；再次调用百炼或 DeepSeek 前重新取得明确的数据外发授权。|
|Rollback|移除新增候选通道和来源过滤接线，恢复 R6 真实失败检查点；不修改 R6 Golden Dataset、模型、门槛或历史证据。|

## DEC-20260920-010

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-010|
|Date|2026-09-20|
|WBS|P03-A11-R4|
|Decision|端到端候选池按 `source_type + ProjectId` 过滤，分别获取 Vector Top-20、Full Text Top-20 和 OCR 规范化词法 IDF Top-20。Vector/Full Text 继续按锁定的 0.6/0.4 排序，随后与词法通道稳定去重合并，再交给外部 Reranker。检索缓存必须携带 `r4-source-filter-lexical-idf-v1` 版本及来源类型，旧缓存不得复用。|
|Reason|旧端到端链在每通道 Top-20 后过早压缩为 20 条且未按来源类型过滤，导致通道召回和融合丢失；词法旁路 116/120 已证明对 OCR 中文有效，但必须接入统一链且不能改变既定 Hybrid 权重。|
|Impact|本地 120 条候选池精确覆盖达到 119/120（99.17%），同文档覆盖 120/120，来源越界 0，候选数 13~59；增加只运行 Hybrid/Reranker、不调用 Embedding 或 DeepSeek 的 `--retrieval-only` 验收模式，完整向量缓存缺失或 Hash 过期时失败关闭。正式 Top-5 仍需新百炼重排验证。|
|Rollback|移除第三词法候选通道、来源过滤参数、检索缓存版本和 `--retrieval-only` 分支；恢复 R6 端到端失败实现，不修改 Golden Dataset、模型或门槛。|

## DEC-20260920-011

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-011|
|Date|2026-09-20|
|WBS|P03-A11-R5|
|Decision|最终 Top-5 采用保护性融合：保留百炼 `qwen3-rerank` 第 1 名，并加入 OCR 规范化、来源类型隔离的确定性词法 IDF 前 4 名；重复项按既有顺序去重并从两路补足。排序过程只使用查询和候选正文，不读取 `expected_relevant_chunk_ids`、答案术语、人工标签或单条 ChunkId 规则。R4 的 120 条真实重排结果允许按 pipeline version 脱敏缓存并用于无外部调用的确定性复算。|
|Reason|R4 候选池精确覆盖 119/120，但纯语义重排只有 91/120；失例包括 OCR 将 `MPP` 拆成单字符，以及同一 API 文档内多个语义等价 XML 片段。纯重排会覆盖高置信字面证据，保护性融合可同时保留语义首选与 OCR/标识符敏感结果。|
|Impact|Windows 11 R6 精确 Top-5 达到 114/120（95.00%），同文档 118/120（98.33%），120/120 个重排结果均源自获批的真实百炼调用，GIN/HNSW 命中，P03-A11 PASS。该结果没有门槛余量且使用同一数据集探索调优，必须保留“独立留出集后验验证”限制；P03-A12/P03-A13 状态不变。|
|Rollback|将最终 Top-5 恢复为纯百炼排序，P03-A11 回到 R4 的 91/120（75.83%）失败结果；保留 R4/R5 脱敏证据和 Golden Dataset，不降低门槛、不修改标签。|

## DEC-20260920-012

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-012|
|Date|2026-09-20|
|WBS|P03-A12-R1|
|Decision|Prompt v2 只允许五类正式业务标签，移除工作流态 `HUMAN_CONFIRMATION_REQUIRED`；模型必须先判断 Context 与问题的匹配性，再判断证据充分性，最后判断满足程度。Context 使用 OCR 字间空白规范化后的完整 Chunk（上限 1000 字），引用只允许一个最直接 Chunk。Prediction Cache 必须绑定 `PromptId + PromptVersion`；新增 `--prediction-only` 模式，缓存不完整时失败关闭，确保复验只调用 DeepSeek。|
|Reason|v1 将六类状态一次性并列，未建立证据 Gate，且每段只取前 600 字；47 条人工确认的 `INSUFFICIENT_INFORMATION` 中有 37 条被误判为 `STANDARD_SATISFIED`，6 条 `NON_STANDARD` 全部误判。需要先消除 Prompt 定义、上下文截断和缓存串版问题，再做真实模型复验。|
|Impact|120/120 条 v2 payload 离线准备完成，每条 5 个 R5 Context；精确证据可用 114/120、同文档 118/120、来源越界 0、规范化后正文截断 0、Golden 字段泄漏 0，外部调用 0。P03-A12 仍保持 FAIL，直到新的 DeepSeek 真实准确率达到 90%。|
|Rollback|恢复 v1 Prompt 与 600 字 Context 作为历史失败实现；删除 v2 payload/报告与 `--prediction-only` 模式，不修改 R6 Golden 标签、P03-A11 结果或验收门槛。|

## DEC-20260920-013

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-013|
|Date|2026-09-20|
|WBS|P03-A12-R2 / P03-A13|
|Decision|Prompt v2 真实复验未达门槛后，不继续在同一 R6 验收集上启动 Prompt v3，也不根据模型结果修改冻结标签、唯一期望 Chunk 或 90%/98% 门槛。先升级为 L3 质量 Gate，由用户决定是否重新打开 R6 业务语义评审，为问题补充可判定的需求/结论目标、人工分类理由和可接受引用集合。|
|Reason|Prompt v2 在 Top-5 已达 114/120 的条件下，分类仍只有 51/120，引用 62/120；主要错误为 30 条 `INSUFFICIENT_INFORMATION` 被判为 `STANDARD_SATISFIED`，6 条 `NON_STANDARD` 无一命中。抽样显示若干问题只要求摘录“采用何种方式/有哪些约定”，输入中没有要求模型判断标准满足或非标的业务目标；继续同集调优会把 Golden 分布或单条答案反向编码进 Prompt，不能证明泛化能力。|
|Impact|P03-A11 保持 PASS；P03-A12/P03-A13 保持 FAIL，POC-03 保持 `BLOCKED_QUALITY_GATE`。保留本轮脱敏聚合证据，查询、Context、逐条响应和 case-level 数据继续只留在 Git 忽略目录；任何新外发复验仍需按当轮范围授权。|
|Rollback|用户若批准重新打开 R6 Gate，则生成新版本数据集和独立留出集，保留 R6 与 Prompt v1/v2 作为历史失败基线；若不批准，则以当前失败结论结束 POC-03，不伪造通过状态。|

## DEC-20260920-014

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-014|
|Date|2026-09-20|
|WBS|P03-A12-R3 / P03-A13|
|Decision|用户批准重新打开 R6 业务语义评审。保留 R6 与 Prompt v1/v2 历史证据，新建 R7 全量 120 条语义、分类与引用确认包；AI 预填可判定目标、五类分类建议、分类理由和可接受引用候选，但只有全局或单条人工确认后才允许导出 R7。|
|Reason|Prompt v2 已证明 R6 中部分抽取式问题与满足程度分类、唯一期望引用之间不可由输入稳定推导。全量重新评审比继续同集调 Prompt 或降低门槛更能修复数据定义，同时保持历史可追溯性。|
|Impact|R7 工作簿含 120 条主确认项、五类结论说明、836 条证据候选和严格技术底稿；原文定位 120/120。AI 建议变更分类 73 条、引用 58 条；合同、技术协议和调研材料缺少标准能力交叉证据时保守建议资料不足。未确认预检为 120 PENDING、0 个问题且不输出数据集；129/129 测试 PASS。R7 因已使用 Prompt v2 诊断结果，只能作为校准集，不能在同一 120 条上关闭 P03-A12/P03-A13；仍须独立留出集。|
|Rollback|删除 R7 本地输出与新增脚手架，恢复 DEC-20260920-013 检查点；R6、Prompt v1/v2、90%/98% 门槛和历史失败证据均不改变。|

## DEC-20260920-015

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-015|
|Date|2026-09-20|
|WBS|P03-A12-R4 / P03-A13|
|Decision|用户完成 R7 全局确认后，严格导入并执行 Schema 与覆盖审计。R7 导入 120/120 PASS，但五类覆盖缺少 `NON_STANDARD`，因此不把数据集标记为覆盖通过，也不为凑数伪造标签。基于原始合同中直接出现的二次开发交付证据，生成仅含 1 条的 R7.1 例外确认表；只有人工确认后才允许修订该条业务语义与分类。|
|Reason|R7 的 AI 建议偏向保守，将所有合同类事项判为资料不足，导致已确认结果没有非标准样本；同时项目规则要求五类全覆盖，且 AI 建议必须经人工确认才能成为正式业务事实。|
|Impact|R7 本地校准数据集已生成且 Schema 有效，但覆盖 Gate 保持 FAIL；R7.1 只影响 1 条，其他 119 条不重审。130/130 测试 PASS，R7.1 两张表均渲染通过、公式错误 0；未调用外部 AI。即使 R7.1 覆盖通过，该批数据仍是校准集，P03-A12/P03-A13 仍需独立留出集关闭。|
|Rollback|若用户退回 R7.1，则保持 R7 的 `NON_STANDARD=0` 和覆盖 FAIL，不修改已确认数据；若确认，则保留 R7 作为历史版本，新建 R7.1 并重跑 Schema 与覆盖审计，不覆盖 R7。|

## DEC-20260920-016

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-016|
|Date|2026-09-20|
|WBS|P03-A12-R4 / P03-A12-R5|
|Decision|严格导入用户确认的 R7.1 单条例外，保留 R7 历史版本并新建 R7.1 数据集；导入后必须同时通过 Golden Dataset Schema 与覆盖审计。R7.1 通过后只作为 Prompt/检索校准集，不使用同批 120 条关闭 P03-A12/P03-A13，下一 WBS 建立独立留出集。|
|Reason|确认项具备直接二次开发证据，且人工确认字段完整；覆盖审计要求 100~200 条、查询唯一、四类来源和五类正式分类齐全。已参与模型诊断的数据若再次作为验收集会产生后验偏差。|
|Impact|R7.1 导入 1/1、问题 0、Schema PASS；120 条覆盖审计 PASS，分类分布为 38/15/1/57/9，重复问题 0，四类来源齐全。134/134 测试 PASS，未调用外部 AI。P03-A12/P03-A13 继续保持未关闭，直到独立留出集完成真实复验。|
|Rollback|保留 R7 数据集与其覆盖失败报告，删除本地 R7.1 输出即可回到确认前状态；已确认工作簿和两版数据集均不覆盖，便于追溯。|

## DEC-20260920-017

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-017|
|Date|2026-09-20|
|WBS|P03-A12-R5 / P03-A13|
|Decision|独立留出集目标锁定为 50 条，来源配额为标准能力 33、合同 7、技术协议 8、调研 2。来源锁必须排除 R7.1 标签、Prompt v2 Context、R4/R5 检索 Top-5 与 R7 评审候选的 Chunk，并排除与污染 Chunk 共享 Source Locator 的相邻重叠块；锁定失败时不得写出部分结果或复用污染样本。|
|Reason|50 条可使分类门槛 90% 对应至少 45/50，引用门槛 98% 对应至少 49/50，同时控制人工评审规模。当前 29 份文档均出现在校准集，无法文档级隔离，只能以未见 Case、Query、Chunk 和 Source Locator 作为最强可实现隔离；调研类在严格口径和仅模型暴露口径下均为 0/2。|
|Impact|来源锁脚手架与失败关闭测试已实现，但当前 WBS 因缺少新的调研来源而阻塞。需要至少 1 份、建议 2 份此前未进入 POC-03 的真实调研业务表单；原始资料、本地锁文件和内容不提交 Git。P03-A12/P03-A13 保持未关闭，验收门槛不变。|
|Rollback|删除留出集锁定脚手架和本地补充资料入口，恢复到 R7.1 校准集检查点；不会修改 R7/R7.1、Prompt v1/v2 历史证据或 90%/98% 门槛。|

## DEC-20260920-018

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-018|
|Date|2026-09-20|
|WBS|P03-A12-R5 / P03-A13|
|Decision|调研类事实证据以面对面访谈、现场交流及其形成的实际客户调研记录为准；调研业务表单只作为问题清单、字段和覆盖范围参考，不得替代客户事实结论，也不得单独满足独立留出集的调研配额。新增资料统一标记为 `ACTUAL_CUSTOMER_DISCOVERY_RECORD`，来源锁对未带该角色的调研块失败关闭。|
|Reason|多数客户不会完整维护标准调研业务表单，模板只能表达应调查什么，不能证明客户实际说过什么、确认了什么。用户明确说明本次新增文件是面对面交流形成的调研记录，应赋予其主要事实证据地位。|
|Impact|49 份新增记录本地解析与文件/正文 Hash 去重全部通过；50 条来源锁按 33/7/8/2 完成，历史表单的 13 个调研块被排除，调研 2/2 均来自新的实际记录。141/141 测试 PASS，外部 AI 调用 0。P03-A12/P03-A13 仍需独立问题、标签、引用人工确认和真实复验。|
|Rollback|移除证据角色强制校验会允许模板再次进入调研配额，因此仅能通过新的正式决策回滚；原始资料、R7/R7.1 和历史失败证据均不修改。|

## DEC-20260920-019

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-019|
|Date|2026-09-20|
|WBS|P03-A12-R6 / P03-A13|
|Decision|在用户当轮明确授权范围内，仅将 50 条锁定候选编号、来源类型、证据角色和正文发送至 DeepSeek，生成问题、五类分类、理由、关键词和摘录建议。DeepSeek V4 结构化短任务通过统一 AIService 显式关闭思考模式；模型同义改写的摘录和关键词不得作为引用，必须由本地原文确定性替换并标记。全部建议仍保持待人工确认。|
|Reason|当前 DeepSeek V4 默认启用思考模式，JSON 模式多次耗尽输出预算并返回空正文；显式非思考模式符合官方接口能力，也保持业务模块只调用 AIService。引用必须逐字落地，不能把模型改写当成原文证据。|
|Impact|50/50 建议完成、问题 50/50 唯一、五类分类全覆盖，分布 23/3/10/13/1；累计请求尝试 227，Embedding/Reranker 调用 0。9 条摘录和 9 条关键词完成本地原文修复。R1 工作簿三表渲染、公式错误 0、50/50 原文定位及批量/例外交互回归 PASS；POC-03 146/146、POC-04 12/12 测试 PASS。P03-A12/P03-A13 状态不变，等待人工确认。|
|Rollback|删除本地 R1 建议缓存、工作簿和证据页即可回到 50 条来源锁检查点；若移除 DeepSeek V4 非思考开关，结构化短任务将恢复空正文风险。历史 R7/R7.1、来源锁和质量门槛均不修改。|

## DEC-20260921-020

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-020|
|Date|2026-09-21|
|WBS|P03-A12-R7 / P03-A13|
|Decision|将人工确认的 50 条独立留出样本保存为单独的 `poc-03.holdout.v1` 验收数据集，不与已经参与 Prompt 和检索调优的 120 条 R7.1 校准集合并。导入器必须独立重算生效状态，锁定确认表和技术底稿的来源字段，并同时验证 50 条固定范围、四类来源配额、五类分类、唯一问题/候选/Chunk、PROJECT 隔离和引用锁对齐。|
|Reason|沿用 Golden Dataset Schema 会要求 100~200 条并诱导把独立样本并入校准集，从而破坏独立验收边界。独立 Schema 可以复用相同业务字段，同时把来源锁指纹、配额和隔离属性设为可验证约束。|
|Impact|实际导入 50/50 APPROVED、0 PENDING、0 RETURNED、0 问题，人工例外 0；Schema 和 12/12 覆盖/隔离检查 PASS，POC-03 151/151 测试 PASS。完整数据集、问题、答案术语、审核人、客户正文和源文件名继续只存在于 Git 忽略目录。P03-A12/P03-A13 仍保持 FAIL，直到独立真实复验达到 90%/98%。|
|Rollback|删除本地独立留出集输出、新 Schema 和导入脚手架，可回到已确认工作簿与来源锁检查点；不会修改 R7/R7.1 校准集、历史 Prompt 结果、来源锁或质量门槛。|

## DEC-20260921-021

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-021|
|Date|2026-09-21|
|WBS|项目分析辅助 R2（Phase 0 本地成果）|
|Decision|将用户对 R1 的整体认可登记为“可作为调研执行输入基线”，并用确定性规则生成 R2：优先依据真实调研与合同/技术约束的组合和资料数量划分四个执行批次；范围、合同、接口、数据迁移、环境、权限、安全、合规、验收、切换和上线类主题标为 P0；R1 待确认项转为独立决策记录。|
|Reason|用户需要直接进入下一步执行，而不是继续逐条填写分析表。确定性分批和优先级便于安排访谈，同时保留证据入口和人工维护字段，避免把方案资料或 AI 建议误当客户事实。|
|Impact|12 个项目形成 60 条调研任务、39 条 P0 和 24 条决策记录；第 3/4 批明确要求先补真实业务调研。工作簿包含看板、任务、决策和说明四页，4/4 渲染、回读、公式与交互验证 PASS；POC-03 160/160 测试 PASS。客户数据与成品不提交，本轮外部调用 0，独立留出集外发 Gate 不变。|
|Rollback|删除 R2 本地输出和新增通用生成器即可回到已确认的 R1；R1 指纹、历史 PoC 证据、质量门槛及当前 HOLDOUT_LIVE_DATA_EGRESS Gate 均不改变。|

## DEC-20260921-022

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-022|
|Date|2026-09-21|
|WBS|项目分析辅助 R3（Phase 0 本地成果）|
|Decision|第一批无法安排客户访谈时，允许以已确认 R1 和 R2 为输入执行桌面调研，并生成带证据等级、局限声明和 TraceLink 的需求候选。标准/非标/差异项仅在有实际调研、合同或技术协议证据时标为可评审；仅有方案/风险资料时保留工作假设；所有待确认项均保持为未关闭前置决策。|
|Reason|项目需要进入下一分析环节，但现阶段不能获得新的客户访谈。桌面调研可以利用已有资料持续推进，同时必须显式隔离“资料事实、资料推断、工作假设和客户确认”，避免制造不存在的调研结论。|
|Impact|第 1 批 5 个项目形成 25 条桌面调研结论、40 条需求候选和 10 条未关闭前置假设；29 条可进入需求评审、1 条带工作假设、10 条受前置决策阻塞。工作簿 5/5 页签渲染、回读、公式和交互验证 PASS，POC-03 165/165 测试 PASS。本决策不形成正式 Requirement、不触发需求冻结或 Phase 6，也不改变独立留出集数据外发 Gate。|
|Rollback|删除 R3 本地输出和新增通用生成器即可回到 R2 调研执行计划；R1/R2 指纹、正式 Phase 0 状态、历史 PoC 证据、质量门槛及 HOLDOUT_LIVE_DATA_EGRESS Gate 均不改变。|

## DEC-20260921-023

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-023|
|Date|2026-09-21|
|WBS|后续项目分析与实施辅助工作|
|Decision|用户授权 AI 代为处理后续普通确认、资料缺口补全、候选项取舍和可回滚方案选择。AI 按“已有证据优先、保守默认、最小影响、可追溯、可回滚”原则直接形成推荐结论并继续执行，不再要求用户逐项填写或确认；证据不足时保留假设标识和 TraceLink。|
|Reason|用户当前无法投入时间逐项确认，希望项目连续推进，同时避免将未验证推断伪装成客户事实。将代决策范围和例外固化，可减少重复交互并维持审计边界。|
|Impact|后续需求候选收敛、普通字段补充、批次安排、文档结构和非破坏性实现选择可由 AI 自主决定并登记。该授权不替代正式 Gate、客户数据外发、安全/License 核心机制、已锁定基线变更、删除已确认 Scope、Secret 使用或不可逆外部操作所需的专项确认；周额度低于 20% 时仍按保护规则停止新任务。|
|Rollback|用户可随时撤销或缩小代决策范围；撤销前已登记的可回滚决策保留历史记录，未进入正式 Gate 的候选结论不自动升级为正式业务事实。|

## DEC-20260921-024

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-024|
|Date|2026-09-21|
|WBS|项目分析辅助 R4（Phase 0 本地成果）|
|Decision|按 DEC-20260921-023 的用户授权，将 R3 的 10 条前置假设分别映射到可复用的保守决策规则，并采用工作基线解除内部分析阻塞。规则必须同时给出纳入范围、明确排除、验收依据、风险和证据链接；受影响候选只能转成内部需求评审稿，统一标记为 `NOT_FORMAL_REQUIREMENT`。|
|Reason|用户要求后续普通确认和资料补充由 AI 代为决定。结构化工作基线可以让标准能力匹配和解决方案分析继续，同时保留未知项、合同解释和客户确认边界，避免概括授权越过正式 Gate。|
|Impact|第一批 5 个项目的 10 条前置假设全部匹配到专用规则，无兜底项；40 条候选全部进入内部需求评审稿，其中 P0 30、P1 10、高风险 6。工作簿 4/4 页签完成视觉和回读检查，50 个证据链接完整、公式错误 0，POC-03 170/170 测试 PASS。本轮外部调用 0，正式 Phase 0 与 HOLDOUT_LIVE_DATA_EGRESS Gate 均不改变。|
|Rollback|删除 R4 本地输出和新增通用生成器即可回到 R3；R3 指纹、原前置假设、客户资料、正式 Gate、历史 PoC 证据和质量门槛均不修改。|

## DEC-20260921-025

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-025|
|Date|2026-09-21|
|WBS|项目分析辅助 R5（Phase 0 本地成果）|
|Decision|将 R4 的 40 条内部需求评审稿一一映射为解决方案草案。标准功能优先使用标准配置；非标功能按接口适配、迁移链路、安全扩展或领域扩展实现；差异项优先采用兼容控制、数据/规则治理或受控流程扩展；代决策事项继承 R4 工作基线。接口、迁移和权限方案另生成结构化专项草案，全部标记为 `NOT_FORMAL_SOLUTION`。|
|Reason|下一环节需要把标准、非标、接口和差异结论转为可实施方案，同时不能在 Phase 0 或需求未正式化时创建正式 Solution。确定性映射和专项设计能保持 Requirement→Solution→Evidence Trace，并避免业务模块绕过统一适配、权限和审计边界。|
|Impact|5 个项目形成 40 条需求—方案映射：标准配置 10、非标实现 10、差异处理 10、工作基线专项 10；结构化专项包括 InterfaceSpec 11、MigrationSpec 7、PermissionDesign 3，高风险方案 6。工作簿 4/4 页签视觉和回读通过，61 个证据链接完整、公式错误 0，POC-03 176/176 测试 PASS。本轮外部调用 0，正式 Phase 0 与 HOLDOUT_LIVE_DATA_EGRESS Gate 均不改变。|
|Rollback|删除 R5 本地输出和新增通用生成器即可回到 R4；R4 指纹、需求评审稿、代决策记录、客户资料、正式 Gate 和历史 PoC 证据均不修改。|

## DEC-20260921-026

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-026|
|Date|2026-09-21|
|WBS|项目分析辅助 R6（Phase 0 本地成果）|
|Decision|把 R4 需求评审稿与 R5 解决方案草案按指纹和唯一 Trace 整合为内部交付包，并采用 W0 范围与决策收敛、W1 标准能力配置、W2 差异验证与治理、W3 非标与专项实现、W4 验收/交接/正式化的顺序组织后续工作。10 条 AI 代决策单列为正式化待办，21 项接口/迁移/权限设计单列为专项，30 个调研主题继续以实际调研记录和证据为主。|
|Reason|项目需要一份能够直接用于内部交接和后续计划编制的统一视图，同时不能把 Phase 0 期间生成的需求、方案和 AI 工作基线描述成正式业务事实。分段路线、进入条件和完成证据可让后续 WBS 保持可追溯、可验收和可回滚。|
|Impact|5 个项目形成 40 条交付项、21 项专项、10 条正式化待办和 30 个调研主题；工作簿 6/6 页签视觉和回读通过，71 个证据链接完整、公式错误 0，POC-03 183/183 测试 PASS。本轮外部调用 0，不创建正式 Requirement/Solution，不改变正式 Phase 0、冻结顺序或 HOLDOUT_LIVE_DATA_EGRESS Gate。|
|Rollback|删除 R6 本地输出和新增通用生成器即可回到 R4/R5；两份源包指纹、客户资料、历史版本、正式 Gate 和质量复验授权状态均不修改。|

## DEC-20260921-027

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-027|
|Date|2026-09-21|
|WBS|项目实施 WBS R7 / 管理层汇报 R8.1 / P03-A11~A13-R8 前置检查|
|Decision|把 R6 内部交付包展开为 5 个项目、60 项内部 WBS 草案任务，按 W0-W4 保留角色、依赖、进入条件、验收和证据追溯，但不填写实名、日期或承诺工期；同时生成 8 页管理层汇报，如实展示校准集 FAIL 和独立留出集待复验。留出集验证器只对 `poc-03.holdout.v1` 接受恰好 50 条，其他数据集仍保持 100~200 条。虽然用户授权“真实质量复验”且 DeepSeek 外发已有明确记录，本轮不得把该授权自动扩大到百炼 Embedding/Reranker；需用户另行明确其目的地和载荷范围。|
|Reason|WBS 与管理汇报可在不外发客户内容的前提下推进内部准备；实名、日期和正式工期需要资源与 Gate 事实，不能由 AI 编造。百炼调用会发送查询及候选正文，属于与 DeepSeek 不同的外部目的地，必须按最小授权原则单独确认。|
|Impact|WBS R7 为 60 项任务、40 个证据链接、5/5 页签检查通过；管理层汇报 R8.1 为 8 页并通过最终化、逐页渲染和原生图表检查；POC-03 188/188 测试 PASS。组合语料为 2,078 个 Chunk、50 条预期证据缺失 0，PostgreSQL 18.6/pgvector 0.8.6 前置检查 PASS；安全拦截前本轮外部调用 0，Phase 0 与质量 Gate 不变。|
|Rollback|删除 R7/R8.1 本地输出及三个新增生成器，回退留出集大小入口改动即可恢复至 R6 检查点；R6 交付包、客户资料、校准集结果、正式 Gate 和历史版本不受影响。|

## DEC-20260921-028

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-028|
|Date|2026-09-21|
|WBS|P03-A11~A13-R8 独立留出集真实复验 / P03-A12~A13-R9 质量改进|
|Decision|接受并冻结本轮独立留出集 98.00% / 48.00% / 74.00% 的真实结果：P03-A11 PASS，P03-A12/P03-A13 FAIL。门槛、人工标签和引用真值均不修改。首次装载发现的 17 个重复 ChunkId 只在逐字段完全一致时去重；同 ID 不同内容继续失败关闭。本轮 50 条已成为已见测试集，后续调优不得再次把它作为未见独立集的通过证据。|
|Reason|检索命中 49/50 但分类只有 24/50、引用只有 37/50，证明主要瓶颈位于业务分类判断和已召回候选中的精确引用选择。模型把 44/50 条判为标准满足，资料不足和非标功能识别明显不足。逐条针对本留出集写规则会产生数据泄漏，不能形成可推广的质量结论。|
|Impact|50/50 条百炼重排与 50/50 条 DeepSeek 预测完整完成，GIN/HNSW 命中，缺失预测与越界引用均为 0。新增两个重复 Chunk 失败关闭回归，POC-03 测试增至 190 项。管理层汇报更新为 R9，Phase 0 和正式编码 Gate 保持阻塞。下一 WBS 在本地分析 26 条分类失例、13 条引用失例和 1 条检索失例，并在独立开发集上设计修复。|
|Rollback|真实结果和审计证据不可回滚或覆盖；代码可回退重复 Chunk 处理与汇报生成器，但不得删除或改写本次质量失败历史。|

## DEC-20260921-029

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-029|
|Date|2026-09-21|
|WBS|P03-A12~A13-R10 独立留出集失败分层诊断|
|Decision|冻结 R10 诊断，采用“双来源证据装配 + Prompt v3 结构化判定 + 独立 Evidence Selector”作为下一轮独立开发集修复方向。当前 50 条只作为已见回归诊断集；不修改其标签、可接受引用集合或分数。|
|Reason|需求来源 17 条中检索命中 16 条但分类只命中 1 条，证明能力适配标签所需的标准能力对照未进入同来源上下文；模型 46/50 次引用第 1 名，正确证据位于第 2～5 名时只命中 2/12。13 条严格引用失例中有 8 条引用覆盖全部答案术语，说明未来数据冻结前还需完成可接受引用集合审查。|
|Impact|下一轮先建立与本留出集隔离的开发/校准集，区分文档事实与能力适配问题，保留 ProjectId 隔离并增加需求证据与标准能力证据双通道；模型供应商、Embedding、Reranker、PostgreSQL、质量门槛和总体架构均不变。任何新真实外部调用仍需当轮外发授权。|
|Rollback|可回退新增诊断工具和建议方案，不影响已冻结的 98.00% / 48.00% / 74.00% 真实结果；不得删除失败历史或把当前 50 条恢复为未见留出集。|

## DEC-20260921-030

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-030|
|Date|2026-09-21|
|WBS|P03-A12~A13-R11 Prompt v3 与 Evidence Selector 离线修复|
|Decision|按用户批准的方案 A 实现离线 Prompt v3、双来源证据装配和 Evidence Selector；遵循用户“不用重复验证”的决定，不对当前 50 条重新调用模型或重算质量分数。|
|Reason|R10 已确认能力适配缺少跨来源对照且引用存在首位偏差。离线合同和合成测试可以修复结构性缺陷而不泄漏已见留出集；但没有新的独立真实证据，不能据此声明 P03-A12/P03-A13 PASS。|
|Impact|新增文档事实/能力适配显式路由、条件 OutputSchema、需求与标准能力证据角色、ProjectId 失败关闭和查询支持度选择器。模型供应商、统一 AIService、数据库、质量门槛、人工标签及历史结果不变；POC-03 保持 FAIL，项目仅继续不依赖该结论的其他 Phase 0 PoC。|
|Rollback|删除 Prompt v3、Evidence Selector、对应测试和 R11 设计文档即可回到 R10 诊断状态；不会改变 v2 历史代码、真实调用缓存或冻结结果。|

## DEC-20260921-031

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-031|
|Date|2026-09-21|
|WBS|P05-A19 真实扫描 PDF 分层语义准确率|
|Decision|以“原页视觉抄录后再比 OCR”的 75 个分层检查点作为真实扫描语义 PoC 门槛：一般语义相似度不低于 0.85，数值、代码和版本完全一致，总召回不低于 95%，关键错误为 0。PaddleOCR 保持主链；未过门槛的 Tesseract 只作辅助回退，关键字段必须由主链或人工确认。依据用户批准，Windows 11 物理断网与 Debian 13 登记 `EXC-P0-004` 暂缓。|
|Reason|成功解析、OCR 行数和自生成术语召回不能证明真实扫描语义准确率。分层页面与人工视觉检查点可避免 OCR 自证；主辅链对照显示 PaddleOCR 75/75，而 Tesseract 只有 70/75 且含关键错误。用户已明确同意 Windows 11 保留 `PASS_LOCAL_ASSETS`、不主动断网，并曾明确 Debian 13 暂不验证。|
|Impact|POC-05 以 `PASS_WITH_EXCEPTION` 收口。Windows 11 与 Windows Server 2025 的已验证结论保留；Windows 11 物理断网、Debian 13 和 105 页逐字符全量标注仍不形成通过结论。原页、真值、客户内容和逐项结果只留在 Git 忽略的本地 artifacts，仓库保存匿名汇总。|
|Rollback|可删除本轮评分工具和匿名汇总并恢复 POC-05 `IN_PROGRESS`；不得把 Tesseract 基线失败改写为通过，也不得删除 `EXC-P0-004` 的历史批准记录。|

## DEC-20260921-032

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-032|
|Date|2026-09-21|
|WBS|POC-06 Word / PowerPoint 交付级样例|
|Decision|以 Microsoft Office 实开和 PDF 导出作为 Windows 目标应用验收主证据；Windows 11 结论为 PASS。Windows Server 2025 未安装 Word/PowerPoint，只记录 OOXML 包结构和 Hash 复验 PASS，POC-06 保持 `IN_PROGRESS / SERVER_OFFICE_BLOCKED`，不从 Windows 11 外推 Server 或 Debian 兼容性。|
|Reason|基线要求“可由 Microsoft Office 正常打开”。工作区 DOCX 渲染器因未安装 LibreOffice 无法运行，但 Windows 11 已由目标 Word 应用导出并完成 100 页视觉检查；Server 虚拟机缺少 Office，不能以结构验证替代实开验收。|
|Impact|Windows 11 形成 100 页 DOCX、50 页 PPTX、实开/PDF 导出、OOXML 完整性和 150 页全量视觉证据。PPTX 制件按当前工作区规范使用 Artifact Tool，不修改正式 `python-pptx` 基线。未经许可不在 Server 安装 Microsoft Office，也不将缺少环境记为通过。|
|Rollback|可删除 POC-06 样件、脚本和匿名证据并恢复 `NOT_STARTED`；不得将 Windows 11 的实验结果改写为 Server/Debian 通过，也不得隐去 Server 未安装 Office 的阻塞。|

## DEC-20260921-033

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-033|
|Date|2026-09-21|
|WBS|POC-08 Plugin Host|
|Decision|PoC 宿主采用“每次调用一个独立 Python 子进程 + 单条 JSON-RPC 2.0 stdio 请求/响应”的最小隔离实现。Manifest 在启动前检查必填字段、Plugin API 版本、OS、入口路径边界和入口文件 SHA-256；子进程只继承最小系统环境，不继承 DB/AI Key。|
|Reason|当前 Phase 0 需要直接证明 crash、timeout、invalid JSON、版本不兼容和独立升级，不需要提前引入常驻池、容器、微服务或自定义 TCP。短命子进程便于失败后立即回收，并与锁定的 stdio 协议一致。|
|Impact|Windows 11 和 Windows Server 2025 均完成 13/13 测试、10/10 验收场景和 20/20 并发调用；插件 crash/timeout 后 FastAPI 仍健康，invalid JSON 失败关闭，v1→v1.1 不修改宿主。SHA-256 只是本 PoC 的包完整性检查，不代表开发者身份签名；正式发布签名待后续冻结。Debian 13 未验证。|
|Rollback|删除 `poc/poc-08-plugin-host/` 和对应匿名证据即可回到 `NOT_STARTED`；不影响正式业务模块、数据库、API Contract 或发布签名方案。|

## DEC-20260921-034

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-034|
|Date|2026-09-21|
|WBS|POC-09 License|
|Decision|PoC 将 MAC 规范化为大写冒号形式后计算 SHA-256；License Payload 采用字段排序、紧凑分隔符的确定性 UTF-8 JSON，并由仅驻留开发者工作台进程内的 Ed25519 私钥签名。客户侧只使用公钥；`SystemTimeGuard` 记录本次运行最近成功时间并拒绝回拨。|
|Reason|基线已锁定 MAC → Normalize → SHA-256 → Ed25519，但未规定规范化文本和确定性序列化细节。显式规范避免分隔符/大小写导致同一网卡产生不同指纹，确定性 JSON 避免同一 Payload 因编码差异导致验签失败。|
|Impact|Windows 11 与 Windows Server 2025 均完成 26/26 测试和 10/10 场景；8 类非法授权全部拒绝，License/MAC/时间防护覆盖率 91%～94%，私钥和原始 MAC 未落盘。跨进程可信时间状态存储留待 Architecture Freeze，Debian 13 未验证。|
|Rollback|删除 `poc/poc-09-license/` 和对应匿名证据即可回到 `NOT_STARTED`；不改变 Ed25519、Payload 正式字段、数据库、正式 API 或商业授权规则。|

## DEC-20260921-035

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-035|
|Date|2026-09-21|
|WBS|Phase 0 Debian 13 验证范围|
|Decision|依据用户明确决定，登记 `EXC-P0-005` 暂缓 POC-06、POC-08、POC-09 的 Debian 13 验证；POC-08、POC-09 以 `PASS_WITH_EXCEPTION` 收口。POC-06 仅解除 Debian 缺口，Windows Server 2025 Office 阻塞保持。|
|Reason|用户明确表示 Debian 13 不用验证。该决定满足 L3 例外确认要求，但不等于形成 Debian 兼容证据。|
|Impact|Phase 0 不再因 POC-08/POC-09 的 Debian 缺口阻塞；剩余正式阻塞为 POC-03 质量 Gate 和 POC-06 Windows Server 2025 Office 实开。Debian 发行与 Release Gate 仍不得宣称通过。|
|Rollback|用户可撤销例外并恢复 Debian 13 实机验证；恢复后 POC-06、POC-08、POC-09 在 Debian 结果形成前回到 `IN_PROGRESS`。|

## DEC-20260922-036

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-036|
|Date|2026-09-22|
|WBS|Phase 0 Gate 1|
|Decision|用户批准 POC-03 和 POC-06 两项替代方案并正式确认 Gate 1。POC-03 保留分类 48.00%、引用 74.00% 的 FAIL，以 R11 + 强制人工确认收口；POC-06 以 Windows 11 Office 实开、Server 包结构/Hash 和 Server Office 豁免收口。|
|Reason|用户此前决定不重复本轮 POC-03 真实复验；POC-06 的 Microsoft Office 不是服务器运行依赖，且 Server 已确认制品 Hash/OOXML 与 Windows 11 一致。两项原验收无法在现有条件下继续，已按 L3 取得明确决定。|
|Impact|Phase 0 状态变为 `COMPLETE_WITH_APPROVED_ALTERNATIVES`，项目进入 Architecture Freeze。POC-03 质量指标转为 Gate 3/UAT 阻塞；Server Office 与 Debian 未验证范围转为 Release 约束；Gate 2 前仍禁止正式业务编码。|
|Rollback|撤销 Gate 1 时恢复 Phase 0 `IN_PROGRESS`：POC-03 重新执行全新独立留出集，POC-06 补齐 Server Office 实开；Architecture/Data/API 冻结活动停止。|

## DEC-20260922-037

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-037|
|Date|2026-09-22|
|WBS|AF-01 Architecture Baseline Consolidation|
|Decision|在锁定模块化单体内把 V1 Scope 收敛为 Platform 公共模块、AI/RAG、Capability 与七个实施业务域，并单列 `output` 作为输出编排模块。`output` 只构造 OutputContext、调用 PluginService 和登记制品，不自行实现格式渲染或直接操作插件进程。|
|Reason|V2.1 功能子系统包含 Output，但最小模块清单未单列；若把输出编排并入 Plugin，会混淆业务输出上下文与进程/包管理边界。单列编排模块可以保持业务依赖稳定，又不改变 python-docx/python-pptx 与 Plugin 技术基线。|
|Impact|形成 22 个客户运行模块与 1 个独立 Developer Workbench 信任区的边界候选；所有跨模块写入通过 Application Port/Domain Event，文件、AI、RAG、Plugin、Review、Trace、Audit 各有唯一 Owner。未冻结实体字段、表或 API。|
|Rollback|在 Architecture Freeze 前可把 `output` 编排职责合并到 Solution Application 层并删除候选模块；不得把职责合并到 Plugin 进程管理实现或引入新的渲染技术栈。|

## DEC-20260922-038

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-038|
|Date|2026-09-22|
|WBS|AF-02 Application Contract|
|Decision|模块间同步交互采用技术无关 Application Port；跨模块状态传播使用最小 Domain Event。第一版同步事件进程内分发，长任务和需要恢复的事件写 PostgreSQL Job/Outbox，并按至少一次处理与幂等消费设计；不引入消息队列。|
|Reason|模块化单体需要稳定边界但不需要分布式基础设施。Application Port 防止跨模块访问内部表，持久化 Job/Outbox 满足长任务和恢复需要，同时符合禁止 Redis/消息队列的基线。|
|Impact|六个公共服务、Document/Evidence 读取端口、18 个事件及错误语义形成候选 Contract；未固定 REST、ORM、表结构或 Python 签名。|
|Rollback|Architecture Freeze 前可合并或拆分事件语义；不得改为直接跨模块写表或新增消息队列，除非提交 L3 Change Request。|

## DEC-20260922-039

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-039|
|Date|2026-09-22|
|WBS|AF-03 Security / File / Job / Runtime Boundaries|
|Decision|在 V2.1 基线内固定默认拒绝的请求安全链、受控文件生命周期、Secret 引用边界、PostgreSQL Job/Outbox 至少一次语义、三类日志以及 API/Worker/Plugin/Developer Workbench 信任区。Plugin 独立子进程只作为故障与凭据隔离，不宣称为可运行任意第三方代码的强安全沙箱。|
|Reason|模块与 Application Contract 已明确，但如果认证授权顺序、文件原子性、Worker 系统主体、Secret 解密范围和日志数据边界不统一，后续 Data/API 设计会产生绕过 ProjectId、泄露路径/凭据或重复任务写入的风险。V1 又明确禁止引入 Redis、消息队列、容器化插件和第三方市场。|
|Impact|后续 Data Model 与 API Contract 必须承载服务器端 Session、CSRF、资源授权、不可变文件版本、Job 租约/幂等、SecretRef、Audit 与可信时间状态语义；具体表名、字段、REST 路径、密码哈希库和服务管理器仍未冻结。Windows 11、Windows Server 2025、Debian 13 保持正式目标，但 Debian 与 Server Office 未验证事实不变。|
|Rollback|Gate 2 前可调整内部顺序或端口粒度；不得弱化默认拒绝、ProjectId 隔离、License 私钥隔离、文件受权访问或 Audit 不可普通删除等基线。若需引入新基础设施或强插件沙箱，提交 L3 Change Request。|

## DEC-20260922-040

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-040|
|Date|2026-09-22|
|WBS|AF-04 Architecture Decision Records|
|Decision|将七项长期架构决策分别固化为 ADR-003～ADR-009，而不合并成单一总 ADR；其状态标记为继承已批准基线但尚未通过 Gate 2 完整冻结。ADR-009 单独保留 POC-03 质量失败和 Gate 3/UAT 阻塞，避免被一般 AI/RAG 架构决策掩盖。|
|Reason|模块化单体、AI/RAG、Plugin、License、Job、文件存储和质量控制的变更触发条件、回滚路径与验收 Gate 不同。独立 ADR 可以让后续 Data/API 设计逐项追溯，也能在某一决策被替代时保留其他决策稳定。|
|Impact|Architecture Freeze Candidate 将引用九份 ADR；ADR-003～009 均具备 Context、Decision、Consequences、Rejected Alternatives 和 Rollback/Change Rule。未引入新技术栈、Schema、API 或正式业务代码。|
|Rollback|Gate 2 前可合并、拆分或调整 ADR 候选；必须保留历史失败与用户例外，不得通过文档重组弱化 L3、Release、Gate 3 或 UAT 约束。|

## DEC-20260922-041

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-041|
|Date|2026-09-22|
|WBS|AF-05 Architecture Freeze Candidate|
|Decision|将 AF-01～AF-04 的详细成果汇总为 `ARCH-CANDIDATE-V1`，采用“显式允许依赖、其余全部禁止”的依赖矩阵，并把同步请求、文件、AI 正式化、Job 和 Output/Plugin 固化为五类运行视图。七项 Phase 0 例外与五项持续风险全部保留关闭 Gate，不因形成候选而视为已解决。|
|Reason|Data Model Freeze 需要稳定的模块 Owner、跨模块 Contract、信任边界、运行流程和风险输入；单一候选清单可以消除多个设计文件之间的解释歧义，同时保留详细文档和 ADR 的反向追溯。|
|Impact|AF-01～AF-05 状态均为 PASS，项目进入 DM-01。Architecture 版本为候选而非正式冻结；实体字段、物理 Schema、REST API 和业务代码仍未授权，正式开发继续由 Gate 2 阻塞。|
|Rollback|Gate 2 前可回退为 AF-05 IN_PROGRESS 并修订候选；不得删除 Phase 0 失败/例外或绕过 L3。Gate 2 后的总体架构变更必须提交独立 Architecture Change Request。|

## DEC-20260922-042

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-042|
|Date|2026-09-22|
|WBS|DM-01 Core Entity / Aggregate Catalog|
|Decision|采用“逻辑对象 Aggregate + 不可变 Version Aggregate”的正式制品模式；AI 建议只保留在 AITask/AIInvocation 聚合，人工显式接受后由目标 Domain 创建新的 Draft Version，再经 Review 指定版本正式化。为落实既有 Review/Event/Job/License 语义，补充 HandoverAnalysisVersion、PlanVersion、TrustedTimeState 和 OutboxEvent 等必要聚合根。|
|Reason|若版本作为可变字段内嵌在逻辑对象，送审锁定、历史确认、Trace 和并发编辑会相互冲突；若 AI 对象可直接切换为正式状态，则无法证明人工确认、证据和输入版本。独立 Version 与显式接受命令可以保持历史不可变和责任边界。|
|Impact|22 个客户运行模块形成 65 个 Aggregate Root，Developer Workbench 另有 3 个且不进入客户 Schema。后续 DM-02～DM-06 必须沿用 Owner、Scope、Version Ref 和 AI/正式事实分离；物理表和外键仍待 Schema V1。|
|Rollback|Gate 2 前可合并低价值运行聚合，但不得合并 AI Suggestion 与正式 Domain Version、不得取消不可变版本/ReviewSubject 或跨模块稳定引用原则；涉及这些原则的改变按 L3 核心数据模型调整处理。|

## DEC-20260923-043

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-043|
|Date|2026-09-23|
|WBS|DM-02 Platform and Security Data Model|
|Decision|Project 不保存 current_stage 可写副本，由 ProjectWorkflow 唯一拥有阶段状态；Review 绑定逻辑主题身份，ReviewRound 绑定具体不可变主题版本。用户名唯一键采用 trim + Unicode NFC + invariant case-fold；Session 只持 Token/CSRF 摘要并绑定 credential_version；Project Role 只存在 ProjectMember，DeploymentAdmin 保持独立部署角色。|
|Reason|复制 current_stage 会造成 project 与 workflow 的双写和反向依赖；Review 若永久绑定单一版本则无法同时满足送审锁定、退回升版重审和历史决定保留。规范化用户名、摘要 Session 与角色分离可让授权和凭据失效语义在 Schema/API 阶段保持唯一解释。|
|Impact|DM-01 聚合数量不变，但 PRJ-01、RVW-01、RVW-02 的包含语义已校正。后续 Schema 必须支持凭据版本失效、单一有效项目成员、Workflow 乐观并发、Review 轮次/版本唯一性、Secret 单 Active Version 与 TrustedTime 单调更新。|
|Rollback|Gate 2 前可调整规范化或状态命名；不得恢复 Project/Workflow 双写、覆盖 Review 历史、保存原始 Session Token/Secret 明文或合并部署/项目角色。触及安全或核心数据机制时按 L3 处理。|

## DEC-20260923-044

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-044|
|Date|2026-09-23|
|WBS|DM-03 Document / Evidence / Trace / Version Data Model|
|Decision|分离 Document 逻辑身份、不可变 DocumentVersion 与 FileObject 物理元数据；以类型化 EvidenceLocator 和 EvidenceBinding 表达证据定位与支持关系，TraceLink 仅表达业务制品间的来源与追溯。实际调研记录归为 PROJECT_RECORD 并作为主要事实来源，调研业务表单归为 TEMPLATE，只能辅助组织调研而不能独立证明客户事实。|
|Reason|逻辑对象、版本和物理文件混合会导致覆盖历史、路径泄漏和定位漂移；Evidence 与 Trace 共用一种关系会混淆“原文证明”与“业务制品来源”。明确实际记录优先也落实了用户此前确认的调研事实规则，并支持从待办一键定位原文。|
|Impact|DM-01 的 EVD-02 Scope 调整为 GLOBAL_OR_PROJECT。后续 Schema/API 必须实现稳定引用、九类定位器、文件状态与恢复、版本保留和图关系授权；Evidence Viewer 不得暴露绝对路径或把短摘录当作权威原文。本阶段仍未定义物理表、API 或 Migration。|
|Rollback|Gate 2 前可细化定位器和关系枚举；不得恢复绝对路径定位、覆盖 DocumentVersion、让模板独立证明客户事实，或重新合并 EvidenceBinding 与 TraceLink。触及核心数据模型时按 L3 处理。|

## DEC-20260923-045

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-045|
|Date|2026-09-23|
|WBS|DM-04 AI / RAG / Job / Plugin / Output Data Model|
|Decision|AITask 只通过统一 AIService 创建不可变 AIInvocation，并保存 Prompt/Input/Context/Provider/Model/Schema 与外发授权快照；Embedding Index 绑定精确模型、维度、Chunk Profile 和 Scope，不兼容变化必须新建索引并全量重建；Job/Outbox 采用至少一次、幂等与租约 fencing；Plugin 成功只产生待校验结果，OutputArtifact 在 FileObject/DocumentVersion/Hash 全部登记后才可发布。将 RAG-04 RetrievalRun Scope 从 PROJECT 校正为 GLOBAL_OR_PROJECT，以落实既有 GLOBAL/PROJECT 双知识域。|
|Reason|这些运行对象跨越外部 Provider、PostgreSQL、文件系统和独立进程，无法可靠承诺精确一次或依赖可变“当前版本”。不可变快照、Scope 隔离、fencing 和分阶段发布可避免模型/索引漂移、跨项目泄露、过期 Worker 提交和半完成制品；GLOBAL 检索记录也必须可审计，不能因目录先前误限为 PROJECT 而丢失。|
|Impact|后续 Schema/API 必须实现 AI、Embedding、Reranker 的逐次外发授权引用，以及 Invocation/Index generation、单一活动索引、Job Lease fencing、Outbox 消费去重、Plugin 精确包版本和 Output 发布完整性；既往 PoC/复验授权不得自动复用于未来调用。POC-03 分类 48%/引用 74% 的质量失败保持 Gate 3/UAT 阻塞，不因模型冻结而关闭；本阶段仍未定义物理表、API 或 Migration。|
|Rollback|Gate 2 前可细化状态名、策略字段和保留方式；不得允许业务模块直连厂商 SDK/pgvector、复用不兼容向量、移除 Project 隔离/外发授权、宣称精确一次、让 Plugin 直连数据库/Secret，或让 AI/插件结果绕过人工确认和制品校验。触及这些边界时按 L3 处理。|

## DEC-20260923-046

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-046|
|Date|2026-09-23|
|WBS|DM-05 Implementation Domain Data Model|
|Decision|实施业务主链统一采用逻辑对象与不可变版本分离，正式指针只指向通过 Review 的指定版本；GLOBAL Capability 是标准能力事实，项目的 STANDARD_FUNCTION、NONSTANDARD_FUNCTION、DIFFERENCE、PENDING_CONFIRMATION 是 RequirementVersion 判断。实际调研记录优先于 TEMPLATE；NeedConfirm/ActionItem 必须保存明确问题、影响、选项、建议、人工输入规格和 EvidenceRef。Requirement→Solution 以章节版本内覆盖快照加 TraceLink IMPLEMENTS 表达，不新增可变双写关系；PlanVersion 固定最多六级 WBS 和仅 FS 的无环依赖。|
|Reason|现有 R1～R9 验证成果同时包含标准、非标、差异和待确认草案，但明确不是正式需求/方案。若直接把表格行或 AI 结果当作事实，会丢失来源、版本和人工责任；若只复制原文到待办，又无法提供友好维护提示和精确原文定位。不可变版本、Evidence Viewer、Review 与 Trace 可以在保留真实调研优先原则的同时形成完整交付链。|
|Impact|后续 Schema/API 必须实现各业务对象的逻辑身份/版本指针、ReviewSubjectSnapshot、CapabilityAssessment、AnalysisItem 输入提示、面对面调研来源标识、需求覆盖、专项设计校验和 WBS DAG 约束。R1～R9 文件保持历史验证制品，不自动导入正式数据库或转为客户事实；POC-03 质量失败仍由 Gate 3/UAT 阻塞。|
|Rollback|Gate 2 前可细化业务枚举、专项字段和状态名称；不得让 GLOBAL 基线被项目反写、让模板/AI 自动成为事实、覆盖已审核版本、取消 Evidence/Review/Trace、把待确认项静默转正，或放宽六级 WBS/仅 FS/无环约束。触及核心业务模型时按 L3 处理。|

## DEC-20260923-047

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-047|
|Date|2026-09-23|
|WBS|DM-06 Data Model Candidate Consolidation|
|Decision|将 DM-01～DM-05 汇总为 `DATA-MODEL-CANDIDATE-V1`，保持 22 个客户运行模块、65 个 Aggregate Root 和 3 个物理隔离 Developer Workbench Root。统一五类 Scope、稳定引用、六类生命周期、正式化链与物理清理六项前置；RetentionPolicy/RetentionHoldEntry 作为 platform.SystemConfiguration 的受控子实体，不新增 Root。采用 R0～R8 九类候选保留策略，其中 Audit/签名/Review 与正式项目资料候选默认 5 年，AI/RAG/Job 运行记录 180 天，临时区 7 天；Active Hold 和保护引用始终优先。|
|Reason|Schema V1 需要单一、无冲突的关系、基数、生命周期和保留输入。只写“历史保留”无法指导清理与容量设计，而把合同/法规期限硬编码又会产生合规风险；版本化策略、可延长默认值、Hold 优先和引用预检能同时提供可实施基线与客户配置空间。|
|Impact|Data Model Freeze 的六个 WBS 全部 PASS，形成 25 条核心不变量、14 项风险和 15 项 Schema 交接要求。后续 SC-01～SC-05 必须映射这些约束并验证空库/有数据升级；候选期限不构成法律结论，客户合同可延长，缩短正式/审计数据期限需在 Gate 2/Release 评审。POC-03、Server Office 和 Debian 未验证结论保持不变。|
|Rollback|Gate 2 前可调整候选期限、物理清理实现和 Schema 交接顺序；不得移除 Hold/保护引用、允许普通用户删除 Audit/正式历史、破坏 Owner/Scope/版本/Review/Evidence/Trace 边界，或把候选 Data Model 描述为已冻结物理数据库。触及核心数据、安全或合规边界时按 L3 处理。|

## DEC-20260923-048

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-048|
|Date|2026-09-23|
|WBS|SC-01 Logical-to-Physical Schema Mapping|
|Decision|客户运行时采用单一 PostgreSQL 数据库和单一 `plm` 应用 Schema，不为 22 个模块分别创建 PostgreSQL Schema；以 `plt_`、`auth_`、`prj_` 等 22 个短前缀表达表 Owner。65 个 Aggregate Root 各映射一个唯一 primary table，Owned Entity 按查询、唯一、顺序、状态和引用需要拆表。固定目标类型优先直接 FK；Review/Trace/Audit/Event 等多态引用采用受控 discriminator + object/version/project 列组，不新增全局共享写 object_registry。Developer Workbench 使用独立数据库/部署。|
|Reason|V1 是单服务器模块化单体并使用同一应用数据库身份，22 个 PostgreSQL Schema 不形成真正安全隔离，却增加 Alembic search_path、跨 Schema FK、备份恢复和离线运维复杂度。模块前缀与 Application Port 能清晰表达 Owner；全局 object_registry 会成为所有模块共同写热点并破坏唯一 Owner。|
|Impact|形成 65/65 Root primary table 映射及 owned table 候选，表名使用 ASCII lower_snake_case、目标不超过 55 字符。SC-02 必须补齐 Scope/ProjectId、Version、固定 FK、多态白名单、唯一/CHECK 与不可变约束；SC-03/04 再定义索引、pgvector、Migration 和恢复测试。本阶段没有创建 ORM、Migration 或业务表。|
|Rollback|Gate 2 前可改为少量分组 Schema 或调整 table/child 拆分，但必须提供 Alembic、权限、备份和跨平台证据；不得把 Developer Workbench 放入客户数据库、取消 Owner 前缀/边界、用 JSONB 隐藏 ProjectId/核心 FK，或引入共享写 object_registry。|

## DEC-20260923-049

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-049|
|Date|2026-09-23|
|WBS|SC-02 Field Types and Constraints|
|Decision|主键使用 PostgreSQL 18 `uuidv7()`；时间使用 UTC `timestamptz(6)`，日历计划日期单独使用 `date`。状态采用 text + named CHECK，不使用 PostgreSQL ENUM/DOMAIN；固定长度 Hash 使用 `bytea` 并检查字节数。PROJECT/GLOBAL_OR_PROJECT 表显式保存 ProjectId/Scope，并以复合 FK 防跨项目归属漂移；FK 默认 NO ACTION、NOT DEFERRABLE，V1 不启用 CASCADE。Version/current pointer 使用复合归属约束，内容不可变、append-only、状态迁移及多态目标由数据库约束、受控 trigger 和 Application Command 共同保护。V1 不把 RLS 作为主防线且默认不启用，授权依靠 ProjectAuthorizationService、显式过滤、复合约束与负向测试。|
|Reason|有序 UUID 降低随机主键的索引局部性成本，同时不承载授权语义；text + named CHECK 比 ENUM 更利于 Alembic 的双版本升级/回退。显式 ProjectId 与复合 FK 能在 Repository 漏写过滤时继续阻止跨项目归属，而过早启用 RLS 会显著增加连接池、后台 Job、Migration 和恢复路径的策略复杂度。NO ACTION 与无自动级联保证 Retention、Hold、Audit 和保护引用先完成预检。|
|Impact|65 个 Root 已分配 M/V/A/R/SEC 字段 Profile，形成 28 组唯一语义、多态白名单、敏感列与数据库角色候选。SC-03 必须把条件唯一、授权过滤、Job/Outbox、Audit/Trace、Retention、FTS 与 pgvector 转为索引和关键查询计划；SC-04 再生成 Alembic 并执行空库/有数据 up/down、绕过 ORM 的负向测试。本阶段没有创建 ORM、Migration、业务表或索引。|
|Rollback|Gate 2 前可调整具体类型长度、CHECK 值、索引或受控 trigger 实现，但必须提供兼容 Migration 与 up/down 证据；不得弱化 Project 隔离、版本不可变、Secret/Session/License 敏感边界、Hold/保护引用预检，或让普通删除通过 CASCADE 绕过清理控制。若未来启用 RLS，须以 ADR 和连接池/Job/Migration/恢复全链验证后增量引入。|

## DEC-20260923-050

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-050|
|Date|2026-09-23|
|WBS|SC-03 Index and Critical Query Design|
|Decision|索引采用“约束索引复用 + 引用侧 FK B-tree + Project 前缀/keyset + 条件唯一 + 专用运行索引”的最小集合。Job/Outbox 使用短事务、稳定排序、`FOR UPDATE SKIP LOCKED`、Lease fencing 与消费幂等。全文使用受控中文 Token `search_body` 的 stored `tsvector` + GIN；向量使用按受支持维度由 Migration 创建的 HNSW 表达式索引族，查询强制 Scope/Project/EmbeddingIndex 过滤并启用 iterative scan，不足时只能在同授权范围扩大扫描或精确回退。V1 不启用按项目动态分区、每项目索引或 Runtime DDL。|
|Reason|PK/UNIQUE 重复索引和无消费者索引会增加单服务器的写放大与维护成本；Project 前缀和双向引用索引同时支撑授权、删除预检和稳定分页。pgvector 共享 HNSW 的过滤发生在近邻扫描过程中，不能只依赖默认候选数；模型维度又可能变化，因此需要受控维度索引、迭代扫描和同 Scope 精确回退。Job/Outbox 的至少一次语义要求数据库领取与外部执行分离，并由 fencing/幂等阻止过期 Worker 发布。|
|Impact|形成 20 个关键 Query ID、28 组唯一语义到 29 个物理唯一键映射、11 项风险及 SC-04 的数据规模/并发/执行计划验收计划。SC-04 必须生成 index manifest，验证 `EXPLAIN (ANALYZE, BUFFERS)`、多项目 Recall、20 Worker 领取/崩溃回收、Retention 保护引用和索引写放大；POC-02/03 的 HNSW 参数仅作初值，不能直接作为生产性能结论。HNSW `vector` 超过 2,000 维默认不兼容，替代表示需质量 PoC。本阶段没有创建 ORM、Migration、表或索引。|
|Rollback|Gate 2 前可依据 SC-04 计划删除冗余索引、调整列序/INCLUDE、HNSW 参数或固定 hash partition；必须保留 Project 隔离、同 Scope 精确回退、Job fencing/幂等和保护引用查询。引入独立向量库、消息队列、Redis、运行时 DDL或按客户动态分区属于超出当前方案的变更，须按 L3 处理。|

## DEC-20260923-051

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-051|
|Date|2026-09-23|
|WBS|SC-04 Migration and Recovery Validation|
|Decision|Gate 2 前建立独立 `VALIDATION_ONLY` Schema Contract：机器可读 manifest 覆盖全部 65 个 Root，关键安全/项目/文档/Review/Job/Audit/RAG/Trace/Retention/WBS 表使用代表字段与真实约束，其余 Root 只验证 M/V/A/R/SEC Profile。Alembic 0001 验证结构，0002 验证索引和 append-only guard；`plm.alembic_version` 位于应用 Schema。强过滤小向量集合允许 planner 使用 B-tree 后精确排序，HNSW 通过独立物理计划和 exact Recall 对照验证，不强制优化器采用成本更高的路径。|
|Reason|SC-01～SC-03 已冻结结构机制，但尚未形成每个 owned table 的完整生产列清单；直接生成完整业务 Migration 会把推断误写为正式事实。Profile + 关键代表表能在不越过 Gate 2 的情况下真实验证 PostgreSQL/Alembic、跨项目 FK、partial unique、GIN/HNSW、Job 并发、Retention 和恢复。优化器按选择性选择 exact fallback 是正确行为，强关 planner 选项不能作为生产性能证据。|
|Impact|Windows 11 上 4/4 单元、65 Root 空库/有数据 up/down、10/10 负向约束、20/20 Worker 唯一领取、Retention/Hold、备份恢复、GIN/HNSW 与敏感扫描通过；生成可重复 JSON 证据。SC-05 必须继续明确验证性/生产边界并汇总未细化 owned table；Gate 2 后正式 Migration 需冻结 revision、与最终 ORM 同步并重跑全量测试。Server 使用既有 POC-02 可行性证据，本轮未重跑；Debian 保持 Release 未验证约束。|
|Rollback|验证工作区可整体移除，不影响任何生产/客户数据库。可在 SC-05/Gate 2 前调整代表表和验证规模，但不得用 Profile 最小列替代正式字段设计、删除 Project 复合保护、append-only、Job fencing/幂等、Hold/保护引用或备份恢复要求。|

## DEC-20260923-052

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-052|
|Date|2026-09-23|
|WBS|SC-05 DB Schema Candidate 汇总|
|Decision|执行规则改为不自动读取 Codex/GPT 周额度，不再以剩余低于 20% 作为停止新任务或 WBS 的条件；仅在用户明确要求时查询。额度重置、购买或消耗 reset credit 仍需逐次明确确认。|
|Reason|用户在进入 SC-05 时明确取消原 20% 停止限制并要求不再检查；该最新明确指令优先于仓库此前的额度保护规则。|
|Impact|`AGENTS.md`、`.ai/SKILL.md`、项目开发 Skill 与 `STATUS.md` 的当前执行规则同步更新；历史决策和 Changelog 作为当时事实保留，不回写删除。该变更不影响 Gate、L3、Secret、客户数据外发或 Git 安全约束。|
|Rollback|用户可再次明确启用新的额度检查频率和停止阈值；在此之前不得自行恢复自动检查。|

## DEC-20260923-053

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-053|
|Date|2026-09-23|
|WBS|SC-05 DB Schema Candidate 汇总|
|Decision|以 `database-schema-v1-candidate.md` 作为 `DB-SCHEMA-CANDIDATE-V1` 单一规范入口，完整固化 65 个 Root primary table/PK/Profile 和 20 个 Query ID；SC-01～SC-04 作为受控明细附件。验证性 Schema Contract 仅作为机制证据，Gate 2 后按模块形成正式 ORM/Alembic，不将 generic Profile 最小列或 5 个代表 child 直接复制为生产 Schema。|
|Reason|逐字复制 SC-01～SC-04 会造成重复和漂移，但只有摘要又不足以检查 Root/Query 完整性。单一入口 + 机器 manifest + 受控明细能统一优先级、保留可追溯性，并如实区分设计候选、验证证据和正式生产实现。|
|Impact|Database Schema V1 候选覆盖 22 Owner、65 Root、29 个物理唯一键、20 个关键查询、14 项开放风险和 14 条 API Contract 输入。SC-05 静态一致性检查全部通过；项目可进入 API Contract V1，但 Architecture/Data Model/Schema/API 仍须 Gate 2 一并确认，正式业务编码继续阻塞。|
|Rollback|Gate 2 前可回退本汇总文件并恢复 SC-05 为待完成；不得删除 SC-01～SC-04 历史证据或把验证性 Migration 改称生产 Migration。若修改 65 Root、Owner、Scope、安全机制或基础设施，必须按 L3 处理。|

## DEC-20260923-054

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-054|
|Date|2026-09-23|
|WBS|API-01 Resource Catalog and Common Protocol|
|Decision|API V1 使用 `/api/v1` REST/JSON、multipart 流式上传和 SSE；JSON 成功/错误均携带 `trace_id`。PROJECT 资源强制 `/projects/{project_id}` 路径并再次校验归属；Session 使用 HttpOnly `plm_session`，状态改变请求使用 `X-CSRF-Token`。Mutable 资源以 ETag/If-Match 映射 `expected_version`，可重试写操作使用 Idempotency-Key，列表使用绑定 Scope/查询指纹的不透明 keyset cursor。65 个 Root 按 DIRECT/NESTED/READ_ONLY/INTERNAL 分类，内部 Job/Outbox/File/Embedding/安全状态不提供通用 CRUD。|
|Reason|统一 HTTP 外壳可避免各模块自行发明认证、分页、并发和错误语义；Project 路径、资源归属双检、固定版本引用和默认拒绝能够把 Architecture/Data/Schema 的隔离不变量提升为可测试 Contract。分类暴露可保留完整领域模型，同时避免把数据库 Root 或运行时细节机械暴露成 API。|
|Impact|后续 API-02～API-04 必须逐操作登记 Owner Port、Role、Scope、License、CSRF、If-Match、Idempotency、Audit 和错误码；API-05 汇总 OpenAPI/权限/错误/SSE。API Contract 工作从已同步的 Schema 检查点进入 `feature/api-contract-v1` 分支。DeploymentAdmin 不自动获得项目业务数据访问权；V1 不使用通用 DELETE、Offset 主分页、GraphQL、WebSocket 或任意 filter/order 表达式。|
|Rollback|Gate 2 前可修改具体路径名、Cookie/Header 名或资源暴露级别并重跑 65 Root/权限一致性检查；不得弱化 Project 隔离、Session/CSRF、固定版本、幂等、乐观并发、文件路径隐藏或内部 Root 不直出的安全边界。冻结后的 Breaking Change 必须走新端点、v2 或 API Change Request。|

## DEC-20260923-055

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-055|
|Date|2026-09-23|
|WBS|API-02 Platform, Security, Document and Governance Contract|
|Decision|平台/安全/治理 API 采用专用状态命令而非通用 DELETE/状态 PATCH；Session、FileObject、Parse runtime、TrustedTimeState 等内部 Root 不提供通用 CRUD。文件上传固定为 UploadIntent → 流式 Content → 幂等 Commit 三步，Commit 同步创建不可变 DocumentVersion 并返回 Parse JobRef。Review Round、EvidenceBinding 和 TraceLink 一律引用固定 Version；License 无效时只开放健康、登录、当前 Session 和 DeploymentAdmin 的五个 License 恢复端点。|
|Reason|内部运行 Root 直接暴露会允许客户端绕过 Application Port、状态机、文件一致性或可信时间。三步上传能隔离大文件传输与业务事务并支持崩溃恢复；固定版本引用保证 Review/Evidence/Trace 可审计。最小 License 恢复面既允许现场修复，又不会把无效 License 变成业务旁路。|
|Impact|形成 10 Owner/22 Root 的 86 个 Operation、42 个模块错误码、DTO 禁止字段、权限/Audit/测试矩阵。DeploymentAdmin 仍不是项目数据超级用户；Secret/临时密码 write-only，Viewer/下载不返回 Storage Locator，Trace 图逐节点授权。后续 API-03/04 必须沿用 API-01 公共 Envelope、CSRF、Project 隔离、If-Match、幂等和错误安全边界。|
|Rollback|Gate 2 前可调整具体路径、Operation 分组或角色白名单并重跑 Contract lint；不得改为通用内部 Root CRUD、返回 Secret/路径、动态 current 引用、跨项目可见、无 CSRF 状态写或扩大 License 恢复面。冻结后的 Breaking Change 走新端点、v2 或 API Change Request。|

## DEC-20260923-056

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-056|
|Date|2026-09-23|
|WBS|API-03 AI, RAG, Job, Plugin and Output Contract|
|Decision|所有可能向外部 AI Provider 发送数据的操作必须先生成可审计的外发预览，并取得绑定 Provider、Region、Purpose、Source、Payload Bounds 与单次逻辑操作的明确授权；授权只允许同一 Payload 的受限重试，不得复用 PoC、其他任务或历史轮次授权。AI Suggestion 始终标记 `NOT_FORMAL_FACT`，接受建议只能经目标 Owner Port 创建 Draft。Chunk、Embedding、Job Lease/fencing 与 Outbox 保持内部对象；Plugin 仅接受开发者签名包并通过独立子进程受控执行，不提供公共任意调用；Output Artifact 只有在二次校验和 Document 登记完成后才可发布。|
|Reason|外发授权必须能证明谁在何时为哪一最小载荷授权，避免授权漂移和客户数据越界；AI 建议、异步任务、插件及文件输出若直接暴露内部状态或绕过 Owner Port，会破坏事实确认、Project 隔离、at-least-once 幂等、fencing 与文件可追溯性。|
|Impact|形成 5 Owner/15 Root 的 79 个 Operation、51 个模块错误码、DTO、权限、SSE、强制 Audit 和测试矩阵。API-04/05 必须沿用逐次外发授权、`NOT_FORMAL_FACT`、Project 隔离、内部运行 Root 不直出、签名插件和输出二次校验边界。POC-03 的分类/引用质量仍为 Gate 3/UAT 阻塞项；本轮实际外部调用 0。|
|Rollback|Gate 2 前可调整具体路径、Operation 分组、角色白名单或事件粒度并重跑 Contract lint；不得弱化逐次最小外发授权、Project 隔离、AI 建议态、Job fencing、签名插件/无任意调用或输出校验与登记边界。冻结后的 Breaking Change 走新端点、v2 或 API Change Request。|

## DEC-20260923-057

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-057|
|Date|2026-09-23|
|WBS|API-04 Implementation Business Chain Contract|
|Decision|Capability、Handover、Survey、Requirement、Prototype、Solution 与 Plan 统一采用逻辑 Identity + 不可变 Version API；版本正文无 PATCH/DELETE，修订创建新 Version。各 Owner 的 `:submit-review` 只做送审前校验和 ReviewService 原子编排，不替代 API-02 的 Reviewer/锁定/决策规则；ReviewCompleted 后由 Owner 幂等更新正式指针、Trace、Audit 与 Outbox。实际调研记录优先于 TEMPLATE，AI Suggestion 只可经白名单 Owner Port 创建 Draft。所有跨阶段关系固定 VersionRef；上游替代只生成影响项，不自动改写或批准下游。|
|Reason|统一版本与 Review 编排可以让业务界面提供清晰动作，又不形成第二套评审引擎；固定引用、来源优先级和 Owner 正式化边界可防止模板/AI 冒充客户事实、动态当前版本漂移及跨模块直接写表。上游变化显式影响分析可保留历史交付并避免静默级联。|
|Impact|形成 7 Owner/28 Root 的 158 个 Operation、54 个模块错误码、DTO、Role × Resource 权限、SSE、强制 Audit 和测试矩阵。API-05 必须验证统一资源/Operation/错误/权限目录，保留不可变版本、Project 隔离、Evidence 定位、Review 锁、AI Draft 和影响分析边界。POC-03 分类/引用质量仍为 Gate 3/UAT 阻塞；本轮实际外部调用 0。|
|Rollback|Gate 2 前可调整具体路径、Operation 分组、角色白名单或 DTO 拆分并重跑 Contract lint；不得弱化版本不可变、固定 VersionRef、统一 Review、实际调研优先、AI 不自动正式化、跨项目拒绝、方案覆盖/Trace 一致或 WBS 六级/FS DAG 边界。冻结后的 Breaking Change 走新端点、v2 或 API Change Request。|

## DEC-20260923-058

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-058|
|Date|2026-09-23|
|WBS|API-05 API Contract Candidate Aggregation|
|Decision|`api-contract-v1-candidate.md` 作为 API V1 单一汇总入口，API-01～04 保持规范明细；不复制 323 个 Operation 形成第二份人工清单，而由 `contract_lint.py` 从四份源文档确定性生成带 SHA-256 的机器 manifest。manifest 统一索引 65 Root/暴露、Operation/展开 Path、错误、SSE、Query 映射和 18 个核心枚举族，但不冒充可部署 OpenAPI；Gate 2 后 FastAPI/Pydantic 生成的实际 OpenAPI 必须与该 manifest 做 Contract diff。|
|Reason|完整手工复制会形成重复规范和漂移，只有文字摘要又无法自动验证。单一汇总 + 受控明细 + 可再生机器目录既保留人类可评审语义，也提供实现和 CI 所需的稳定输入，并如实区分设计契约与尚未创建的运行 OpenAPI。|
|Impact|API-05 静态验证覆盖 22 Owner、65 Root、323 Operation、363 Method/Path 变体、150 错误、18 SSE、20 Query 映射和 18 枚举族，5/5 测试 PASS。Architecture/Data Model/Schema/API 四份 Gate 2 候选已齐备；Gate 2 仍需用户明确确认，正式编码未获授权。|
|Rollback|Gate 2 前可删除生成 manifest/校验器并恢复 API-05 为待完成；不得删除 API-01～04 历史或把未实现的 OpenAPI 描述为已运行。Gate 2 后修改冻结 Operation/DTO/枚举/错误/安全边界必须走非 Breaking 扩展、v2 或 API Change Request。|

## DEC-20260923-059

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-059|
|Date|2026-09-23|
|WBS|Gate 2：Architecture / Data Model / DB Schema V1 / API Contract V1 Freeze|
|Decision|依据用户明确指令“批准 Gate 2，冻结 Architecture、Data Model、DB Schema V1 和 API Contract V1”，将 `ARCH-CANDIDATE-V1`、`DATA-MODEL-CANDIDATE-V1`、`DB-SCHEMA-CANDIDATE-V1` 和 `API-CONTRACT-CANDIDATE-V1` 以提交 `64cdf09` 的内容冻结为正式开发基线。候选标识为保持历史 Trace 不重命名；Gate 2 对正式开发的阻塞解除，下一 WBS 为 Phase 1 `1.01 定义模块目录规范`。|
|Reason|AF-01～AF-05、DM-01～DM-06、SC-01～SC-05、API-01～API-05 已全部 PASS；跨层 22 Owner、65 Root、323 Operation、363 Method/Path、150 错误、18 SSE 和 20 Query 映射一致，API-05 Contract Lint 5/5 PASS。用户已完成正式 Gate 决策，满足进入基础工程的前置条件。|
|Impact|允许按 WBS 创建正式基础工程和业务实现；冻结后的总体架构、核心数据模型、DB Schema V1、Breaking API、技术栈、安全/License 机制或 Scope 变化必须走 L3 Change Request。批准不等于生产 ORM/Migration、运行 OpenAPI、性能、AI 质量、发行或 UAT 通过；POC-03 继续阻塞 Gate 3/UAT，Server Office、Debian 13、Ghostscript AGPL 发行合规和 SC-04 验证性边界继续保留。|
|Rollback|Gate 决策不得静默回退或通过技术提交抹除。若需撤销或修改冻结基线，必须由用户明确批准独立 Change Request，保留本决策、原冻结提交和全部历史证据；普通 Git revert 不改变该历史批准事实。|

## DEC-20260923-060

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-060|
|Date|2026-09-23|
|WBS|1.01 定义模块目录规范|
|Decision|采用单仓库双应用布局：客户运行代码放在 `apps/backend` 与 `apps/frontend`；后端使用 `src/plm_assistant` Python src layout，FastAPI 与 Worker 共用 22 个 `plm_assistant.modules.<module>` 模块；每个模块固定为 `api/application/domain/infrastructure` 四层，跨模块只允许目标模块 `application.public`。License/Plugin 签名和 Release 工具放在物理分离的 `tools/developer-workbench`，不进入客户运行包。未进入实现 WBS 的模块不创建空 package。|
|Reason|该布局直接承载冻结的模块化单体、22 Owner 和 API/Application/Domain/Adapter 依赖方向，同时避免 FastAPI 与 Worker 复制业务代码。独立 Workbench 路径能防止私钥工具误入客户包；按需创建模块可避免 22 组空目录和伪实现。|
|Impact|后续 1.02/1.03 分别在稳定的 backend/frontend 根创建 App；模块 WBS 必须遵循固定层次、测试镜像和依赖白名单。新增运行模块或把 Workbench 合并进客户运行包属于 L3；普通模块内子目录调整属于 L2。|
|Rollback|在尚无运行实现和 Migration 时，可删除新增骨架并恢复为纯文档仓库；若需变更顶层布局，先更新机器 manifest、验证和本决策的后继记录。不得借回滚改变冻结的 22 模块、信任区或依赖矩阵。|

## DEC-20260924-061

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-061|
|Date|2026-09-24|
|WBS|1.02 FastAPI app factory|
|Decision|后端采用无模块级全局 App 的 `create_app()` 工厂，由 Uvicorn `--factory` 加载；每个实例拥有独立的 lifespan 与 `HealthService`。只注册 `/health/live`、`/health/ready` 两个非业务健康端点，Swagger、ReDoc 和外部 OpenAPI 暂不暴露。Readiness 通过 Composition Root 注入同步/异步探针，未启动、探针返回非 True 或抛异常时统一失败关闭为最小 `503 {"status":"NOT_READY"}`。直接依赖固定为 FastAPI 0.141.1、Uvicorn 0.53.0，测试按 Starlette 1.7 要求使用 HTTPX2 2.13.1。|
|Reason|工厂模式避免测试、Worker 或多实例共享可变状态，并为后续 Config、DB Session、日志、Trace 和 Router 逐步装配提供稳定入口。健康面符合冻结 Contract 的最小披露原则；注入探针允许后续数据库/存储检查接入而不改变公开响应。固定已在 Python 3.13.14 验证的直接版本可减少三平台漂移。|
|Impact|当前运行面只有两个健康端点，不初始化数据库、License、Session 或业务模块；外部 OpenAPI 仍为 404，但 `app.openapi()` 可供后续 Contract diff 使用。1.04/1.09 可向工厂装配基础设施；1.06 负责正式错误 Contract，1.08 负责 TraceId。|
|Rollback|删除 WBS 1.02 新增 package/测试并恢复 backend README/pyproject 即可回到 1.01；不影响数据库或客户数据。更换 FastAPI/Uvicorn、改变健康路径或暴露额外未冻结 API 必须按依赖/API 变更规则重新评审。|

## DEC-20260924-062

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-062|
|Date|2026-09-24|
|WBS|1.03 Vue app shell|
|Decision|前端采用 Vue 3 + TypeScript + Vite 的单页应用壳，使用 Vue Router 维护首页与 catch-all 404；目录先建立 `app` 与 `shared` 两个公共层，不预建业务模块。浏览器仅通过 same-origin `/health/ready` 读取后端就绪状态，开发代理只指向本机 `127.0.0.1:8000`；不在浏览器存储 Secret、Token 或业务事实。固定 Node 24/pnpm 11 工具链和直接依赖版本，并以 lockfile 及 workspace override 将传递依赖 `ini` 固定为无已知漏洞的 1.3.8。|
|Reason|最小应用壳为后续认证、错误处理和业务模块提供稳定挂载点，同时避免在对应 WBS 前形成伪页面或客户端信任边界。same-origin 健康检查不会引入厂商调用或跨域凭据；固定依赖和安全 override 可复现当前 Windows 11 验证结果。|
|Impact|当前 UI 只包含产品导航骨架、后端连接状态、可访问性基础样式、安全错误边界和 404；没有登录、权限裁决、业务路由、数据库或外部 AI 调用。后续业务页面应放入 `src/modules` 并经正式 API/权限 WBS 接入，客户端显示权限不得代替服务端授权。|
|Rollback|删除 WBS 1.03 新增前端源码、测试、lockfile 和验证证据并恢复 frontend README 即可回到空前端目录；不影响数据库、后端或客户数据。更换冻结技术栈、引入跨域业务调用或改变 `/api/v1` Contract 必须按对应 L3/API 变更规则处理。|

## DEC-20260924-063

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-063|
|Date|2026-09-24|
|WBS|1.04 SQLAlchemy session|
|Decision|客户运行时采用同步 SQLAlchemy 2.0.54 + psycopg 3.3.5；每个进程持有一个 `DatabaseRuntime`/Engine Pool，每个 Application Command 使用一次性 `SqlAlchemyUnitOfWork` 和独立 Session/事务。事务 `autobegin=False`，进入 UoW 时显式 begin；只有显式 `commit()` 才提交，异常、遗漏提交或显式 rollback 均回滚，退出始终关闭 Session。连接池启用 pre-ping、return rollback、recycle 和有限超时，隔离级别固定 `READ COMMITTED`；只接受 `postgresql+psycopg`。数据库 URL 由 Composition Root 注入且所有展示隐藏密码，本 WBS 不读取环境或 Secret。|
|Reason|同步 Session 与 Phase 0/SC-04 已验证的 PostgreSQL/psycopg 路径一致，也可由 FastAPI 同步依赖和独立 Worker 共用一套事务边界，避免在基础阶段维护同步/异步双栈。显式 begin/commit、默认 rollback 和一次性实例能防止请求间 Session 共享、隐式提交及连接池污染；技术无关 Application Protocol 保持业务层不依赖 ORM。|
|Impact|`platform` 提供 UnitOfWork Contract、SQLAlchemy Adapter、连接健康检查和安全 URL；业务 Repository 只能在对应模块 Infrastructure 内使用当前 UoW Session，不得把 Session 跨线程/请求缓存。异步端点不得在事件循环中直接执行同步数据库 I/O，应使用同步依赖/执行边界。1.05 使用独立 Migration 角色建立正式 Alembic；1.09 负责 URL/Secret 与 Engine 生命周期装配。本任务未创建业务 ORM、表、Migration 或 API。|
|Rollback|删除 WBS 1.04 的 UnitOfWork/DatabaseRuntime、测试与验证材料并移除 SQLAlchemy/psycopg 依赖即可回到 1.03；当前无数据库对象或客户数据需要回滚。若未来以 AsyncSession 取代该基础边界，应提交后继 L2 决策和等价事务/并发验证；不得借此改变 PostgreSQL 18、Schema、安全角色或冻结业务模型。|

## DEC-20260924-064

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-064|
|Date|2026-09-24|
|WBS|1.05 Alembic migration|
|Decision|正式 ORM Base 固定 `plm` Schema 和 PK/FK/UQ/CK/IX 命名约定；Alembic 环境与 revision 作为 `plm_assistant.migrations` 包随 backend wheel 交付。首个不可变 revision 为 `20260924_0001`，只验证 PostgreSQL 18 并建立 pgvector 0.8.6 平台基线，不创建任何业务表。`plm.alembic_version` 位于应用 Schema；online/offline 环境先幂等建立 `plm` Schema。downgrade 到 base 删除 revision 记录，但按冻结恢复边界保留空 `plm` Schema、版本表和共享 pgvector 扩展。迁移 URL 仅通过内存 Config attribute 注入，`alembic.ini` 不保存凭据。|
|Reason|WBS 1.05 需要建立可发行、可审计的正式 Migration 链，但 DB Schema V1 明确要求业务表按模块 WBS 逐项细化，禁止复制 SC-04 的 70 张验证表。先冻结 Schema/版本表/扩展/命名与打包机制，既能满足后续 revision 前置，又不会把 Profile 占位结构冒充生产 ORM。保留共享扩展和空 Schema 与冻结 SC-04 恢复边界一致，也避免 downgrade 破坏其他 revision 或数据库能力。|
|Impact|后续每个模块数据库任务必须继承此 Base、以新 revision 增量变更并完成 ORM、空库/有数据 up/down、漂移和恢复验证。Runtime Role 不得调用本迁移入口或拥有 DDL/版本表写权限；1.09 再装配 Secret/配置与部署命令。本 revision 不关闭 65 Root 正式 ORM、业务约束、索引或权限验证风险，当前业务表数量仍为 0。|
|Rollback|可执行 downgrade 到 base 清除 revision 记录；空 `plm` Schema、版本表和 pgvector 作为平台前置按设计保留，不包含客户数据。代码回退可移除迁移包与 Alembic 依赖。只有在确认没有后续 revision、业务对象或其他扩展依赖时，管理员才能通过独立维护步骤移除这些前置；不得在普通 downgrade 中级联删除。|

## DEC-20260924-065

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-065|
|Date|2026-09-24|
|WBS|1.06 Error contract|
|Decision|平台层建立受控错误码目录和统一 FastAPI 异常处理。已分类的 ApplicationError 按冻结 API-01 通用码返回；未分类异常固定为 SYSTEM_INTERNAL，Pydantic 校验只返回安全的 400/422 而不暴露原始输入。普通 HTTP 403 隐藏为与不存在资源一致的 404；CSRF、License 等已分类错误保留冻结的 403。框架 405 使用新增的兼容错误码 REQUEST_METHOD_NOT_ALLOWED，不修改任何冻结码语义。响应固定为 `error.code/message/details` + `trace_id`，并同步 `X-Trace-Id`、禁止缓存；在 WBS 1.08 Trace 中间件接入前，复用规范 UUID 请求头或生成 UUIDv7。|
|Reason|统一封装可以防止框架异常明文、校验原值、权限存在性、堆栈与内部路径进入公开响应，并为后续模块提供稳定的错误边界。405 使用独立码比错误地归类为请求格式错误更精确，属于 API-01 允许的非破坏性扩展。|
|Impact|只改变错误响应，不新增公开业务路由或数据库对象；两个健康端点的冻结最小响应保持原样。后续模块需先登记自己的业务错误码再使用；1.07 增加服务端脱敏日志，1.08 统一整个请求生命周期的 TraceId。|
|Rollback|移除平台错误目录、异常处理注册和对应测试，即恢复 WBS 1.05 行为；当前无数据迁移。若改变已冻结 `/api/v1` 错误 Envelope 或已有错误码语义，须走 API Change Request/L3。|

## DEC-20260924-066

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-066|
|Date|2026-09-24|
|WBS|1.07 JSON log|
|Decision|平台日志使用两个独立、由 Composition Root 注入的 JSON 行输出流，分别记录 Application 与 Integration 事件；不改 Python root logger，也不以自由文本格式化异常。写入 API 只接受登记事件、受控集成类型/Provider、规范 UUID、固定格式错误码和非负耗时，输出字段由代码白名单构造。未分类 API 异常记录 `request_failed`、`SYSTEM_INTERNAL` 与响应同一 TraceId，不记录 exception、request body、URL、SQL 或路径；日志写入失败不改变安全错误响应。Audit 保持独立，未来由 audit 模块写 PostgreSQL。|
|Reason|自由文本和第三方异常拼接易把 Secret、客户正文、绝对路径或 Provider 原始响应写进普通日志；事件/字段白名单在写入前拒绝不受控数据。按应用/集成分流可保持权限、保留期和排障职责分离，且不抢占后续 Audit、Trace、Config WBS。|
|Impact|仅增加平台日志能力和未分类 API 失败的安全记录；未新增业务 API、数据库对象或网络调用。当前记录不含请求性能、Actor/Project 等上下文；WBS 1.08 Trace 中间件和后续业务模块逐步接入受控字段。默认 Application 输出 stdout、Integration 输出 stderr；正式部署的收集、保留与访问控制由 Release 阶段配置。|
|Rollback|移除日志模块、App Factory 注入及异常处理中的安全记录即可恢复 WBS 1.06；无数据迁移。未来需要新 Provider 或事件时先扩充受控目录及测试，不允许改成任意消息透传。|

## DEC-20260924-067

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-067|
|Date|2026-09-24|
|WBS|1.08 TraceId middleware|
|Decision|采用纯 ASGI Trace 中间件，在每个 HTTP 请求入口只解析一次 `X-Trace-Id`：仅单个规范 UUID 可复用，缺失、格式无效或重复请求头一律生成 UUIDv7。TraceId 同时写入 `request.state` 与 ContextVar，响应头统一回传；上下文在请求结束后恢复，供 Application 和后续受控集成调用读取。新增受控 `request_completed` Application Log，仅记录 TraceId、HTTP 状态和非负耗时，不写 URL、Header 或正文。健康端点只增加响应头，不改变冻结的最小 body。|
|Reason|单次入口解析防止错误处理、业务代码和日志各自生成不同 TraceId；纯 ASGI 包裹整个响应发送过程，可覆盖同步/异步请求及流式响应，ContextVar 避免并发请求污染。重复请求头不能有歧义，按无效值处理更安全。|
|Impact|所有 HTTP 响应增加 `X-Trace-Id`；错误正文继续由 WBS 1.06 固定 Envelope 保持相同值。未来正式业务成功 JSON 仍须按冻结 API-01 由业务响应层提供 `data` 与 `trace_id`，中间件不会改写响应正文。当前无 Job/AI/Plugin/Audit 实例；后续入口应显式继承已验证的 TraceId，不能把它当授权或幂等凭据。无业务路由、数据库或外部调用变化。|
|Rollback|移除中间件装配、Trace 上下文及新增日志字段即可恢复 WBS 1.07；WBS 1.06 错误响应仍保留独立 Trace 回退。若需改变冻结的 Trace Header/Envelope 语义，必须走 API Change Request/L3。|

## DEC-20260924-068

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-068|
|Date|2026-09-24|
|WBS|1.09 Config/Secret|
|Decision|基础工程先实现非敏感 Bootstrap 配置与 Secret 单次访问边界，不提前创建 PLT-01/PLT-02 正式业务表/API。Bootstrap 采用基线建议的 pydantic-settings 2.15.0 与 PyYAML 6.0.3，显式加载受限 UTF-8 YAML、`PLM_` 环境变量，开发 `.env` 仅在调用者明确传入时读取；重复/未知键、未知环境字段、危险 YAML tag、超限文件或非法类型失败关闭，错误消息固定脱敏。密钥、密码、Token 不进入 Bootstrap schema。Secret 只用 `SecretRef`，按受控 Purpose/Consumer、ACTIVE、版本与密文元数据检查后调用注入的解密 Port；Audit Port 是必需依赖，失败关闭；明文仅作为单次调用的可变缓冲区使用并在退出时清零。加密算法、持久密文仓库与 Windows/Linux SecretKeyProvider 保持未实现，遵照冻结方案留待 PLT-02 与 Release 安全设计，不把当前 Port 冒充生产 Secret Store。|
|Reason|现有正式 Migration 仅是无业务表的平台基线，PLT-01/PLT-02 的版本化实体和 Audit 尚未实施；在 1.09 直接写持久 Secret 或私自选定平台主密钥机制会跨 WBS 且掩盖 Gate 风险。先锁定非敏感配置来源和失败关闭的单次访问契约，可让后续 DB/AI Adapter 使用统一引用，同时避免把明文配置或测试密钥写入 Git。pydantic-settings/YAML 选型直接落实已批准技术建议，不引入新的商业授权或更改安全基线。|
|Impact|backend 增加两项固定直接依赖和一个不含 Secret 的示例模板；无数据库对象、业务 API、真实密钥、外发或生产加密能力。App Factory 目前不自动从 YAML/.env 读取，也不以缺失的 SecretKeyProvider 假装连接数据库；PLT-01/PLT-02 后续 Task 必须实现正式 ORM/Migration、权限/API、审计、密文与主材料分离及恢复验证，才能标记生产 Secret 可用。|
|Rollback|移除 Bootstrap/Secret 边界代码、示例、测试及两项依赖即可回到 WBS 1.08；无数据迁移。任何把密钥写入 YAML/.env 发行包、弱化 Secret 消费方授权或改变冻结 PLT-01/PLT-02 API/数据语义的方案必须走对应 L3 Change Request。|

## DEC-20260924-069

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-069|
|Date|2026-09-24|
|WBS|PLT-01-A01 SystemConfiguration ORM/Migration|
|Decision|将本任务严格限定为 PLT-01 的非敏感配置身份表与不可变版本表；Root Active Version 使用同父复合 FK，Version 的 UPDATE/DELETE 用数据库触发器拒绝，已有配置数据的 Alembic downgrade 失败关闭。Settings/RetentionPolicy/RetentionHold 子表、版本命令、DeploymentAdmin 授权、Audit 与敏感值识别留给后续独立 WBS。配置值物理形状暂用 STRING/INTEGER/BOOLEAN/JSON 四类 JSONB 约束；应用层必须进一步校验 INTEGER 语义及禁止 Secret/客户正文。|
|Reason|SC-01/02 冻结了聚合所有权、M-DEP 和不可变版本约束，但未冻结 PLT-01 每个子表的完整业务字段与命令实现。先交付可独立验证的身份/版本存储，不把未实现的权限或敏感值检测称为已完成。拒绝含数据回退可避免默认 DROP TABLE 静默丢失正式配置历史。|
|Impact|新增正式 Alembic `20260924_0002` 和两张 `plm` 表；`retention_policy_id` 保留 nullable 占位，目标子表落地前不具备外键/保留策略功能。无公开 API、客户数据外发或冻结基线变更。后续业务命令在开放前必须补齐非敏感值筛查、单调版本分配、乐观并发、权限与 Audit。|
|Rollback|空表可降级到 `20260924_0001`；含配置数据拒绝回退，须经备份和受控数据迁移/恢复流程处理。不得通过禁用不可变触发器来绕过正式版本历史。|

## DEC-20260924-070

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-070|
|Date|2026-09-24|
|WBS|PLT-01-A02 配置版本命令与仓储边界|
|Decision|只交付内部创建/激活版本命令与 SQLAlchemy 仓储，不提前暴露管理 API。受控配置值使用开发者拥有的键、Schema 版本、类型及精确值白名单；不提供任何默认可写策略，也不允许客户请求动态登记策略。写命令必须注入部署写授权 Port 和同事务 Audit Port，主记录行锁序列化版本号并以 lock_version 防陈旧写。A01 已发布迁移不可改写，以新增 `20260924_0003` 为不可变版本补充 API-02 已冻结要求的 `schema_version`。|
|Reason|冻结 API 要求非敏感值、Schema 版本、乐观锁、DeploymentAdmin 和强制 Audit；当前真实 Auth/License/Audit/Idempotency 适配器未落地。白名单与 Port 失败关闭使内部逻辑可验证，又不把测试替身冒充生产安全能力。版本数只由锁定的 Root 分配，避免并发产生重复或跳号。|
|Impact|A01 旧数据升级时 Schema 版本安全归为 1；有非初始 Schema 版本时拒绝回退到 `0002`。当前无公开 API、客户数据外发、新依赖或冻结基线改变；配置身份创建、持久幂等、真实认证/License/CSRF/Audit 和默认策略留给后续 WBS。A01 `version_state` 被解释为版本可用性，生效版本只由 Root 指针决定，避免更新不可变历史。|
|Rollback|移除内部命令、仓储和策略代码即可撤回未暴露功能；数据库 `0003` 仅在所有记录 Schema 版本为 1 时可安全降级到 `0002`，否则先完成受控备份/迁移，不强制删除或改写正式历史。|

## DEC-20260924-071

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-071|
|Date|2026-09-24|
|WBS|PLT-01-A03 配置身份与幂等命令|
|Decision|为已冻结的 API-01/02 幂等要求，增加 PLT-01 技术性命令收据表，不新增 Aggregate Root 或客户业务实体。以 `(actor_id, operation, SHA-256(Idempotency-Key))` 唯一约束确定部署范围内重放；只存规范请求 SHA-256 和结果引用，原始键/值不持久化。`INSERT ... ON CONFLICT DO NOTHING` 在同一事务中预约收据，随后配置写入、Audit Port、完成收据原子提交；完成收据由专用触发器禁止 UPDATE/DELETE，源 FK 设置索引。含收据数据的迁移回退失败关闭。|
|Reason|冻结 API 明确同键同 payload 返回原结果、不同 payload 返回冲突，而进程内字典无法跨重启/并发保证。技术表只承载请求去重事实，不改变 PLT-01 业务聚合的 Root/Version/Retention 映射；摘要化避免 Idempotency-Key 误含敏感材料时明文留库。事务收据确保 Audit 失败也不会留下假的成功重放。|
|Impact|新增普通增量迁移 `20260924_0004`；A02 内部命令签名增加必填 idempotency_key，仍无公开 API、客户数据外发或新第三方依赖。正式 Auth/License/CSRF/AuditEvent 和受控 Retention 尚未接入，命令不得对外开放。Phase 1 基础工程按实施方案收口并写阶段总结，转入 Phase 2 AuditEvent；Gate 3 不自动通过。|
|Rollback|空收据表可降级到 `0003`；有收据时必须先备份并完成受控恢复/迁移，不允许普通 downgrade 删除重放历史。移除本任务内部命令修改不影响 A01/A02 已保存的配置主记录和不可变版本。|

## DEC-20260924-072

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-072|
|Date|2026-09-24|
|WBS|AUD-01-A01 AuditEvent ORM/Migration|
|Decision|AUD-01 首步只提供真实存储模型，不开放写/查 API。Audit Root 保持 DEPLOYMENT Owner Scope；`event_scope` 标示被审计操作的部署或项目上下文，PROJECT 必填 `target_project_id`，DEPLOYMENT 不得填写。多态目标在库内固定为冻结的 65 个客户运行 Root 类型或全空（无可定位对象的认证失败），不包含 Developer Workbench。仅存受控 action/outcome/reason/state 码、标识与可选 SHA-256 主体提示摘要，不存请求正文、Secret、文件或完整 AI 输入输出。数据库触发器禁止普通 UPDATE/DELETE/TRUNCATE；非空 downgrade 拒绝。|
|Reason|冻结模型要求 AuditEvent 只追加、项目隔离、来源可追溯和最小安全摘要；冻结 SC-02 允许部署 Owner 与项目目标并存，SC-03 固定三组索引。当前 Auth/Project/License 未落地，外键或真实权限不能伪造；安全码替代任意自由文本，避免向审计库复制敏感内容。|
|Impact|新增迁移 `20260924_0005` 和一张 `plm` 表；无冻结基线变更、新依赖、公开 API 或客户数据外发。数据库管理员仍有 DDL 权限，因此触发器不是防篡改封存；AuditService 权限/事务 Port、读隔离、Retention/Legal Hold 和备份权限控制留待对应 WBS。|
|Rollback|空表可回退到 `0004`；含审计事件时须备份并进行受控恢复/迁移，普通回退失败关闭，不能删历史记录换取迁移通过。|

## DEC-20260924-073

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-073|
|Date|2026-09-24|
|WBS|AUD-01-A02 AuditService append Port/Repository|
|Decision|Audit 的跨模块公开入口仅暴露只追加 AuditService 与不可变 AuditEventDraft；Audit 模块内部 Port/SQLAlchemy 仓储不对业务模块开放。Service 接收调用方已开启的事务并直接插入，不创建、提交或补偿第二事务。输入只接受 UUID、受控大写码、结构化目标和可选 32 字节主体提示摘要；数据库白名单与 append-only 触发器作为第二层约束。|
|Reason|冻结 DM-02 要求强制审计与业务状态同事务提交，且只由 AuditService 追加。由业务用例掌握事务可避免 Audit 成功而业务回滚或相反；自由文本会扩大敏感内容进入审计库的风险。Auth/License/Project 权限仍未落地，本任务不以测试替身伪装成公开可用写入口。|
|Impact|只新增 Audit 模块 Application/Domain/Infrastructure、测试与验收脚本；A01 迁移与冻结 API 不变，无新依赖或客户数据外发。业务命令只有在真实权限和 Audit 适配器接线后才能开放。下一项单独完成只读查询及项目隔离。|
|Rollback|移除 A02 新增服务、Port、仓储和测试即可退回 A01；已提交的审计事件仍由 A01 append-only 表保护，不得清理历史以撤销代码。|

## DEC-20260924-074

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-074|
|Date|2026-09-24|
|WBS|AUD-01-A03 审计只读查询与项目隔离|
|Decision|内部 AuditQueryService 必须注入权限 Port 并在 Repository 查询前检查；Project 读取固定 `event_scope=PROJECT AND target_project_id=授权项目`，部署读取固定 `event_scope=DEPLOYMENT AND target_project_id IS NULL`，DeploymentAdmin 不自动读取项目 Audit。时间查询要求显式、最多 31 天，页大小 1～200，排序固定 `occurred_at DESC, audit_event_id DESC`；内部 keyset position 不作为公开游标，对外签名/Scope/查询指纹绑定在未来 HTTP API 任务中实现。投影排除主体提示摘要。|
|Reason|冻结 API-01/02 要求权限先行、项目隔离、受控筛选、完整性保护分页和不暴露敏感材料；SC-03 已冻结对应 Audit 索引。真实 Auth/License/Session 尚未落地，当前不提供公开路由或伪造权限适配器。31 天上限是可回滚的内部初值，控制无界查询，不改变冻结外部 API 语义。|
|Impact|只新增 Audit 内部查询与测试，不改 A01 Schema/索引或冻结 `/api/v1`。权限 Port 必须由后续真实认证/项目授权实现；公开 API 上线前还必须加入签名游标及 Scope/查询指纹校验。审计导出另行 WBS 实施。|
|Rollback|移除内部查询 Service/Repository 和测试即可回到 A02；不删除审计事件，也不改变已冻结查询索引。|

## DEC-20260924-075

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-075|
|Date|2026-09-24|
|WBS|AUT-01-A01 User/Credential ORM/Migration|
|Decision|User Root 先以 DISABLED、credential_version=0、无当前凭据建立，随后同事务追加不可变 PasswordCredential 版本并由复合 FK 指向本 User 的相同版本；只有存在当前凭据才可 ENABLED。用户名展示值与规范值分列，规范值部署内普通唯一，停用不释放。凭据只保存不可逆 Hash、算法 ID、非敏感参数、版本和变更时间；算法选择/哈希验证由后续专门任务完成，不以本迁移中的合成测试值作为生产方案。数据库触发器禁止凭据历史 UPDATE/DELETE/TRUNCATE 与 User 凭据版本倒退；非空 downgrade 拒绝。|
|Reason|冻结 DM-02/SC-01～03 要求身份与凭据版本分离、唯一用户名、一个有效凭据和 Session 凭据版本失效。先创建 DISABLED Root 避开循环 FK 插入顺序，同时由复合 FK 阻止把别人的或旧版本凭据设为当前；不得在 Schema 任务中假装选定密码算法或开放登录。|
|Impact|新增正式迁移 `20260924_0006` 与两张 Auth 表，无新依赖、公开 API、客户数据外发或冻结基线变更。Unicode trim/NFC/casefold、密码 Hash 策略、命令授权/审计、Session 失效须由后续 WBS 实现并验证；原始密码和哈希不得进入 DTO/Audit/日志。|
|Rollback|空 Auth 表可降级到 `0005`；一旦有身份/凭据历史，普通 downgrade 失败关闭，必须先备份并通过受控恢复/迁移处理，不删除账号历史。|

## DEC-20260924-076

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-076|
|Date|2026-09-24|
|WBS|AUT-01-A02 User/Credential 内部命令与规范化|
|Decision|本项只实现内部 User 创建，不提前实现登录、重置密码、停用/启用或公开管理端点。用户名以 `strip → NFC → casefold → NFC` 得到规范值，拒绝空值、控制字符及 Schema 长度越界；数据库唯一键处理并发重名。命令必须注入同事务权限、密码 Hash 和 AuditService，先授权再哈希/写库；初始凭据版本为 1，默认普通部署角色。Hash 结果只允许受控算法 ID、非敏感整数参数和限定长度编码值；不内置或宣称生产算法。原始密码从调用方可变 UTF-8 缓冲区传入并在成功/失败后尽力清零。|
|Reason|冻结 DM-02/API-02 要求服务端 canonical username、DeploymentAdmin 授权、write-only 密码、同事务 Audit 和凭据版本。生产密码算法、Session/License 和持久幂等尚未落地；独立 Port 与无公开路由可验证创建流程及失败关闭，同时避免在普通实现任务中擅定安全核心机制。|
|Impact|新增 Auth Domain/Application/Repository 与合成测试；不改 A01 Schema、冻结 API 或技术栈，无新依赖/真实客户数据外发。只有未来正式 Hash Adapter、真实 Auth/License/Session 授权和幂等收据就绪后才能开放 `AUTH_USER_CREATE`；测试算法 `TEST_ONLY` 不属于生产支持。Python/第三方组件可能复制密码缓冲区，清零不是内存绝对擦除承诺。|
|Rollback|移除内部命令、仓储及测试即可回到 A01；已有 User/Credential/Audit 历史不能因代码回退而删除，须继续遵守 A01 非空 downgrade 拒绝。|

## DEC-20260924-077

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-077|
|Date|2026-09-24|
|WBS|AUT-01-A03 生产密码哈希与凭据校验|
|Decision|首版采用 Python 3.13/OpenSSL 标准库 `hashlib.scrypt` 固定 V1 Profile：每条凭据 16 字节独立随机盐、`N=2^17,r=8,p=1,dklen=32`、256 MiB `maxmem` 上限、自描述编码与独立 `algorithm_id/parameter_set` 一致性校验。Verifier 只接受本 Profile，拒绝由数据库记录选择任意耗时参数，使用 `hmac.compare_digest` 比较导出值。密码输入上限同步收紧为 1024 字节；保留既有 Port，使将来算法升级新建 Profile/版本，不静默重写旧凭据。无 Argon2id 第三方依赖或安全基线替换。|
|Reason|冻结方案要求不可逆 PasswordHasher，但未规定库与参数。[OWASP 密码存储建议](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)首选 Argon2id，标准库可用时推荐的 scrypt Profile 为 `N=2^17,r=8,p=1`；[Python 3.13 `hashlib` 文档](https://docs.python.org/3.13/library/hashlib.html)提供 scrypt 与显式内存限制。此选择不新增重要第三方依赖，属于当前已批准安全机制的具体实现；对畸形参数失败关闭避免存储内容触发资源耗尽。|
|Impact|新增 Auth Infrastructure Hash/Verifier，无 Schema、API 或新依赖；本机单次创建约 317ms 仅为观测，不代表三平台吞吐或安全审计通过。每次哈希约需 128 MiB 工作内存，公开登录前仍必须实现 Origin/Host/限流、Session/CSRF、License/权限、统一失败响应和平台负载验收。Python/OpenSSL 可能复制密码字节，调用方清零不保证绝对擦除。|
|Rollback|移除新适配器可返回仅 Port 的 A02，但已保存的 `SCRYPT` 凭据将无法验证；上线后不得直接撤销而不提供兼容验证或受控凭据迁移。普通代码回滚不删除用户/凭据历史。|

## DEC-20260924-078

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-078|
|Date|2026-09-24|
|WBS|AUT-02-A01 Session ORM/Migration|
|Decision|Session 为部署级运行聚合，物理表只存 32 字节 Session Token 摘要与 CSRF 绑定摘要，不存 Cookie/CSRF 原值。`(user_id,credential_version)` 复合 FK 指向不可变 PasswordCredential 历史，Session 是否仍有效还须后续服务重新检查 User ENABLED、当前凭据版本、绝对/空闲到期与撤销。`state` 由时间/撤销事实派生，不持久化。Token 摘要唯一，额外 `(user_id,revoked_at)` 索引用于用户全会话撤销；更新触发器禁止身份/摘要/绝对期限替换、last_seen/idle 倒退及撤销复活。|
|Reason|冻结 DM-02/API-02 要求服务端 Session、Token/CSRF 不可逆摘要、凭据变化使旧 Session 失效和撤销不可恢复；SC-02 R-DEP Profile 允许专用列覆盖通用状态。复合 FK 保留历史版本，但不能代替实时 User 状态校验；避免误把数据库行存在等同于已认证。验收中显式补上 `revoke_reason IS NOT NULL`，以防 PostgreSQL CHECK 对 NULL 的 UNKNOWN 结果放行。|
|Impact|新增普通增量迁移 `20260924_0007` 和一张 Session 表，无冻结 API/架构变更、新依赖或客户数据外发。真实 Token 生成/哈希、Cookie/CSRF、续期/撤销及 License/项目授权均须后续独立 WBS 实现；当前仅持久层，不可开放登录。|
|Rollback|空表可降级到 `0006`；含 Session 记录时普通 downgrade 拒绝，必须备份并走受控恢复/迁移，不删除历史以强制通过。|

## DEC-20260924-079

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-079|
|Date|2026-09-24|
|WBS|AUT-02-A02 Session 签发/校验/撤销内部服务|
|Decision|内部 Session 签发须由注入的 `SessionIssueAccessPort` 对当次认证证明、User 和当前凭据版本作明确许可；没有生产适配器时不得开放登录。每次生成独立 32 字节随机 Token/CSRF，数据库只存各自 SHA-256 摘要。内部默认绝对期限 8 小时、空闲期限 30 分钟，允许受控配置但上限 24 小时且空闲期不超过绝对期；本任务校验不滑动空闲期。校验实时重查 User ENABLED、当前凭据版本、撤销及双期限；撤销需有效 Token 与绑定 CSRF，更新与 Audit 同事务。|
|Reason|冻结 DM-02/API-02 规定服务器端 Session、凭据变化失效、CSRF 和审计，但未固定内部期限数值。保守初值与强制认证证明 Port 防止仅凭 UserId 签发；无公开路由避免跳过 Origin/Host、限流、Cookie 与 License。固定 Token 长度使摘要存储和输入检查简单；原值不进入数据库或 Audit。|
|Impact|新增 Auth Application Service、Auth Infrastructure Repository、单元及 PostgreSQL 临时库验证；无 Schema/Migration、公开 API、第三方依赖或客户数据外发。Cookie 设置、Origin/Host、真实密码证明/License 适配、登录限流、续期轮换、全会话管理员撤销及项目授权仍需后续任务，当前不能开放真实登录。|
|Rollback|未接入公开入口，移除本服务/适配器即可回退代码；已签发 Session 的撤销历史及 Audit 不删除。调整期限需安全评估和兼容测试，不改变冻结的摘要/凭据版本机制。|

## DEC-20260924-080

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-080|
|Date|2026-09-24|
|WBS|AUT-02-A03 Session 续期轮换|
|Decision|把已冻结 API-02 的 Session 续期轮换细化为独立内部 WBS A03。仅有效 Session + 绑定 CSRF 可续期；在单一数据库事务中先将旧记录撤销为 `RENEWED`，再创建独立随机 Token/CSRF 的新记录及 Audit。新记录继承旧会话绝对到期时间，仅将空闲期限延至 `min(当前时间+空闲期, 原绝对期限)`；因此轮换不能无限延长认证会话。新旧 Token 或 CSRF 发生重复则失败关闭。|
|Reason|冻结 API-02 已规定 `AUTH_SESSION_RENEW` 必须轮换；A02 仅实现初始签发/校验/撤销。将轮换独立验收符合一 WBS 一问题。继承绝对期限可保留“绝对到期”的安全含义，而同事务写入保证 Audit 或新记录失败时旧 Session 继续有效，不出现半轮换。|
|Impact|仅变更内部 Auth Application Service 与测试，无 Schema/Migration、公开 API、外部依赖或客户数据外发。Cookie 原子替换、多标签行为、Origin/Host、限流、License、真实登录与管理员撤销仍未接入，不能宣称对外续期已可用。|
|Rollback|未接入公开路由，可移除内部续期命令；既有 Session/Audit 历史不删除。|

## DEC-20260924-081

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-081|
|Date|2026-09-24|
|WBS|AUT-02-A04 Session 管理员批量撤销|
|Decision|将冻结 API-02 的 `AUTH_USER_REVOKE_SESSIONS` 底层能力拆为内部 A04。服务必须注入真实管理员权限 Port，验证 actor 的 Session、License、DeploymentAdmin 后，锁定目标 User 行并批量撤销该用户尚未撤销的 Session；单次 Audit 与撤销同事务。未注入生产权限适配器时默认拒绝。重复调用返回本次实际撤销数 0，并保留审计，不删除历史。|
|Reason|Session 签发已锁定 User 行；管理员批量撤销采用相同 User 行锁以序列化并发签发，避免撤销时漏掉已在提交中的新 Session。权限 Port 阻止凭 UserId 直接执行高权限命令；单事务 Audit 避免无证据的状态变更。|
|Impact|新增 Auth 内部管理员撤销命令与 Repository、测试；无 Schema/Migration、公开路由、第三方依赖或客户数据外发。`AUTH_USER_DISABLE` 仍需在未来 User 状态命令里与撤销同事务接线；生产权限/License/CSRF 尚未接线，此内部命令不能直接暴露为 API。|
|Rollback|移除内部命令可回退代码；已撤销 Session 不可恢复，Audit 历史不得删除。|

## DEC-20260924-082

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-082|
|Date|2026-09-24|
|WBS|AUT-02-A05 生产密码证明适配|
|Decision|将原候选“生产认证证明与权限接线”拆分：A05 仅实现内部 Session 签发的真实密码证明，管理员权限适配须待 LicenseService 形成后另列任务。`PasswordIssueProof` 持有短时可变字节缓冲区且不显示于 repr，Session 签发结束无论成功、拒绝或异常均清零。Auth Infrastructure 在同一事务中只对 ENABLED User 的当前 PasswordCredential 调用已批准 scrypt Verifier；错误/畸形证明统一拒绝，无密码或哈希进入 Audit、Session 或日志。|
|Reason|冻结 API-02 允许 License 无效时登录，但管理员业务接口仍需有效 License；当前仓库没有正式 License 模块，不能用测试许可绕过。把密码证明单独验收可完成不受阻塞部分，又避免把未实现的 License/权限或 Origin/Host/限流误报为已可用。|
|Impact|新增 Auth 内部密码证明 DTO、Verifier Port、SQLAlchemy 适配、测试；无 Schema/Migration、公开 API、第三方依赖或客户数据外发。密码缓冲区清零不承诺 Python/OpenSSL 内部副本绝对擦除。公开登录仍需用户名解析、统一失败/审计、Origin/Host、限流、Cookie/CSRF 等后续工作；管理员权限接线仍依赖 License。|
|Rollback|未接入公开路由，移除适配器可回退；不修改现有 Credential/Session 历史。|

## DEC-20260924-083

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-083|
|Date|2026-09-24|
|WBS|LIC-01-A01 LicenseInstallation ORM/Migration|
|Decision|按冻结 SC-01/DM-02 建立 `lic_installations` 与不可变 `lic_installation_documents`。签名文档以最多 64 KiB 原始字节快照与 32 字节 SHA-256 摘要保留，关联 `public_key_ref`，不存公钥私钥或原始 MAC；每次安装独立 UUIDv7。状态限 `IMPORTED/ACTIVE/SUPERSEDED/REJECTED`，partial unique 保证至多一个 ACTIVE；进入非 IMPORTED 状态须有验证结果引用。更新触发器只允许 IMPORTED→ACTIVE/REJECTED、ACTIVE→SUPERSEDED 及受控同态验证引用更新，终态不可复活；文档禁止更新/删除，安装历史禁止删除。INSERT 不设只允许 IMPORTED 的触发器，以保证含 ACTIVE 历史的备份恢复；初始导入状态由未来受控服务保证。|
|Reason|冻结模型要求签名文档历史、单一 ACTIVE、不可变签名内容和私钥隔离，但未固定长度与具体列。64 KiB 是可调整的 L2 存储上限；原始字节避免 JSON 重新序列化破坏签名材料。用数据库约束守住状态/单例及历史更新，避免恢复时触发器拒绝历史状态。|
|Impact|新增两张正式 License 表与迁移 `20260924_0008`；无公开 API、验签/激活服务、新依赖或客户数据外发。`validation_result_ref` 待 LIC-02 建表后加正式关联与验证来源检查；仅有非空 UUID 不证明签名、机器、时间或 License 有效。测试使用明确标注的合成无效签名文档，只验 Schema，不构成 License 验证。|
|Rollback|空表可降级至 `0007`；存在安装或文档历史时普通 downgrade 拒绝，必须备份并按受控恢复方案处理，不删除历史以强制降级。|

## DEC-20260924-084

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-084|
|Date|2026-09-24|
|WBS|LIC-01-A02 Ed25519 签名真实性预检|
|Decision|用户已在本轮明确批准将 POC-09 验证的 `cryptography 50.0.1` 纳入后端生产依赖。原候选“签名文档验证与受控导入”拆分：A02 仅实现最多 64 KiB 签名文档的严格 UTF-8/JSON envelope 与 Ed25519 签名真实性校验；公钥只能由注入的可信 `PublicKeyResolverPort` 按引用提供，不接受请求自带公钥。采用 POC-09 的 UTF-8、字段排序、紧凑分隔符确定性 Payload 序列化；重复 JSON 键、非标准数值、畸形签名、未知公钥、超深/超量载荷均失败关闭。返回类型明确标记仅为 `SignatureVerifiedDocument`，不提供 License `VALID` 或 Entitlement。|
|Reason|当前 LIC-02 验证事件、LIC-03 可信时间、正式机器/产品/功能规则与受控导入事务尚未实现；仅签名正确不能当作有效授权。拆分使已批准的密码学依赖可独立验收，同时不越过冻结的机器指纹与可信时间信任边界。|
|Impact|正式后端新增已获用户批准的 `cryptography==50.0.1` 直接依赖及 License 内部验签组件；无 Schema/Migration、公开 API、私钥落盘或客户数据外发。生产公钥配置装配、语义 Schema/产品/功能/机器/有效期/可信时间校验、导入历史/Audit/激活仍属后续任务；测试私钥只在测试进程内即时生成，不序列化。|
|Rollback|尚未接入公开路由或 License 状态决策，可移除验签组件与依赖；不修改 License 安装历史。若未来替换 Ed25519 核心机制必须走 L3，不由本决策授权。|

## DEC-20260924-085

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-085|
|Date|2026-09-24|
|WBS|LIC-02-A01 LicenseValidationState ORM/Migration|
|Decision|建立部署级单例 `lic_validation_states` 与追加不可变 `lic_validation_events`，验证码至少覆盖冻结 DM-02 的八类，并增加产品不符/可信时间状态损坏安全分类。`VALID` 行必须具备活动安装引用、32 字节机器指纹摘要、事件引用、对象型权益快照与验证时间；但这些列形状不代替密码学/机器/时间验证。状态变更要求新事件引用、版本单调加一和更新时间不倒退。安装记录的 `validation_result_ref` 在本迁移升级为指向验证事件的正式 FK；验证事件的可选 `installation_id` 保留可查询来源引用但不反向设 FK，以避免安装↔事件外键循环阻断备份恢复。已有非空且无对应事件的旧引用在升级前拒绝，要求受控核对。|
|Reason|冻结 SC-01/DM-02 要求当前安全状态与不可变验证历史分离；单例与 VALID 必备形状可在数据库失败关闭。单向 FK 既落实安装结果指针的来源完整性，又让事件→安装→状态按依赖顺序恢复；事件来源 ID 的匹配关系由未来 LicenseService 在同事务检查，不可凭事件行自行放行。|
|Impact|新增两张正式 License 表与迁移 `20260924_0009`；无公开 API、实际授权判定、新依赖或客户数据外发。测试仅使用合成验证事实，即使状态行标为 VALID，也不代表真实有效授权；TrustedTimeState 与 LicenseService 仍未实现。|
|Rollback|空表及无新验证 FK 引用时可降级到 `0008`；有状态或事件历史时普通 downgrade 拒绝，须备份并受控恢复，不删除验证历史。|

## DEC-20260924-086

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-086|
|Date|2026-09-24|
|WBS|LIC-03-A01 TrustedTimeState ORM/Migration|
|Decision|按冻结 DM-02/SC-01 建立 `lic_trusted_time_states` 部署单例与追加不可变 `lic_trusted_time_events`。单例初态允许尚未成功验证的空时间、版本 0；前移后必须有 UTC 成功时间、正版本、对象型完整性元数据及事件引用。更新触发器要求身份不变、时间严格前移、版本恰好 +1、事件引用变化及更新时间不倒退；事件禁止 UPDATE/DELETE/TRUNCATE，状态禁止 DELETE/TRUNCATE。事件结果码仅要求非空且限长，不在存储层提前冻结 License 分类或完整性算法。|
|Reason|冻结基线要求原子 expected_version、单调时间和追加检查事件，但完整性算法由后续 TrustedTimeStatePort 实施。数据库负责可稳定验证的结构与转移约束；不设置 INSERT 只能空态的触发器，以允许含历史前移状态的普通备份恢复，初始写入和完整性认证必须由受控服务保证。|
|Impact|新增两张 License 表和 Alembic `20260924_0010`；无公开 API、新依赖、客户数据外发或真实 License 判定。数据库表中的完整性元数据仅为存储位，不能单凭行内容放行业务。|
|Rollback|空表可降级至 `0009`；存在状态/事件历史时普通 downgrade 拒绝，须先备份并按受控恢复方案处理。|

## DEC-20260924-087

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-087|
|Date|2026-09-24|
|WBS|LIC-03-A02 TrustedTimeStatePort 单调更新与完整性边界|
|Decision|在冻结模型留出的 `integrity_metadata` 实现空间内，选用无新增依赖的 HMAC-SHA256-V1 对部署状态 ID、最新成功 UTC 时间、版本及最新事件 ID 做确定性绑定；元数据只保存算法、受信任密钥引用和 tag，密钥由独立注入解析器提供，不在数据库、Git、日志或客户端输入中取得。内部端口要求 expected_version，使用 PostgreSQL 行锁和条件 UPDATE，明显回拨（相对上次成功时间超过内部允许容差）、旧版本或完整性错误失败关闭。容差由可信内部调用方给定，受 0～5 分钟硬上限约束，容差内不回写较早时间。成功事件/Audit 与状态同事务，拒绝事件/Audit 在状态事务回滚后独立持久化。|
|Reason|DM-02 明确完整性算法由 TrustedTimeStatePort 细化、时间只能前移且回拨/损坏/冲突拒绝并审计。HMAC 是状态完整性机制，不改变 License 的 Ed25519 签发、MAC 规范化或私钥隔离；未接入生产密钥源时默认失败关闭。一次性初态由未来部署装配显式创建，日常端口不自动补建缺失状态，避免数据库被清空后静默重置。|
|Impact|新增内部端口、HMAC 适配和 PostgreSQL 仓储，无 Schema/Migration、第三方依赖、公开 API 或客户数据外发。仅使用合成测试密钥验证；生产 Secret Store 解析器与初始化尚未完成，不能据此判定 License 有效。高权限数据库初态重置及数据库与密钥/备份同时回滚不在此离线方案的可检测保证内，也不宣称硬件可信时间。|
|Rollback|端口尚未接入公开路由和 LicenseService，可移除内部实现而不改变既有 Schema 与历史；已写入的 HMAC-V1 状态不应无验证地改写，未来算法迁移须保留验证/受控转换策略。|

## DEC-20260924-088

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-088|
|Date|2026-09-24|
|WBS|CR-LIC-001 / LIC-02-A02 前置基线变更|
|Decision|用户明确同意“修改已锁定方案，采用方案B”。首版 License 维持 `plm.license.v1` 七字段签名 Payload，限定为本产品全功能整体授权；不提供多产品或细分功能权益。原 V2.1 与 Gate 2 冻结提交保留历史，正式差异由 `docs/changes/CR-LIC-001-single-product-full-bundle.md` 与 V2.1 License 补充承载。|
|Reason|七字段载荷没有产品/功能权益；原 ADR-006/DM-02 的细分验证无法在不更换签名 Payload 的情况下实现。用户选择保留载荷并收窄首版授权粒度。|
|Impact|修订 ADR-006、DM-02、执行指令与状态；不改 MAC→SHA-256→Ed25519、私钥隔离、有效期、可信时间、Schema 或 `/api/v1`。生产可信公钥须限定本产品；无法按功能差异化授权。|
|Rollback|不静默回退已批准业务规则。若未来需要多产品或功能分级，另提 L3、采用新版签名载荷并定义兼容/迁移。|

## DEC-20260924-089

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-089|
|Date|2026-09-24|
|WBS|LIC-02-A02 LicenseService 综合验证|
|Decision|本项只实现内部综合校验，不把 `SignatureVerifiedDocument` 或结果写成活动 License。受信任本产品专用公钥引用、实施人员选定 MAC 和当前 UTC 时间均由独立 Port 提供，客户端不能指定；严格接受 `plm.license.v1` 七字段，复用 LIC-01-A02 Ed25519 验签。先校验签名/Schema/机器/签发及有效期，再推进可信时间；产出 `VerifiedFullBundleLicense` 但不持久化验证状态。|
|Reason|CR-LIC-001 保留七字段并取消细分权益，必须避免在代码中伪造签名保护的产品/功能列表。分离内部判定与下一任务的状态/Audit 编排，避免未完成权限/导入事务前对外开放。|
|Impact|新增 License 内部服务、测试与临时 PostgreSQL 集成验证；无 Schema/Migration、新依赖、公开 API 或客户数据外发。生产公钥必须本产品专用，选定 MAC 和可信时间密钥/初始化尚待装配；本项测试密钥仅在进程内生成。|
|Rollback|未接入公开路由或安装状态，移除内部服务可回退；不改 v1 签名载荷、既有表或历史记录。|

## DEC-20260924-090

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-090|
|Date|2026-09-24|
|WBS|LIC-02-A03 验证结果持久化与审计编排|
|Decision|只对已有 IMPORTED 安装从不可变文档取证并调用内部 LicenseService；完整验证成功记录 VALID 事件，但不更新部署级 ValidationState、不激活安装。事件、安装结果引用和 Audit 由同一数据库事务提交，拒绝事件不包含权益。|
|Reason|验证成功是安装候选的真实性与当前机器/时间判定，不等于管理员授权激活；部署级运行许可必须待受控激活和状态投影实现后才可能为 VALID。先保持失败关闭，避免单个事件绕过权限边界。|
|Impact|无 Schema/API/依赖变更；可信时间前移由既有独立事务完成，若随后结果记录失败，安装仍为 IMPORTED 且没有新结果引用，不能激活，重试需新的可信时间版本。|
|Rollback|没有公开入口或状态激活；回退代码不删除已写入的不可变验证/Audit 历史。|

## DEC-20260924-091

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-091|
|Date|2026-09-24|
|WBS|LIC-01-A03 受控导入命令与初始安装记录|
|Decision|内部导入命令由 Auth 所有的适配器在同一事务验证 Session Token、CSRF、当前凭据版本、未撤销/未超时状态和 DeploymentAdmin；公钥引用只取本产品可信 Port。Ed25519 预检成功后存 IMPORTED 安装和不可变文档；预检拒绝写无安装关联的脱敏验证事件及 Audit，绝不存失败文档正文。|
|Reason|冻结 API 的 LICENSE_IMPORT 恢复面不能绕过 Session/CSRF/Role/Audit；在 HTTP 装配和完整 License 判定尚未完成时，先把候选导入与激活分离。Auth 模块拥有身份表的查询，License 不直连 Auth 表。|
|Impact|无 Schema、Migration、新依赖或公开 API；成功导入的 `validation_result_ref` 仍为空且状态仅 IMPORTED，后续综合验证和激活必须另行执行。过大或未授权请求不落库；验签失败留摘要、分类和追踪，不留 Payload。|
|Rollback|内部命令尚无公开路由；移除代码不删除已形成的不可变安装、验证和 Audit 历史。|

## DEC-20260924-092

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-092|
|Date|2026-09-24|
|WBS|LIC-01-A04 受控激活与部署验证状态投影|
|Decision|激活命令内部先复核管理员 Session/CSRF，再调用 LIC-02-A03 对目标 IMPORTED 安装执行本次完整验证；仅 VALID 可继续。激活事务再次核对权限和事件的安装/文档摘要/同追踪号、完整本产品权益、有效期及 60 秒新鲜度；旧 ACTIVE→SUPERSEDED、新安装→ACTIVE、部署单例状态→VALID、Audit 同事务。|
|Reason|冻结 DM-02/ADR-006 要求成功验证才可激活、至多一条 ACTIVE、旧记录保留历史；旧 VALID 事件不能成为可重复使用的客户端激活凭据。双次权限检查覆盖验证跨事务窗口；60 秒界限缩短状态漂移窗口。|
|Impact|无 Schema/API/依赖变更。验证记录先于激活提交，若激活权限/并发/Audit 失败，成功验证事件仍作为历史存在但安装保持 IMPORTED；不得据此开放业务。首次投影版本为 0，后续每次更新 +1。|
|Rollback|无公开路由；代码可回退但不可删除已形成的安装、验证与 Audit 历史，已有 ACTIVE 需受控迁移或后续激活替换。|

## DEC-20260924-093

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-093|
|Date|2026-09-24|
|WBS|LIC-02-A04 运行时许可检查与失败关闭|
|Decision|内部 Guard 对受许可操作每次读取并锁定部署级状态，核对 ACTIVE 安装、不可变文档摘要、当前验证事件与状态一致；再读取经完整性校验的可信时间版本并调用现有 LicenseService 全量验签/机器/时窗/单调时间检查。成功或拒绝均追加验证事件、更新单例状态并与 Audit 同事务。状态行锁贯穿检查，串行化并发运行时验证；任何 DB/审计/可信输入失败都拒绝，不信任旧 VALID 缓存。|
|Reason|冻结 ADR-006/DM-02 要求任一验证失败即停止受许可业务。单独读取可信时间版本后释放状态锁会使并发成功检查互相冲突，甚至把合法状态投影为无效；贯穿行锁避免该竞态。|
|Impact|无 Schema/API/依赖变更；每次 Guard 检查写新事件与 Audit，运行性能尚未验收。可信时间推进与状态事件仍是先后两笔事务，后者失败时 Guard 拒绝且不能把旧状态当放行依据。状态拒绝后只允许未来受控恢复命令重验证，不由普通 Guard 自动复活。|
|Rollback|内部入口尚未挂路由；可撤销代码但不可删历史事件和 Audit。|

## DEC-20260924-094

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-094|
|Date|2026-09-24|
|WBS|LIC-02-A05 受控重验证与状态恢复|
|Decision|内部恢复命令仅接受当前 DeploymentAdmin Session+CSRF；在锁定部署状态与 ACTIVE 安装的同一事务中读取不可变签名文档和最新事件，再以可信时间版本调用原 LicenseService 全量验证。成功才追加 VALID 事件并恢复状态，失败追加分类拒绝事件；安装结果引用、状态投影和 Audit 同事务。|
|Reason|运行时 Guard 失败关闭后不得自行复活；已冻结恢复面允许管理员触发重验证，但不能直接把数据库状态翻转为 VALID 或重置可信时间完整性。|
|Impact|无 Schema、Migration、依赖或公开 API 变更。可信时间前移与状态事务仍是两个事务；若后者失败，本次命令拒绝，不能据此放行业务。|
|Rollback|内部入口未挂 HTTP；代码可撤销，不删除已形成的不可变验证/Audit 历史。|

## DEC-20260924-095

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-095|
|Date|2026-09-24|
|WBS|执行纪律 / LIC-03-A03 前置决策|
|Decision|接受用户持续授权，按 `CR-EXEC-001` 将原 L3/Gate 的逐项许可改为偏差先记录、按证据执行与持续交付。LIC-03-A03 采用用户选择的方案 A，先做受控初态初始化，生产密钥来源与恢复留待 PLT-02/Release。|
|Reason|用户明确要求减少确认并持续交付；冻结架构仍将跨平台密钥保护与恢复安排在 Release 安全设计。|
|Impact|更新仓库执行约束、Skill、STATUS 与追溯文档；不自动通过 Gate，不上传 Secret/客户数据，不把测试密钥标作生产密钥。|
|Rollback|保留原 V1.0 和冻结提交，可恢复旧流程；已经形成的偏差与验证历史不删除。|

## DEC-20260924-096

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-096|
|Date|2026-09-24|
|WBS|LIC-03-A03 一次性受控可信时间初态初始化|
|Decision|使用已存在的 Auth DeploymentAdmin Session+CSRF 适配器授权内部初始化；只在可信时间状态与事件均为空时插入版本 0/空成功时间单例，并与 Audit 同事务。PostgreSQL 事务 advisory lock 串行化同时初始化请求，事件表 SHARE 锁防止检查到插入之间出现事件历史；已有状态/历史绝不重置。|
|Reason|用户选择方案 A，只允许创建首次空状态，不提前决定生产密钥来源。冻结 DEC-20260924-087 禁止日常可信时间端口在缺失时自动补建。|
|Impact|无 Schema/Migration、公开 API、新依赖或生产 Secret；生产密钥保护和恢复留待 PLT-02/Release，测试不可当作生产 License 验收。|
|Rollback|未挂外部路由；代码可撤销，但已经创建的单例及 Audit 不删除，恢复依正式备份流程。|

## DEC-20260924-097

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-097|
|Date|2026-09-24|
|WBS|PLT-02-A01 SecretRecord / SecretVersion ORM/Migration|
|Decision|按冻结 DM-02/SC-01～03 建立部署级 SecretRecord 与密文版本；版本的密文、元数据、Key Provider 引用及创建事实不可改，activated_at/retired_at 仅可沿 CREATED→ACTIVE→RETIRED 单向变化。当前版本用同父复合 FK；partial unique 保证同一记录至多一个活动版本，记录状态用 lock_version 约束。|
|Reason|保留密文与主材料分离及历史追溯，防止跨 Secret 引用和静默覆盖；冻结模型虽称 SecretVersion 不可变，但版本激活/退役需要受控生命周期字段变更，内容本身始终不可变。|
|Impact|新增两表和迁移 `20260924_0011`；无公开 API、新依赖或生产密钥来源。非空历史拒绝普通降级，升级前需备份。|
|Rollback|空表可降级到 `20260924_0010`；有历史时须走受控备份恢复，不能删除密文历史。|

## DEC-20260924-098

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-098|
|Date|2026-09-24|
|WBS|PLT-02-A02 活动密文信封只读适配|
|Decision|将原候选“元数据读取与信封适配”拆为单一内部读路径：SQLAlchemy 仅从 ACTIVE SecretRecord 的 current_version_ref 读取同父、已激活且未退役的密文版本，转换为现有 SecretEnvelope；管理元数据查询另列 A03。|
|Reason|内部消费与管理员查询具有不同权限/数据最小化边界；先验收受控消费适配，避免通用密文查询扩散。|
|Impact|无 Schema/Migration、公开 API 或解密器实现；生产加密主材料和正式写命令仍未具备。|
|Rollback|可移除内部只读适配，不修改已存 Secret 历史。|

## DEC-20260925-001

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-001|
|Date|2026-09-25|
|WBS|PLT-02-A03 Secret 管理元数据只读查询与权限边界|
|Decision|内部详情与分页服务先用 Auth-owned 无 CSRF DeploymentAdmin 只读 Session 证明，再执行 License Guard，最终同事务复核管理员身份并读取只含安全列的投影；普通查询不读取 encrypted_payload、encryption_metadata 或 key_provider_ref。|
|Reason|冻结 GET 合同仅要求 Session+License，不能套用写操作的 CSRF；Guard 检查跨事务，第二次身份复核缩小权限撤销窗口；只投影安全字段降低误回显风险。|
|Impact|新增 Auth 内部只读权限适配及 Platform 服务/仓储；无 Schema、Migration、公开 API 或新依赖。Guard 尚未挂 HTTP，测试使用合成许可替身。|
|Rollback|内部服务未公开；撤销代码不影响 Secret 历史或冻结 API Contract。|

## DEC-20260925-002

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-002|
|Date|2026-09-25|
|WBS|PLT-02-A04 Secret 加密算法与密文写入边界|
|Decision|按 CR-PLT-002 采用版本化 AES-256-GCM；随机 96-bit nonce，AAD 绑定 SecretRef/用途/消费者/版本号/Key 引用，严格拒绝非 V1 元数据；加密输入与解密失败缓冲区尽量清零，主密钥仍只由外部 Key Provider Port 解析。|
|Reason|冻结模型规定只存密文、算法元数据和 Key 引用，但未定密文算法。Authenticated Encryption 可在不改 Schema/API 下提供完整性和上下文绑定。|
|Impact|新增内部加解密适配、合成测试和 PostgreSQL 临时库验证；无 Migration、新依赖、公开 API 或生产 Key Provider。生产安全验收仍未满足。|
|Rollback|尚无正式 Secret 写命令；已有历史密文不可静默转换或删除，后续算法升级须版本读取或受控重加密。|

## DEC-20260925-003

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-003|
|Date|2026-09-25|
|WBS|PLT-02-A05 Secret 管理写入与轮换命令|
|Decision|内部写服务在 License Guard 前先检查管理员 Session+CSRF，写事务再次检查；创建生成 SecretRef，轮换以活动记录行锁及 expected_version_no 保护，旧版先退役再激活新版并更新 Record，Audit 同事务。Cipher 草稿放入 Platform 应用层契约以保持依赖方向。|
|Reason|防止无权操作触发 License 信息侧信道，避免失效 Session/CSRF、并发轮换和审计失败留下部分密文。冻结 API-02 的 write-only 值与当前期望版本在内部命令层先形成可验证边界。|
|Impact|无 Schema/Migration、新依赖或公开 API；License Guard 与写事务分离导致检查后变化窗口，正式集成前须复核。生产 Key Provider 未实现，合成验证不能视为真实 Secret 可用。|
|Rollback|内部服务未公开；已存密文历史不可删除或覆盖，应使用新受控版本/状态命令恢复，不能普通降级。|

## DEC-20260925-004

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-004|
|Date|2026-09-25|
|WBS|PLT-02-A06 Secret 停用命令|
|Decision|把上一检查点暂列的“停用命令与管理 API 接线”拆为 A06 内部停用命令和 A07 公开 API/生产装配前置审查；停用将活动版本退役、Record 置 DISABLED 且 current_version_ref 清空，要求期望 lock_version 与同事务 Audit。|
|Reason|当前 FastAPI 仅开放健康检查；生产 Auth/License/Key Provider 装配、If-Match 与幂等基础尚未齐备，直接挂路由不能满足冻结 API-01/API-02 的安全协议。先验收不可逆读取拒绝的状态命令，公开接线另行验证。|
|Impact|仅时序/任务粒度调整，不改变冻结 API Contract、Schema 或数据模型；无 Migration/新依赖。公开 Secret API 仍未可用，完整程序包仍未交付。|
|Rollback|内部服务未公开；已退役密文历史不删除、不直接复活，恢复必须另走受控新版本命令。|

## DEC-20260925-005

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-005|
|Date|2026-09-25|
|WBS|PLT-02-A07 Secret 管理 API 前置检查|
|Decision|A07 公开路由暂不接线，保留 BLOCKED_BY_PREREQUISITES；先实施 AUT-03 登录/Session HTTP 安全、生产 License/Key Provider 装配和幂等/版本协议，再恢复 A07。CR-PLT-003 记录将 Key Provider 安全设计前移的时序差异。|
|Reason|TestClient 实测登录及 Secret 路由均 404，仅健康路由 200；若以合成 Guard/Key Provider 挂路由会违反冻结 API-01/API-02 和生产 Secret 分离要求。|
|Impact|不变更冻结路径、Schema 或权限；A07 未完成，不得声称管理 API/真实 Secret 可用。项目继续不受阻塞的 Auth/平台基础任务。|
|Rollback|尚无公开 Secret 路由；若前置不能满足，保持默认 404 和失败关闭，不能以测试替身代替生产装配。|

## DEC-20260925-006

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-006|
|Date|2026-09-25|
|WBS|AUT-03-A01 登录可信 Host/Origin 边界|
|Decision|将 A07 前置的“登录 HTTP 安全边界”拆为可信 Host/Origin、限流、凭据编排和 Cookie/CSRF 独立可验收项；首项采用显式允许集合，非 loopback 仅 HTTPS，缺失/重复来源拒绝，转发头不参与信任判断。|
|Reason|当前无公开登录路由与可信部署源配置；一次性开放会混入未验证限流和凭据流程。严格来源策略先作为独立组件验证，不把 `X-Forwarded-Host` 当作可信目标。|
|Impact|无公开 API、Schema、Migration 或新依赖；登录仍 404。反向代理须保留可信 Host；配置、限流与 Cookie 另行验收。|
|Rollback|组件未挂路由；移除不会改变现有健康接口，不能以宽松默认源替代。|

## DEC-20260925-007

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-007|
|Date|2026-09-25|
|WBS|AUT-03-A02 登录限流策略与持久化边界|
|Decision|依 CR-AUT-001 在 PostgreSQL 建 Auth 私有窗口桶，以来源地址与规范化用户名两个独立 SHA-256 摘要键原子预约尝试；来源限 30 次/5 分钟、账户限 10 次/5 分钟，拒绝及数据库不可用时不进入密码验证。|
|Reason|单机部署可运行多个 API 进程，进程内限流可绕过；双维度限制来源爆破与分布式针对账户尝试，且不落原始地址/用户名。|
|Impact|新增 ORM/Migration，密文/API Contract/架构不变；摘要不等同匿名化，数据库仍需访问控制与短期保留。限值、代理来源与清理调度须在正式登录装配前验证。|
|Rollback|短期计数桶可在维护窗口清理，确认无登录流量后按 Alembic down 回退；不得删除 Audit/User/Session 历史。|

## DEC-20260925-008

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-008|
|Date|2026-09-25|
|WBS|AUT-03-A03 登录用户名/密码证明与 Session 签发编排|
|Decision|登录先预约限流，再规范化用户名并查活动身份；不存在或停用的用户执行受控 scrypt 假验证以缩小时间差，成功身份交既有 SessionService 再次锁用户/校验真实密码并原子签发 Session+Audit。所有凭据失败对外统一 `AUTH_INVALID_CREDENTIALS`，追加不含原始用户名/密码的拒绝审计；密码可变缓冲区始终清零。|
|Reason|复用已验证的 Session 与密码 Port，避免按用户名查询与签发之间的停用/换密竞争；不让错误类型直接暴露用户存在性。|
|Impact|仅新增 Auth 应用编排、只读身份仓储和假验证适配，无 Schema/Migration、公开 API 或新依赖；HTTP Cookie/Origin/限流真实客户端地址仍待装配。|
|Rollback|内部服务未挂路由；撤销不改变已签发 Session 历史，已有 Session 只能按正式撤销命令处理。|

## DEC-20260925-009

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-009|
|Date|2026-09-25|
|WBS|AUT-03-A04 登录 HTTP Cookie/CSRF 接线|
|Decision|增加显式注入的登录 Router，默认应用不挂载；HTTP 入口先校验已配置的精确 Host/Origin，再限制 JSON 正文为 4096 字节且只收 username/password。Session Token 仅放 HttpOnly/SameSite=Lax Cookie，HTTPS Origin 自动设置 Secure，受信任 loopback HTTP 用于本机验证；CSRF 原值仅在本次成功响应 DTO 给前端内存，错误统一安全 Envelope。|
|Reason|在生产依赖装配前验证 HTTP 边界，防止默认开放未配置的登录；保持冻结 API-01/02 的传输与失败语义。|
|Impact|新增登录 HTTP Router、可选应用装配和已冻结 AUTH_INVALID_CREDENTIALS 错误码映射；无 Schema/Migration、新依赖或默认公开登录。Session 查询/续期/注销和初始管理员仍由后续 WBS 完成。|
|Rollback|移除可选 Router 注入即可恢复默认 404；已签发 Session 不能仅靠下线 Router 撤销。|

## DEC-20260925-010

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-010|
|Date|2026-09-25|
|WBS|AUT-03-A05 登录 SessionView 真实身份投影|
|Decision|把冻结 SessionView 的 user/deployment_role/authorized_projects 设为登录 Router 必填的只读投影 Port。Auth 适配器只从当前 ENABLED User 读身份和部署角色；项目摘要必须由 Project-owned Port 显式提供，尚无 ProjectMember 层时不设置生产默认空列表。投影失败时不发 Cookie、返回固定服务不可用错误。生产装配与初始管理员顺延为 A06。|
|Reason|上一项 HTTP 边界的最小 DTO 缺少冻结字段；Auth 不应自行伪造项目成员事实或长期把缺失数据写为空项目权限。|
|Impact|登录 Router 签名要求真实投影，旧的可选接线测试需增加投影替身；无 Schema/Breaking API，新响应补齐冻结结构，仍不默认开放。已签发但投影失败的 Session 在服务器端保留至超时，后续评估补偿撤销。|
|Rollback|回退该非公开 Router 装配；不改变已冻结 API 或 User/Session 数据。|

## DEC-20260925-011

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-011|
|Date|2026-09-25|
|WBS|AUT-03-A06 初始 DeploymentAdmin 离线受控创建|
|Decision|仅在本机离线命令入口创建首个 DeploymentAdmin。应用服务使用专用 PostgreSQL 事务级 advisory lock 串行化，确认整个 User 表为空后在同一事务写 User、scrypt 凭据和不含密码的 Audit；任何已有 User 即拒绝，不能用于管理员恢复或新增普通用户。初始密码至少 15 个 Unicode 字符、最多 1024 UTF-8 字节。CLI 通过终端无回显读取数据库 URL 和双次密码，不能从参数或环境变量接收初始密码；无回显不可用时失败关闭。|
|Reason|初次部署时不存在可验证的管理员 Session，既有 UserCommandService 正确地要求已登录授权。离线单次初始化可解除循环依赖，但必须独立于公开 API 并禁止重新引导提权。|
|Impact|新增 Auth bootstrap 内部服务、SQL 适配和受控 CLI；无 Schema/Migration、公开路由或新依赖。初始化凭据仍需部署者现场设置，不能由 AI 代用户填写真实密码。生产登录 Router 与 Project 授权读取仍待后续任务。|
|Rollback|在尚未执行初始化的部署可移除 CLI；已创建的管理员属于正式 User/Audit 历史，不得简单删除，应走未来受控管理员迁移/停用流程。|

## DEC-20260925-012

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-012|
|Date|2026-09-25|
|WBS|AUT-03-A07 登录生产依赖装配前置|
|Decision|按 CR-AUT-002 保留默认登录关闭，A07 暂不记 PASS；先建设 Phase 2 范围内的 Project/ProjectMember 持久层及授权摘要读取，再在安全运行配置完成后恢复生产装配，随后继续 Session HTTP。|
|Reason|现有项目授权摘要和运行信任源缺口无法由空列表或测试配置安全替代。|
|Impact|仅实施顺序调整，无冻结 API/Schema 变化；Gate 3/UAT 不受自动放行。|
|Rollback|前置补齐后可直接恢复 A07，保留本次核查记录。|

## DEC-20260925-013

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-013|
|Date|2026-09-25|
|WBS|PRJ-01-A01 Project/Department/ProjectMember ORM 与 Migration|
|Decision|按冻结 PRJ-01～03 建立三张 `plm.prj_*` 表：Project 代码部署内唯一；Department 代码在同项目 ACTIVE 状态唯一；ProjectMember 对未 REMOVED 用户建立全部署与同项目 partial unique；ProjectMember.department_id 与 project_id 通过复合 FK 锁定同项目。三者保留状态、时间、乐观锁版本和不可删除 FK；本任务不开放读写 API 或自动生成项目事实。|
|Reason|真实项目授权摘要需要可验证成员事实；数据库必须阻止跨项目部门绑定及多项目有效成员，不能依赖登录响应空列表替代。|
|Impact|新增普通增量 Migration 和 ORM，无现有表变更、公开 API 或新依赖。Project 状态/角色变更的应用命令与授权读取后续单项完成；已有库升级保留所有数据。|
|Rollback|仅确认三张表无数据且无下游 FK 后允许 Alembic downgrade；有数据时拒绝自动删除。|

## DEC-20260925-014

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-014|
|Date|2026-09-25|
|WBS|PRJ-01-A02 项目成员授权摘要读取|
|Decision|Project 模块公开只读 `ProjectAccessSummary` DTO，并在当前事务中按 UserId 查询 ACTIVE、已生效、未结束的 ProjectMember；只返回 ACTIVE Project 与 ACTIVE Department 的项目 ID/名称/角色，不缓存也不以 DeploymentAdmin 身份推定项目成员。Auth SessionView 复用该公开 DTO，并从显式 Project Port 取得摘要。|
|Reason|冻结模型将 ProjectMember 作为项目权限唯一事实，Session 不持久化权限快照；部署管理员不自动拥有项目数据访问权。|
|Impact|无 Schema/Migration、公开 API 或新依赖；补齐登录响应所需的真实 Project 摘要读层，但完整 ProjectAuthorizationService 的逐操作判定仍待后续 WBS。|
|Rollback|移除只读适配器并恢复 Auth Port 未装配状态；不改变项目成员或 Session 历史。|

## DEC-20260925-015

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-015|
|Date|2026-09-25|
|WBS|PRJ-01-A03 ProjectAuthorizationService 逐操作授权|
|Decision|Project 模块对冻结 API-02 的项目路径操作维护显式角色白名单；未登记操作默认拒绝。每次在新事务中从 Project、ACTIVE Member、ACTIVE Department 重读状态，目标 Member/Department 由数据库反查 owner ProjectId 并与路径交叉校验；DeploymentAdmin 不自动成为项目成员。归档项目只允许授权读取，不允许写。普通无权/不存在/跨项目统一 `RESOURCE_NOT_FOUND`；有权成员对归档项目写入返回 `PROJECT_ARCHIVED`。|
|Reason|登录摘要不能当权限快照；冻结模型要求按资源实际归属和当前成员事实重新校验。`PROJECT_LIST` 的授权列表与部署级 `PROJECT_CREATE` 的管理员命令另在对应读/写任务接线，不能用项目成员角色替代。|
|Impact|新增 Project 内部授权 Service/SQL Repository，无 Schema/Migration、公开 API 或新依赖。调用者仍必须先经 Auth Session、License、CSRF 等契约前置；本服务只实现 Project 角色/Scope 判定，不宣称全链路开放。|
|Rollback|内部 Port 尚未挂公开路由；撤销本实现不改变业务数据。|

## DEC-20260925-016

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-016|
|Date|2026-09-25|
|WBS|PRJ-01-A04 Project 创建命令|
|Decision|Project code 与可选 department seed code 做 Unicode NFKC、去首尾空白与 casefold 归一化，再由数据库唯一约束兜底；未提供部门 seed 时原子建立 `DEFAULT`/`默认部门`，保证首位 ProjectManager 的必需 Department FK。创建命令先验证当前管理员 Session/CSRF，再执行 License Guard，再在同一写事务重新验权并由 Auth-owned Port 锁定 ENABLED 初始负责人；Project、Department、Member 和 Audit 原子提交。|
|Reason|冻结 API 允许 department seed 缺省，但冻结 DM-02 要求每个 Member 有同项目 Department；创建者不自动成为项目成员。归一化统一代码大小写与兼容字符，锁定负责人防并发重复绑定，数据库约束最终兜底。|
|Impact|内部服务、Auth 只读资格 Port 与 Project 写适配器；无 Schema/Migration、公开 API 或新依赖。生产 License/HTTP 装配仍待后续。|
|Rollback|内部命令尚未公开；撤销代码不自动删除已创建项目或审计历史。|

## DEC-20260925-017

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-017|
|Date|2026-09-25|
|WBS|PRJ-01-A05 Project 列表与详情读取|
|Decision|Project 只读 Application Port 先执行 License Guard，再由 Auth-owned Port 在查询事务验证当前 Session、User 状态与凭据版本；Project-owned SQL 在同一事务重读 ACTIVE 且已生效 Member、ACTIVE Department 与 Project 当前状态，不使用登录时摘要。`PROJECT_LIST` 仅返回当前有权项目；`PROJECT_GET` 对不存在、无成员或跨项目统一隐藏。ARCHIVED 允许受权读取。冻结单有效项目成员不变量使当前列表最多 1 项，DTO 仍保留 Page 形状，`next_cursor` 为 null。|
|Reason|避免 Session 摘要陈旧与 DeploymentAdmin 隐式越权；列表和详情共用当前成员事实。模型强制单一未移除成员，当前不产生多页，因此无须提前引入未验证的公开游标格式。强 ETag 仅从 Project.lock_version 生成。|
|Impact|新增 Auth 只读 Session 身份适配器、Project 查询 Service/Repository；无 Schema/Migration、公开 API 或新依赖。公开 GET 仍须由后续 HTTP 装配并应用 API-01 Envelope/trace。|
|Rollback|撤销未公开的查询 Port；不改变项目数据。|

## DEC-20260925-018

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-018|
|Date|2026-09-25|
|WBS|PRJ-01-A06 Project 元数据修改与归档内部命令|
|Decision|`PROJECT_PATCH` 首版只允许修改 Project 显示名称，不允许经通用 PATCH 修改 ProjectCode；编码不可静默复用，未来如需改码须专用受控命令和旧码保留机制。`PROJECT_PATCH`/`PROJECT_ARCHIVE` 均要求当前 ProjectManager、ACTIVE Project、Session/CSRF、License、expected lock_version 与同事务 Audit；归档不提供普通反向操作。Project 授权 Port 增加写事务内核验，写操作锁定项目/成员/部门事实并在同事务更新。|
|Reason|冻结 API-02 仅写“metadata”，未规定可修改 code；DM-02 明确 ProjectCode 不可静默复用，而当前冻结 Schema 不保存旧 code，直接改码会释放旧码导致复用。名称是可安全修改的显示元数据；乐观并发和事实锁避免撤权/归档竞态。|
|Impact|新增内部 Project 写命令/SQL Repository，授权 Port 增加同事务入口；无 Schema/Migration、新依赖或公开 API。若未来需要 code 修改，先按正式变更流程设计历史保留与升级。|
|Rollback|内部命令未挂公开路由；已有名称/归档变更保留在 Audit，归档不可自动回滚为 ACTIVE。|

## DEC-20260925-019

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-019|
|Date|2026-09-25|
|WBS|PRJ-02-A01 ProjectMember 授权列表读取|
|Decision|`PROJECT_MEMBER_LIST` 在 License Guard 与 Auth 当前 Session 验证后，于同一数据库事务调用 ProjectAuthorizationService 的 `PROJECT_MEMBER_LIST` 策略；仅 ProjectManager/CustomerManager 可读取该路径 Project 的成员历史。Project Repository 只读 ProjectMember/Department，Auth-owned Port 批量提供 user_id/display name，Project 不直接查询 Auth 表。内部分页以 `(project_member_id ASC)` 做稳定 keyset，原始 after_id 不对 HTTP 客户端暴露；后续公开路由必须按 API-01 封装完整性保护的不透明 cursor。|
|Reason|成员列表需保留 ACTIVE/SUSPENDED/REMOVED 历史，同时防止其他项目成员和 Auth 凭据数据泄漏。用户显示名由 Auth Owner 提供，避免跨模块内部表访问。内部 keyset 位置不是可直接暴露的 API cursor。|
|Impact|新增 Project 内部列表 Service/Repository 与 Auth 最小用户摘要适配器；无 Schema/Migration、新依赖或公开 API。归档 Project 仍允许授权只读。|
|Rollback|撤销未公开查询 Port；不改变成员历史。|

## DEC-20260925-020

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-020|
|Date|2026-09-25|
|WBS|PRJ-02-A02 ProjectMember 创建命令|
|Decision|创建成员由当前 ProjectManager 在 License Guard、Session/CSRF 后于同一事务执行：锁定当前项目权限事实，Auth-owned Port 锁定 ENABLED 目标 User 并返回最小显示名，Project-owned Repository 锁定同项目 ACTIVE Department、检查目标 User 未有任何非 REMOVED membership，插入单一角色/部门成员并同事务 Audit。数据库 partial unique 与复合 FK 作为并发/跨项目最终防线；目标 User 缺失/停用或部门不合规则固定拒绝，已分配返回 `PROJECT_USER_ALREADY_ASSIGNED` 且不披露另一项目。允许可选未来 effective_at，未提供由数据库取当前时间。|
|Reason|冻结模型要求一个 User 同时最多一个未移除成员，部门必须同项目；跨模块 User 状态只能通过 Auth Port，不能由 Project 直查 Auth 内部表。锁 User 与 Department，再结合数据库约束可防并发重复和归属漂移。|
|Impact|新增 Project 内部创建 Service/Repository、Auth-owned 目标资格适配器；无 Schema/Migration、新依赖或公开 API。公开 POST 的 Idempotency-Key 仍待正式 API 安全装配。|
|Rollback|内部命令尚未公开；已创建成员如需撤销，应走后续 REMOVE 命令保留历史，不物理删除。|

## DEC-20260925-021

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-021|
|Date|2026-09-25|
|WBS|PRJ-02-A03 ProjectMember 角色/部门修改命令|
|Decision|依据 CR-PRJ-001，在冻结的当前成员表之外增加 Project-owned 角色/部门变更历史子表，不改当前权限读取路径；每次实际变更在同一事务更新成员版本、插入前后值历史并写 AuditEvent。无变化返回原 ETag，不制造事件。最后一名当前有效 ProjectManager 不允许降级，以避免项目无法再管理。|
|Reason|冻结 DM-02 要求角色变更历史，而原 Schema 与通用 AuditEvent 无法完整追溯角色和部门的旧、新值。项目行锁使当前授权与负责人数量检查串行，成员版本锁与数据库约束防覆盖。|
|Impact|新增 Migration `20260925_0014`、Project 内部修改命令及 Auth 最小显示名 Port；无公开 API Breaking Change。必须升级数据库后部署本版。|
|Rollback|历史表为空时可降级到 `20260925_0013`；已有历史需保留，不允许自动丢弃。内部命令未公开，可停用但不可篡改已写历史。|

## DEC-20260925-022

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-022|
|Date|2026-09-25|
|WBS|PRJ-02-A04 ProjectMember 暂停/恢复/移除命令|
|Decision|三项内部命令复用同一状态 Service/Repository，但调用不同的冻结操作策略；仅允许 ACTIVE→SUSPENDED、SUSPENDED→ACTIVE、ACTIVE/SUSPENDED→REMOVED。每次变更需当前 ProjectManager、Session/CSRF、License、目标归属、expected_version 与同事务 Audit。恢复要求关联部门 ACTIVE。暂停/移除最后一个当前有效 ProjectManager 拒绝。未来生效成员提前移除时 `ended_at = greatest(statement_timestamp(), effective_at)`，状态立即 REMOVED。|
|Reason|统一状态矩阵避免各命令实现分歧；最后负责人保护防管理权限被清空，数据库时间约束要求提前移除的 ended_at 不早于 effective_at。|
|Impact|新增 Project 内部状态 Service/Repository，无 Schema/Migration、新依赖或公开 API；正式 POST 幂等和 If-Match 留给公开 API 安全接线。|
|Rollback|内部命令未公开；已移除成员不可原地恢复，只能按后续受权创建命令重新分配并保留原历史。|

## DEC-20260925-023

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-023|
|Date|2026-09-25|
|WBS|PRJ-03-A01 Department 授权列表读取|
|Decision|`PROJECT_DEPARTMENT_LIST` 在合成 License Guard 与 Auth 当前 Session 证明后，于同一事务检查 ProjectAuthorizationService 的当前成员事实。Project Repository 只查目标 Project 的 ACTIVE/INACTIVE Department，不访问 Auth 表；内部按 department_id ASC 稳定 keyset，返回最多 200 项及内部 after_department_id。归档项目受权只读保留。|
|Reason|冻结 API-02 授权所有当前 ProjectMember 读取所属项目部门；历史部门须保留，权限不得依赖缓存或客户端 project_id 声称。稳定内部 keyset 避免更新造成分页位置漂移；公开 API-01 cursor 后续必须签名或完整性保护，不暴露原始 ID。|
|Impact|新增 Project 内部只读 Service/Repository；无 Schema/Migration、新依赖或公开 API。|
|Rollback|内部查询尚未公开，可移除该 Port；不影响部门数据与历史。|

## DEC-20260925-024

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-024|
|Date|2026-09-25|
|WBS|PRJ-03-A02 Department 创建命令|
|Decision|Department 创建沿用 Project bootstrap 的 NFKC/trim 显示值与 casefold 规范化语义，在当前 ProjectManager、Session/CSRF、License 与项目 ACTIVE 检查后，以 PostgreSQL `uq_prj_departments__project_code_live` 部分唯一索引作为并发最终防线。冻结 DM 的“DepartmentCode 项目内唯一”按更具体的冻结 SC-02/03 部分唯一索引解释为同项目 ACTIVE Department 唯一；INACTIVE 历史保留且其代码可被新 ACTIVE Department 复用。创建与 Audit 同事务，冲突固定 `CONFLICT_DUPLICATE`。|
|Reason|冻结 SC-03 明确为 partial unique，已有 ORM/Migration 仅对 ACTIVE 行唯一；保持现有 DB 基线与可追溯历史，不额外改变冻结 Schema。|
|Impact|新增 Project 内部创建 Service/Repository；无 Schema/Migration、新依赖或公开 API。对停用部门编码复用的 UI 展示需要在未来公开设计中结合 ID/状态区分，不能只凭 code 认定历史身份。|
|Rollback|内部命令尚未公开，可停止新建；已有 Department 不物理删除，若需撤销须走后续受控停用并保留历史。|

## DEC-20260925-025

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-025|
|Date|2026-09-25|
|WBS|PRJ-03-A03 Department 名称/编码修改命令|
|Decision|仅 ACTIVE Department 可由当前 ProjectManager 在同事务 Session/CSRF、License、目标归属及 expected_version 检查后修改名称和/或编码。编码沿用 NFKC/trim/casefold；同项目 ACTIVE 部门不得重复，项目行锁串行化受权写入且 DB partial unique 兜底。真实变更版本+1并写 Audit，无变化返回原 ETag 不制造事件；INACTIVE 历史不允许普通 PATCH。|
|Reason|维持冻结 API-01 强 ETag、API-02 逐操作权限与 SC-03 活动编码唯一；禁止修改停用历史，避免旧引用被悄然改写。|
|Impact|新增 Project 内部 PATCH Service/Repository；无 Schema/Migration、新依赖或公开 API。当前 AuditEvent 可追溯操作者/对象/时间，但不保存字段级旧/新 code/name，不能支持逐版字段恢复；如后续正式要求该能力须单独 Change Request。|
|Rollback|内部命令尚未公开，可停止使用；已修改元数据不能依赖 Audit 自动恢复旧值，需有正式备份或后续受权修订。|

## DEC-20260925-026

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-026|
|Date|2026-09-25|
|WBS|PRJ-03-A04 Department 停用命令|
|Decision|仅当前 ProjectManager 可对所属 ACTIVE 项目内的 ACTIVE Department 执行一次性停用；先核对 Session/CSRF、License、目标归属与 expected_version，再在项目行锁保护下检查目标部门没有 ACTIVE/SUSPENDED ProjectMember。仅 REMOVED 历史引用不阻止停用，不做成员静默迁移。成功时版本+1并与前后状态 Audit 同事务提交；重复停用拒绝。|
|Reason|冻结 DM-02 与 API-02 明确成员引用阻断和 `PROJECT_DEPARTMENT_IN_USE`；项目行锁与成员新建/修改命令共享写入序列，数据库查询在同事务内复核，避免并发创建与停用形成矛盾状态。|
|Impact|新增 Project 内部停用 Service/Repository；无 Schema/Migration、新依赖或公开 API。仅通过正式服务写入可受项目锁保护；部署数据库角色权限仍须保证应用外写入受控。|
|Rollback|内部命令未公开；已停用部门按冻结状态模型无普通恢复命令，若业务需要重用编码可新建部门，旧 DepartmentId 和历史引用保持不变。|

## DEC-20260925-027

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-027|
|Date|2026-09-25|
|WBS|AUT-03-A07-P01 可信 Origin 部署配置|
|Decision|在现有非敏感 BootstrapSettings 中新增默认空的 `trusted_origins`，允许 YAML 显式数组和 `PLM_TRUSTED_ORIGINS` JSON 数组覆盖；配置层限制最多 16 项、非空和单项长度，但不在 Platform 层复制 Auth 的 URL/Host 规则。最终装配仍必须调用既有 `LoginOriginPolicy` 校验 URL、HTTPS/loopback、Host 匹配，任何失败不得挂载登录路由。|
|Reason|CR-AUT-002 要求可信 Origin 生产来源，而现有 Auth 策略已有精确语义；配置层只持有非敏感部署值，避免 Platform 反向依赖 Auth 或维护两套可能分叉的来源校验。|
|Impact|新增非敏感配置和测试；无 Schema/Migration、新依赖、公开 API 或权限变化。配置加载成功本身不代表生产登录可用，安全数据库凭据和端到端装配仍待完成。|
|Rollback|删除部署配置即可恢复默认空来源；当前默认应用不挂登录路由，无数据迁移。|

## DEC-20260925-028

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-028|
|Date|2026-09-25|
|WBS|AUT-03-A07-P02 Windows 数据库凭据来源|
|Decision|依 CR-AUT-003 使用当前 Windows 运行账户的 Credential Manager Generic Credential，固定生产 Target `PLMProjectTool/Database`；本机无参数、无回显交互写入/轮换，运行时只读。URL 必须为带 Host、用户名、密码的 `postgresql+psycopg`；读取/写入失败统一脱敏拒绝，不回退到环境变量/YAML/测试 URL。|
|Reason|安全数据库凭据是 AUT-03-A07 的真实前置；使用系统账户保护的持久存储，比把密码保存在普通配置中更符合已冻结 Secret 边界。固定 Target 防止运行时路径注入；测试只操作 UUID 合成 Target。|
|Impact|新增 Windows 专有基础设施和部署入口；无 Schema/Migration、新依赖或公开 API。目标服务账户需现场录入，跨账户/跨机器不自动迁移；Debian 仍需独立来源。Python/SQLAlchemy 内存副本不可保证绝对清零。|
|Rollback|停止调用该来源并关闭服务；生产 Vault 凭据不会自动删除，由部署管理员通过系统凭据管理手工移除或轮换。|

## DEC-20260925-029

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-029|
|Date|2026-09-25|
|WBS|AUT-03-A07-P03 Windows 生产登录组合根|
|Decision|单独提供显式 Windows 登录应用工厂，不更改普通 `create_app()` 的默认无登录行为。启动顺序为可信 Origin 策略 → 当前账户 Credential Manager 数据库 URL → PostgreSQL 连通性与 `plm.alembic_version` 等于包内迁移 head → 真实 Auth/Project/Audit 接线；任一步失败均不发布应用且释放连接。进程退出释放 Engine。本机 Uvicorn 明文入口只绑定回环 IP，禁用代理头信任；对外 HTTPS 由本机受控反向代理提供。|
|Reason|让 CR-AUT-002 的项目摘要与安全来源成为真实生产依赖，同时避免把测试注入应用冒充默认产品入口。仅 `SELECT 1` 不能证明 Schema 已升级；非回环明文监听会让密码暴露于网络。|
|Impact|新增组合根、Windows 启动入口及应用生命周期清理；无 Schema/Migration、新依赖或冻结 API 变化。Windows 11 合成 PostgreSQL/Windows Vault 链路已验证；Server 2025 服务账户、HTTPS 代理与 Debian 来源仍需单独验收，不能由本项推定通过。|
|Rollback|不调用 Windows 启动入口即可保留原默认健康-only 应用；无数据迁移，已签发的测试 Session 随一次性库删除。|

## DEC-20260925-030

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-030|
|Date|2026-09-25|
|WBS|AUT-03-A08 当前 Session 查询 HTTP|
|Decision|冻结 GET Session 仅验证唯一严格格式的 `plm_session` Cookie 和当前 Session，再读取最新 User/ProjectMember 摘要；响应只含身份、授权摘要与到期时间，不回显 Cookie/Token/CSRF，也不刷新期限。只读请求必须有单一可信 Host；若客户端提供 Origin 则仍按已冻结登录来源策略精确校验，不要求浏览器 GET 必须带 Origin。仅显式生产组合根挂载，普通应用继续 404。|
|Reason|API-02 对 GET 标记 `S` 而非 `C`，CSRF 原值仅在创建/轮换响应发放；强行要求所有 GET 带 Origin 会拒绝合法浏览器读取。Host 必须可信以避免不受信域名承载 Cookie 身份投影，实时摘要不能复用登录时的旧权限。|
|Impact|新增 Auth 只读 HTTP 入口、Host 策略及生产显式挂载；无 Schema/Migration、新依赖或冻结 API Breaking Change。Windows 11 真实 PostgreSQL 验证成员暂停后摘要即时刷新；业务请求仍须逐操作重新授权。|
|Rollback|停止显式挂载 Session Router 即恢复默认 404；GET 不修改 Session/项目数据，无迁移回滚。|

## DEC-20260925-031

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-031|
|Date|2026-09-25|
|WBS|AUT-03-A09 Session 续期 HTTP|
|Decision|冻结 `POST /api/v1/auth/session:renew` 使用唯一严格 Cookie、`X-CSRF-Token`、精确 Origin/Host 且不接受请求正文。先验证当前 Session/CSRF 并读取 User/Project 投影，确保投影失败不会先撤销旧凭据；之后调用已验收的同事务 Session 轮换/Audit，成功只通过 HttpOnly Cookie 和本次 DTO 返回新 Token/CSRF。绝对到期保持原时刻，旧凭据立即失效。|
|Reason|API-02 的续期控制为 S/C/A 而非 I；投影属于响应必需内容，若轮换后才发现投影故障会让浏览器收不到新凭据。预检与轮换间的并发由轮换服务再次校验 Session 关闭，不把预检当成最终授权。|
|Impact|新增 Auth 续期 HTTP 与显式生产挂载；无 Schema/Migration、新依赖或 Breaking Change。投影可能在相邻事务之间被项目成员变更，后续业务请求仍须实时重验授权；多标签旧凭据按冻结轮换语义失效。|
|Rollback|停止显式挂载续期 Router 即恢复默认 404；已成功轮换的 Session 不反向复活，用户可重新登录，无数据库迁移。|

## DEC-20260925-032

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-032|
|Date|2026-09-25|
|WBS|API-RUNTIME-01 通用持久幂等收据|
|Decision|按 CR-API-001 新增与配置专用收据并列的 `plt_idempotency_receipts`；范围为 actor/project/版本化 operation/Key SHA-256，部署级 NULL Project 通过 `UNIQUE NULLS NOT DISTINCT` 仍唯一。只存规范化请求 SHA-256 和非敏感结果引用/HTTP 状态，不存 Key/正文/Token/完整响应。reserve→业务/Audit→complete 必须在同一事务；已完成行触发器禁止修改/删除，PENDING 误提交后失败关闭；非空表禁止 downgrade，暂不自动过期清理。|
|Reason|冻结 API-01 要求跨进程/重启重放同一语义，现有 `plt_configuration_command_receipts` 受 CHECK/外键限制，不能混入 Auth/Project 命令。单独增量保留 Gate 2 历史与旧配置收据语义。|
|Impact|新增 ORM/Alembic `20260925_0015`、应用范围/指纹与 PostgreSQL 收据仓储；无公开 API/新依赖。调用方必须先完成授权并保证结果引用可重建原语义，ProjectId 归属由调用方验证。记录会持续增长，Retention 和误提交 PENDING 的受控恢复仍需单独设计。|
|Rollback|停止新命令挂载；新收据为空时可 downgrade 到 `0014`，非空时拒绝以保留去重历史。旧表和旧业务数据不变。|

## DEC-20260925-033

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-033|
|Date|2026-09-25|
|WBS|AUT-03-A10 Session 注销 HTTP|
|Decision|注销首次请求以有效 Session、匹配 CSRF、可信 Origin/Host 与合法幂等 Key 为前置，在同一 UoW 内预留 `V1_AUTH_LOGOUT` 收据、撤销 Session、追加 `SESSION_REVOKED` Audit 并完成指向该 Session 的 200 结果引用。已撤销 Session 仅在原 Token/CSRF、同 Key/同 Session 指纹、收据已完成、撤销原因确为 LOGOUT 时返回原 200 并再次清 Cookie；并发等待收据后重新读取 Session 状态。不同 Key 对旧 Session 返回 401，不同 Session 同 Key 返回 409。|
|Reason|冻结 API-02 的注销同时标记 S/C/I/A，但首次成功后 S 已失效；为了满足 API-01 同 Key 同结果重试，不可用普通 Session 再授权，也不可把所有旧 Cookie 当幂等成功。通过持久收据与已撤销原因双重绑定，重试只获取原注销语义，不恢复权限。|
|Impact|新增 Auth 注销 Application/HTTP 接线，复用 `0015` 收据；无新 Migration、新依赖或 Breaking Change。已完成收据与 Session 历史的 Retention 需协同设计，当前不得自动删除。默认应用仍不挂 Auth 路由。|
|Rollback|停止显式挂载注销 Router 即恢复默认 404；已撤销 Session 不反向复活，用户需重新登录；收据与 Audit 保留供追溯。|

## DEC-20260925-034

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-034|
|Date|2026-09-25|
|WBS|PLT-02-A07-P01 Windows Secret 主密钥只读来源|
|Decision|依 CR-PLT-003 的安全装配前置，Windows 侧使用当前运行账户 Windows Credential Manager Generic Credential 作为独立主密钥读取来源，严格映射受限 key_ref，要求正好 32 字节；读取器不创建、覆盖、导出或自动回退到配置/环境变量。此项只是 OS 来源适配，不宣称生产 Key Provider 和恢复已完成。|
|Reason|现有 AES-GCM Secret 密文引用 key_ref，需要密文库外的受保护来源；Windows Vault 可由当前运行身份访问且不需将原始主密钥放进仓库、YAML 或数据库。缺失、错账户或错长度必须失败关闭。|
|Impact|新增 Platform 基础设施适配器与 Windows 11 合成测试；无 Schema、Migration、公开 API、新依赖或冻结合同变化。服务账户供给、独立备份与异机恢复、Server 2025/Debian 13 均未验证。|
|Rollback|移除该只读适配器注入即可回到原先未装配状态；测试临时凭据已删除，无真实主密钥或业务密文迁移。|
