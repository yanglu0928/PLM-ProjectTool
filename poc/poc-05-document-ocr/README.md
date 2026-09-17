# POC-05 Document + OCR 统一解析

## Status

`IN_PROGRESS`

Windows 11 六类输入和主辅 OCR 功能链已通过；Windows Server 2025 已在虚拟网卡断开状态完成同一语料的全新离线复跑。另已在 Windows 11 对本地真实方案库完成只读批量解析：17/17 个受支持文件通过，1 个旧版 `.doc` 明确标记为不支持。POC-05 仍为 `IN_PROGRESS`：Windows 11 未做物理断网复跑，Debian 13 未执行，且方案库中没有真实扫描 PDF，不能替代真实扫描件 OCR 质量验收。

## Objective

验证 DOCX、PPTX、XLSX、CSV、文本 PDF 和扫描 PDF 能否通过同一入口转换为 PoC 级 `ParsedDocument`，并保留适用于原格式的页码、章节、工作表、表格和源位置。扫描 PDF 以 PaddleOCR 为主引擎，以 Tesseract/OCRmyPDF 为辅助链。

本目录中的 `ParsedDocument` 只是 Phase 0 验证结构，不是已冻结的正式数据模型或 API Contract。

## Environment

- Windows 11 Home 10.0.26200，x86-64，Python 3.13.15。
- Windows Server 2025 Datacenter 10.0.26100，x86-64，Python 3.13.15；已完成本 PoC 完全断网复跑。
- Debian 13 x86-64；当前无可用验收环境，状态为 `NOT_RUN`。
- Python 依赖沿用 POC-01 已验证范围：python-docx、python-pptx、openpyxl、PyMuPDF、pdfplumber、Pillow、PaddleOCR、PaddlePaddle、pytesseract、OCRmyPDF。
- Tesseract、Ghostscript、OCRmyPDF 的 Windows 安装与中文 `--deskew` 编码兼容修复沿用 POC-01 成果，但必须在本 PoC 输入上重新执行。

## Input

`input/` 保存不含客户数据的自生成测试语料：

- `sample.docx`：标题、两个章节、显式分页和表格；
- `sample.pptx`：两页幻灯片、标题、正文和原生表格；
- `sample.xlsx`：两个工作表和结构化行列数据；
- `sample.csv`：UTF-8 BOM、中文列名和多行记录；
- `sample-text.pdf`：两页可检索文本和表格；
- `sample-scan.pdf`：含轻微倾斜、噪声与对比度衰减的中文扫描样本。

这些样本用于验证格式覆盖和来源定位。真实客户扫描件准确率仍需在取得脱敏样本后补充。

Windows 11 真实方案库验证使用仓库根目录下被 Git 忽略的 `方案库/` 作为只读输入。该批次共 18 个文件、365,328,831 字节，包含 11 个 DOCX、5 个 PPTX、1 个文本 PDF 和 1 个旧版 DOC。原文件名、Hash、解析正文和逐文件本地映射只保存在被 Git 忽略的 `artifacts/poc-05/solution-library/`；仓库仅保留脱敏统计。

## Steps

1. 使用固定内容规范生成六类输入，并记录 SHA-256。
2. 对 PPTX、XLSX 和 PDF 样本执行逐页/逐表可视化检查；DOCX 执行 OOXML 结构检查并记录渲染器缺口。
3. 通过统一 CLI 解析六类输入并输出 `ParsedDocument` JSON。
4. 验证每个输出符合 PoC JSON Schema，且保留原格式可提供的页码、章节、工作表、表格和源定位。
5. 对扫描 PDF 分别执行 PaddleOCR 与 Tesseract；另用 OCRmyPDF 生成 searchable PDF 并回读文本。
6. 统计预期术语召回率、处理耗时、块数量、页数和表格行数。
7. 在 Windows Server 2025 使用同一输入和脚本复跑；Debian 13 保持独立未验证状态，除非后续取得环境或用户批准例外。
8. 对本地真实方案库执行 OOXML 包完整性检查、格式识别、统一解析、Schema 校验及解析前后 Hash/大小/修改时间核对；不修改原件，不提交文件名或正文。

## Result

|验收域|Windows 11|Windows Server 2025|Debian 13|说明|
|---|---|---|---|---|
|测试语料与 Hash|PASS|PASS|NOT_RUN|两端输入 SHA-256 一致|
|DOCX 统一解析|PASS|PASS|NOT_RUN|2 个显式页、15 个块、7 个表格行|
|PPTX 统一解析|PASS|PASS|NOT_RUN|2 张幻灯片、7 个块、4 个表格行|
|XLSX 统一解析|PASS|PASS|NOT_RUN|2 个工作表、9 个表格行|
|CSV 统一解析|PASS|PASS|NOT_RUN|3 个表格行，保留行号|
|文本 PDF 统一解析|PASS|PASS|NOT_RUN|2 页、19 个块、6 个表格行|
|扫描 PDF PaddleOCR|PASS|PASS|NOT_RUN|两端预期术语 5/5|
|扫描 PDF Tesseract/OCRmyPDF|PASS|PASS|NOT_RUN|两端两条辅助链均为 5/5|
|Schema 与来源断言|PASS|PASS|NOT_RUN|两端 8/8 结果 PASS|
|完全离线复跑|PASS_LOCAL_ASSETS|PASS|NOT_RUN|Server：1 个物理网卡、0 个连接|
|真实方案库只读批量解析|PARTIAL_PASS|NOT_RUN|NOT_RUN|17/17 个受支持文件 PASS；1 个旧版 `.doc` 不在当前范围；18/18 原件未改变|

## Metrics

|指标|Windows 11|Windows Server 2025|
|---|---|---|
|六类输入统一解析|PASS|PASS|
|扫描 PDF PaddleOCR 耗时 / 召回|10.981 s / 100%|14.311 s / 100%|
|扫描 PDF Tesseract 耗时 / 召回|1.222 s / 100%|1.247 s / 100%|
|OCRmyPDF PDF/A-2b + deskew 耗时 / 召回|7.386 s / 100%|7.768 s / 100%|
|PoC Schema 错误|0|0|
|PaddleOCR 模型|PP-OCRv5 mobile det + rec|同一模型 Hash，显式本地目录|
|离线状态|本地制品重放，网络未隔离|1 个物理网卡、0 个连接|

Windows 11 真实方案库批次指标：

|指标|结果|
|---|---|
|总输入|18 个，365,328,831 字节|
|受支持输入|17 个：DOCX 11、PPTX 5、文本 PDF 1|
|统一解析与 Schema|17/17 PASS，0 个 Schema 错误|
|解析输出|492 个页/幻灯片或显式页对象、13,710 个块、2,399 个表格行|
|OOXML 包检查|16/16 PASS|
|原件不变性|18/18 PASS|
|批次耗时|22.110 秒，其中解析器累计 20.637 秒|
|旧格式|1 个 `.doc`，`UNSUPPORTED`|

上述批次只验证结构提取、Schema、来源定位和输入不变性；由于没有人工标注答案集，不把块数量或成功退出码解释为语义完整率或 OCR 准确率。

性能数字只用于本 PoC 主机上的方案比较，不构成生产容量承诺。

## Logs

- Windows 11：`evidence/windows-11/`
- Windows 11 真实方案库脱敏结果：`evidence/windows-11/solution-library-validation.json` 与 `solution-library-README.md`
- Windows Server 2025：`evidence/windows-server-2025/`
- Debian 13：`evidence/debian-13/`
- 大型模型、渲染中间文件和原始运行日志保存在被 Git 忽略的 `artifacts/poc-05/`。

## Known Issues

1. 已完成真实业务方案 DOCX、PPTX 和文本 PDF 的结构解析，但当前方案库没有真实扫描 PDF；自生成退化扫描样本通过只能证明技术链可执行，不能代替真实扫描资料质量结论。
2. Windows 11 使用显式本地模型目录完成重放，但没有物理断开主机网络；只有 Windows Server 2025 形成完全断网证据。
3. XLSX 和 CSV 没有天然页码；本 PoC 使用工作表、行号和单元格范围作为来源，不伪造物理页码。
4. DOCX 的物理分页取决于排版引擎；PoC 仅保证显式分页符和章节来源，自动分页页码需由渲染或版面解析补充。
5. Debian 13 尚未执行；两个 Windows 平台的结果不能替代 Debian 兼容性结论。
6. PaddlePaddle 3.3.1 在本次 Windows CPU 环境启用 oneDNN 时触发 `ConvertPirAttribute2RuntimeAttribute` 未实现错误；PoC 通过 `enable_mkldnn=False` 稳定运行，需作为 Windows 运行约束继续回归。
7. Windows PowerShell 5.1 读取 Python 生成的无 BOM UTF-8 JSON 时会按本地代码页解码；Server 驱动已显式使用 `-Encoding UTF8`。
8. 当前工作区依赖未提供打包的 LibreOffice，DOCX 样本无法按文档制作规范完成 DOCX 转 PNG；已完成 OOXML 结构解析，Microsoft Office 打开性属于 POC-06。
9. 当前统一解析器不支持旧版二进制 `.doc`；方案库中的 1 个 `.doc` 保留为 `UNSUPPORTED`，未自动转换或改写。是否把旧格式转换纳入 P0 需单独确认。
10. 真实方案库发现部分 DOCX 段落样式对象没有名称；解析器已将其按空样式兼容处理，并增加回归测试。

## Conclusion

统一 `ParsedDocument` 技术路径在 Windows 11 和 Windows Server 2025 上可行：六类输入均通过同一入口输出 PoC Schema，并保留页码/幻灯片号、章节、工作表、表格及源定位；PaddleOCR 主链和 Tesseract/OCRmyPDF 辅助链在固定退化扫描样本上均达到 5/5 术语召回。Windows Server 2025 已证明受控模型和运行制品可完全断网执行。

Windows 11 真实方案库的 17 个受支持文件也已全部完成结构解析和 Schema 校验，说明解析器可以处理远大于自生成样本的真实 DOCX、PPTX 与文本 PDF；该结果不包含旧版 `.doc`，也不构成真实扫描件准确率结论。

POC-05 尚不收口。Windows 11 物理断网复跑、Debian 13 和真实脱敏扫描件质量仍待处理或取得独立用户例外。

## PASS / FAIL

`IN_PROGRESS`

## Alternative

- 若 PaddleOCR 在 Python 3.13 或目标 CPU 上不可用，先保留失败证据，再评估同系列轻量模型、ONNX 推理或独立 OCR 子进程；不得直接把 Tesseract 改写为主技术基线。
- 若 DOCX 自动分页无法可靠恢复，统一结构保留显式分页与 OOXML 定位，并把物理页码标记为未知；不得生成猜测页码。
- 若复杂表格提取质量不足，保留原表格坐标、行列文本和源定位，后续通过专用表格解析器增强，不阻塞纯文本回退。
