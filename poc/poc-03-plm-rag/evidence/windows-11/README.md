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

## Privacy

- `方案库/`、`技术协议&合同/` 和 `artifacts/` 均由 Git 忽略。
- 提交证据不含原文件名、客户名称、原始 Hash、解析正文、OCR 正文或候选正文。
- 仓库只保存脱敏文档编号、数量、类型、状态和质量边界。

## Result

候选集生成链路 PASS，但这些记录尚未人工确认，因此不能计入正式 Golden Dataset，不能计算或宣称 Top-5 Recall、分类准确率和引用准确率通过。

## Known Issues

1. 两个资料库共 10 个旧版二进制 `.doc` 尚不支持。
2. 当前来源覆盖历史方案以及合同/技术协议，仍缺少独立的标准能力和调研样本确认。
3. Tesseract 扫描件结果尚未完成语义准确率人工标注。
