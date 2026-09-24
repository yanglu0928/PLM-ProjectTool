# Windows 11 中文 OCR 验证证据

## Environment

- Windows 11 Home 10.0.26200 x86-64。
- Python 3.13.15。
- OCRmyPDF 17.12.1。
- Tesseract 5.4.0.20240606。
- Ghostscript 10.08.0，项目内 portable 安装。
- `tessdata_best`：固定提交 `e12c65a915945e4c28e237a9b52bc4a8f39a0cec`，包含 `chi_sim`、`chi_sim_vert`、`eng`、`osd` 并校验 SHA-256。

## Input

脚本生成一页 300 DPI 中文扫描 PDF，包含项目名称、需求调研、合同编号和客户确认等字段。输入文件为 `input-scanned.pdf`。

## Steps

1. 使用 `prepare-tessdata-best.ps1` 从 Tesseract 官方仓库准备高精度语言模型。
2. 使用 `install-ghostscript-portable.ps1` 安装并校验 Ghostscript。
3. 通过项目兼容层处理 Tesseract 的 UTF-8/Windows 本地编码输出。
4. 使用 `run-ocr-validation.ps1` 调用离线 Python 环境。
5. OCRmyPDF 使用 `chi_sim+eng`、PDF/A-2b、deskew、关闭优化、400 DPI 采样和 PSM 6。
6. 使用 PyMuPDF 提取输出文本，对五个预期术语计算召回率。

## Result

- OCRmyPDF exit code：0。
- searchable PDF：成功生成并通过 PDF/A-2b 检查。
- deskew：成功执行。
- 预期术语：5/5 命中。
- 术语召回率：100%。
- 结果：PASS。

## Metrics

|指标|结果|
|---|---|
|输入大小|189,198 bytes|
|输出大小|320,053 bytes|
|术语召回率|100%|
|语言覆盖|chi_sim + eng|
|Ghostscript|10.08.0|
|PDF/A|PDF/A-2b PASS|
|deskew|PASS|

## Logs

- 最终结构化结果：`result.json`。
- OCRmyPDF 日志：`ocrmypdf-stderr.txt`。
- 高精度模型 Hash：`tessdata-best-sha256sums.txt`。
- Ghostscript 安装证据：`ghostscript-installation.md`。
- 前两次 80% 识别结果及 deskew 失败结果作为回归证据保留。

## Known Issues

1. Windows 编码兼容层使用 OCRmyPDF 内部解析函数挂接，升级 OCRmyPDF 时必须执行回归测试。
2. 当前为合成清晰扫描件，不代表真实低质量扫描件准确率。
3. 当前仓库仍为私有；包含 Ghostscript 的对外发行需先完成 ADR-002 的源码公开与许可证 Gate。

## Conclusion

Windows 11 上 Tesseract + OCRmyPDF + Ghostscript 的 PDF/A-2b 中文主链可行，deskew 与编码兼容修复均通过，判定 PASS。真实扫描质量继续作为 POC-05 Gate；源码公开和发行许可证继续作为 POC-09 / Release Gate。

## PASS / FAIL

`PASS`

## Alternative

核心 OCR 已通过，无需替换技术。首次安装失败及解决过程记录于 `ghostscript-install-attempt.md` 和 `ghostscript-installation.md`。

## Source

- Tesseract 官方高精度模型仓库：https://github.com/tesseract-ocr/tessdata_best
- Ghostscript 官方发布页：https://github.com/ArtifexSoftware/ghostpdl-downloads/releases
