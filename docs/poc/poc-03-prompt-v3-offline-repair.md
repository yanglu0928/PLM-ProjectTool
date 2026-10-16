# POC-03 Prompt v3 离线修复设计 R11

## 状态

`IMPLEMENTED_OFFLINE / NOT_LIVE_REVALIDATED / QUALITY_GATE_UNCHANGED`

用户同意 R10 修复方向，并明确本轮不重复执行真实质量复验。R11 只实现离线合同、失败关闭和合成样本测试，不调用百炼或 DeepSeek，不复用 50 条已见留出集调参，也不改变 98.00% / 48.00% / 74.00% 历史结果。

## 目标

1. 区分文档事实确认与能力适配判断，避免把“协议明确要求”直接解释为“标准能力满足”。
2. 能力适配必须同时装配需求/约定证据与标准能力证据。
3. 引用选择独立于检索首位，比较全部候选的直接支持度。
4. 保持 ProjectId 隔离、统一 AIService、现有技术栈和质量门槛不变。

## Prompt v3 合同

### 问题类型

- `DOCUMENT_ASSERTION`：只回答资料是否存在所问事实；输出 `PRESENT / ABSENT / AMBIGUOUS`，分类固定为 `NOT_APPLICABLE`，不进入五类能力质量指标。
- `CAPABILITY_FIT`：使用需求证据与标准能力证据进行适配判断；输出仍为标准满足、部分满足、非标、资料不足、无可靠匹配五类之一。

问题类型必须由开发集在推理前显式冻结，运行时不通过来源或关键词静默猜测。

### 结构化证据门

能力适配依次输出：

1. `evidence_match`：直接、部分或无匹配。
2. `evidence_sufficiency`：证据是否充分。
3. `requirement_coverage`：原子需求完整、部分或未覆盖。
4. `customization_basis`：明确二开、确认的标准能力缺口、无非标依据或不适用。
5. `classification`：最终五类结论。
6. `citation_chunk_ids`：主引用在前，最多再附一个必要对照引用。
7. `decision_basis`：简洁、可审核的证据结论，不输出思维过程。

JSON Schema 使用条件约束，阻止文档事实任务返回五类能力结论，也阻止能力适配任务返回 `NOT_APPLICABLE`。

## 双来源证据装配

- 需求证据只接受 `CONTRACT / SURVEY / TECHNICAL_AGREEMENT`。
- 标准能力证据只接受 `STANDARD_CAPABILITY`。
- 两组证据均必须为 `PROJECT` Scope 且 ProjectId 与请求完全一致。
- 未提供问题类型、需求证据或能力适配所需的标准能力证据时失败关闭。
- Prompt Payload 排除 `expected_classification`、人工期望 Chunk、答案术语、期望引用和评审信息。

## Evidence Selector

- 对 supplied candidates 逐项计算与查询的 CJK 感知术语覆盖。
- 原始检索顺序只作为最终同分规则，不作为主要支持度。
- 输出支持分、命中术语数和原始名次，便于审计。
- 不读取人工答案术语、期望 Chunk 或标签。
- 未知 Chunk、非 PROJECT Scope、跨 ProjectId 或空文本均失败关闭。

该本地 Selector 是防止“默认引用第 1 名”的可测试基线；正式质量仍需后续全新数据证明，当前不作 PASS 推断。

## 测试

- 合成样本证明第 2 名直接证据可以超过第 1 名泛化描述。
- 验证跨 ProjectId、错误来源角色、缺少双来源证据和未声明问题类型均失败关闭。
- 验证 OCR CJK 字符间空格规范化和 Golden Dataset 字段不进入 Prompt。
- R11 新增 10 项单元测试；POC-03 全量测试增至 203 项。

## 未执行

- 未对本轮 50 条已见留出集重新预测或重算分数。
- 未发起新的 Embedding、Reranker 或 DeepSeek 调用。
- 未生成或冻结新的开发集业务标签。
- 未修改数据库 Schema、正式 API、架构、模型供应商或质量门槛。

## 下一步

R11 离线修复合同已经具备。由于用户明确不重复本轮验证，POC-03 保持历史 FAIL，不能据此进入 Architecture Freeze；项目可继续推进不依赖该质量结论的其余 Phase 0 PoC。
