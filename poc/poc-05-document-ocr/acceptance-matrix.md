# POC-05 验收矩阵

|ID|验收项|Windows 11|Windows Server 2025|Debian 13|证据要求|
|---|---|---|---|---|---|
|P05-A01|环境、依赖与权限采集|PASS|PASS|DEFERRED_BY_USER|脱敏环境 JSON|
|P05-A02|六类自生成输入及 SHA-256|PASS|PASS|DEFERRED_BY_USER|manifest + SHA-256|
|P05-A03|DOCX 输出统一 ParsedDocument|PASS|PASS|DEFERRED_BY_USER|JSON、章节、显式页码、表格定位|
|P05-A04|PPTX 输出统一 ParsedDocument|PASS|PASS|DEFERRED_BY_USER|JSON、幻灯片号、章节、表格定位|
|P05-A05|XLSX 输出统一 ParsedDocument|PASS|PASS|DEFERRED_BY_USER|JSON、工作表、单元格范围|
|P05-A06|CSV 输出统一 ParsedDocument|PASS|PASS|DEFERRED_BY_USER|JSON、行号、列结构|
|P05-A07|文本 PDF 输出统一 ParsedDocument|PASS|PASS|DEFERRED_BY_USER|JSON、页码、章节、表格定位|
|P05-A08|扫描 PDF 使用 PaddleOCR 解析|PASS|PASS|DEFERRED_BY_USER|模型信息、JSON、耗时、召回率|
|P05-A09|扫描 PDF 使用 Tesseract 解析|PASS|PASS|DEFERRED_BY_USER|版本、JSON、耗时、召回率|
|P05-A10|OCRmyPDF searchable PDF 回读|PASS|PASS|DEFERRED_BY_USER|退出码、PDF/A/deskew、回读文本|
|P05-A11|PoC JSON Schema 校验|PASS|PASS|DEFERRED_BY_USER|自动化断言|
|P05-A12|页码/章节/表格来源断言|PASS|PASS|DEFERRED_BY_USER|逐格式断言结果|
|P05-A13|中文和英文预期术语召回|PASS|PASS|DEFERRED_BY_USER|逐术语命中及比例|
|P05-A14|完全离线模型和运行制品复跑|PASS_LOCAL_ASSETS|PASS|DEFERRED_BY_USER|网络隔离说明、manifest、执行结果|
|P05-A15|真实方案库只读批量解析|PARTIAL_PASS|NOT_RUN|DEFERRED_BY_USER|17/17 个受支持文件通过；1 个旧版 `.doc` 为 `UNSUPPORTED`|
|P05-A16|真实方案库隐私与输入不变性|PASS|NOT_RUN|DEFERRED_BY_USER|不提交文件名/正文/Hash；18/18 原件前后校验一致|
|P05-A17|真实技术协议/合同批量解析|PARTIAL_PASS|NOT_RUN|DEFERRED_BY_USER|9/9 个受支持文件通过；含 5 个扫描 PDF；9 个旧版 `.doc` 不支持|
|P05-A18|真实扫描 PDF 技术链与输入不变性|PASS|NOT_RUN|DEFERRED_BY_USER|5 个、105 页、45,145 个 OCR 行、Schema 0 错误；18/18 原件未改变|
|P05-A19|真实扫描 PDF 分层语义准确率|PASS|NOT_RUN|DEFERRED_BY_USER|5 个文档、15 页、75 个视觉真值检查点；PaddleOCR 75/75、关键错误 0；Tesseract 基线 FAIL 并降级为辅助链|

## 当前验收阈值

- 所有六类输入必须成功生成符合 `schema/parsed-document.schema.json` 的 JSON。
- DOCX、PPTX 和文本 PDF 必须保留页码或幻灯片号、章节和表格来源。
- XLSX 和 CSV 必须保留工作表或文件章节、行号以及单元格/行范围；其 `page` 允许为 `null`。
- 扫描 PDF 的 PaddleOCR 主链与 Tesseract 辅助链，在自生成样本上的预期术语召回率均不得低于 90%。
- OCRmyPDF 必须成功生成可检索 PDF，`--deskew` 中文 Windows 输出不得触发编码异常。
- 任何未执行平台均保持 `NOT_RUN`；只有用户明确批准并登记例外后才能改为 `DEFERRED_BY_USER`。
- 真实方案库批次仅验证结构解析、Schema、来源定位和输入不变性；没有人工标注答案集时，不得把成功解析报告成语义完整率或 OCR 准确率。
- 真实扫描件采用先看原页、后比 OCR 的分层检查点法；语义检查点相似度至少 0.85，数值/代码/版本必须完全一致，总召回至少 95%，关键错误必须为 0。
- PaddleOCR 为真实扫描件主链；Tesseract 若未满足上述门槛，只能作为辅助回退，关键字段必须由主链或人工确认。

## 状态定义

- `PASS`：已执行且证据满足要求。
- `PASS_LOCAL_ASSETS`：已从显式本地模型和制品成功执行，但主机物理网络未隔离；不等同于完全离线 PASS。
- `NOT_RUN`：尚未执行，不得视为失败或通过。
- `BLOCKED_INPUT`：缺少满足验收要求的输入。
- `BLOCKED_RUNTIME`：依赖、模型或本机能力阻止执行。
- `FAIL`：已执行但未满足标准，必须保留失败分析。
- `DEFERRED_BY_USER`：仅可在用户明确批准并登记例外后使用。
- `PARTIAL_PASS`：批次内所有当前支持格式均通过，但仍存在明确记录的不支持输入；不等同于整个 POC PASS。
