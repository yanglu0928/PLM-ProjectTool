# Windows 11 验证证据

## Result

`PASS_WITH_EXCEPTION`

Windows 11 10.0.26200 x86-64、Python 3.13.15 完成六类输入统一解析、PoC JSON Schema、来源定位、PaddleOCR、Tesseract 和 OCRmyPDF PDF/A-2b + deskew 验证。PaddleOCR 与两条辅助链的扫描术语召回均为 5/5。

PaddleOCR 使用显式本地模型目录复跑，但主机物理网络未隔离，因此完全离线项记为 `PASS_LOCAL_ASSETS`，不等同于完全离线 PASS。

真实扫描件语义审计新增 5 份匿名文档、15 个分层抽样页和 75 个视觉真值检查点。PaddleOCR 主链 75/75、关键错误 0，结果 `PASS`；既有 Tesseract 辅助链 70/75、关键错误 2，结果 `FAIL`，不得作为关键字段唯一来源。Windows 11 物理断网复跑依据 `EXC-P0-004` 暂缓。

## Evidence

- `environment.json`：操作系统、Python、包和外部工具版本。
- `input-manifest.json`：六类输入的大小和 SHA-256。
- `model-manifest.json`：PP-OCRv5 mobile 检测/识别模型文件、大小和 SHA-256。
- `validation-result.json`：最终 8/8 PASS 结果。
- `validation-result-attempt-1.json`：首次 OCRmyPDF 标题单字误识别导致 4/5 的失败记录；调整固定扫描退化参数后最终达到 5/5。
- `real-scan-semantic-audit.json`：真实扫描件匿名抽样、阈值、主辅 OCR 结果与使用边界。
- `real-scan-semantic-audit.md`：真实扫描件语义审计方法、结论和隐私边界。

运行期 ParsedDocument、searchable PDF 和 stderr 位于被 Git 忽略的 `artifacts/poc-05/runtime/windows-11/`。
