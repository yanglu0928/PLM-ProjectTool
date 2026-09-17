# Windows 11 中文 OCR 验证证据

## Environment

- Windows 11 Home 10.0.26200 x86-64。
- Python 3.13.15。
- OCRmyPDF 17.12.1。
- Tesseract 5.4.0.20240606。
- `tessdata_best`：固定提交 `e12c65a915945e4c28e237a9b52bc4a8f39a0cec`，包含 `chi_sim`、`chi_sim_vert`、`eng`、`osd` 并校验 SHA-256。

## Input

脚本生成一页 300 DPI 中文扫描 PDF，包含项目名称、需求调研、合同编号和客户确认等字段。输入文件为 `input-scanned.pdf`。

## Steps

1. 使用 `prepare-tessdata-best.ps1` 从 Tesseract 官方仓库准备高精度语言模型。
2. 使用 `run-ocr-validation.ps1` 调用离线 Python 环境。
3. OCRmyPDF 使用 `chi_sim+eng`、普通 PDF 输出、关闭优化、400 DPI 采样和 PSM 6。
4. 使用 PyMuPDF 提取输出文本，对五个预期术语计算召回率。

## Result

- OCRmyPDF exit code：0。
- searchable PDF：成功生成。
- 预期术语：5/5 命中。
- 术语召回率：100%。
- 结果：PASS。

## Metrics

|指标|结果|
|---|---|
|输入大小|189,198 bytes|
|输出大小|201,363 bytes|
|术语召回率|100%|
|语言覆盖|chi_sim + eng|

## Logs

- 最终结构化结果：`result.json`。
- OCRmyPDF 日志：`ocrmypdf-stderr.txt`。
- 高精度模型 Hash：`tessdata-best-sha256sums.txt`。
- 前两次 80% 识别结果及 deskew 失败结果作为回归证据保留。

## Known Issues

1. 使用 `--deskew` 时，OCRmyPDF 在中文 Windows 上按 UTF-8 解码 Tesseract 本地编码输出，触发 `UnicodeDecodeError`。
2. Ghostscript 非交互安装未完成，因此 PDF/A 和相关优化未验证。
3. 当前为合成清晰扫描件，不代表真实低质量扫描件准确率。

## Conclusion

Windows 11 上 Tesseract + OCRmyPDF 的普通 searchable PDF 中文主链可行，判定 PASS。deskew、PDF/A、Ghostscript 和真实扫描质量不包含在本结论中，继续作为 POC-05 Gate；发行许可证继续作为 POC-09 Gate。

## PASS / FAIL

`PASS`

## Alternative

核心 OCR 已通过，无需替换技术。Ghostscript/PDF-A 的选项和建议记录于 `ghostscript-install-attempt.md`。

## Source

- Tesseract 官方高精度模型仓库：https://github.com/tesseract-ocr/tessdata_best
