# POC-03 Windows 11 候选数据准备证据

## Scope

2026-09-17 在 Windows 11 上只读处理两个本地资料库：历史方案和技术协议/合同。原文件、原文件名、Hash、解析正文、OCR 正文、候选正文和本地映射均未提交 Git。

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

## Review Import Gate

- 新增本地评审表导入器，逐行核对候选编号、ProjectId、文档/Chunk、来源定位、正文和正文 Hash，不允许人工修改来源证据。
- 只转换 `APPROVED` 且查询、来源类型、分类、答案术语、确认引用、审核人和审核时间完整的记录。
- 确认引用必须来自原候选的来源定位；工作簿公式显示不作为导出依据，导入器独立重算 Gate。
- 修正后实际工作簿验证结果：120 行、109 条 `APPROVED`、11 条 `PENDING`、0 个问题；人工 Gate 为 `READY`，未通过的 11 条不会导出。
- 19/19 单元测试通过，其中评审导入覆盖 100 条正式集 Schema、待审核阻断、来源正文篡改、越界引用、缺失审核人、无效短查询、人工“确认全部定位”和本地日期格式。

## Index Binding

- P03-A04 已验证索引身份包含 provider、model、dimension 和 index_version。
- 同一 index_id 重复注册相同绑定是幂等操作；更改模型或维度会被拒绝，必须使用新 index_id。
- 候选绑定为阿里云百炼 OpenAI-compatible `qwen3.7-text-embedding`、1024 维、索引 `v1`。
- 本地结构与维度保护测试通过；因缺少对应供应商凭据，live dimension probe 为 `NOT_RUN`，候选尚未激活。
- 安全探测合同通过模拟验证：Key 不写入报告、返回维度必须匹配、HTTP 错误不透传厂商响应正文。

## Privacy

- `方案库/`、`技术协议&合同/` 和 `artifacts/` 均由 Git 忽略。
- 提交证据不含原文件名、客户名称、原始 Hash、解析正文、OCR 正文或候选正文。
- 仓库只保存脱敏文档编号、数量、类型、状态和质量边界。

## Result

候选集、工作簿和严格导入 Gate 已验证，109 条人工批准记录达到数量门槛。正式 Golden Dataset 仍需在 P03-A04 实际 Embedding 绑定激活后导出；当前不能计算或宣称 Top-5 Recall、分类准确率和引用准确率通过。

## Known Issues

1. 两个资料库共 10 个旧版二进制 `.doc` 尚不支持。
2. 当前来源覆盖历史方案以及合同/技术协议，仍缺少独立的标准能力和调研样本确认。
3. Tesseract 扫描件结果尚未完成语义准确率人工标注。
4. 候选 Embedding 服务缺少 live probe 凭据，P03-A04 保持 `IN_PROGRESS`。
