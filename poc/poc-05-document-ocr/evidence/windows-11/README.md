# Windows 11 验证证据

## Result

`FUNCTIONAL_PASS`

Windows 11 10.0.26200 x86-64、Python 3.13.15 完成六类输入统一解析、PoC JSON Schema、来源定位、PaddleOCR、Tesseract 和 OCRmyPDF PDF/A-2b + deskew 验证。PaddleOCR 与两条辅助链的扫描术语召回均为 5/5。

PaddleOCR 使用显式本地模型目录复跑，但主机物理网络未隔离，因此完全离线项记为 `PASS_LOCAL_ASSETS`，不等同于完全离线 PASS。

## Evidence

- `environment.json`：操作系统、Python、包和外部工具版本。
- `input-manifest.json`：六类输入的大小和 SHA-256。
- `model-manifest.json`：PP-OCRv5 mobile 检测/识别模型文件、大小和 SHA-256。
- `validation-result.json`：最终 8/8 PASS 结果。
- `validation-result-attempt-1.json`：首次 OCRmyPDF 标题单字误识别导致 4/5 的失败记录；调整固定扫描退化参数后最终达到 5/5。

运行期 ParsedDocument、searchable PDF 和 stderr 位于被 Git 忽略的 `artifacts/poc-05/runtime/windows-11/`。
