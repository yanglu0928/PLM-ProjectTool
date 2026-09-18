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
