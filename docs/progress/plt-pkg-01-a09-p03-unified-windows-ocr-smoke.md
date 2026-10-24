# PLT-PKG-01-A09-P03：统一候选 Windows 11 OCR 路径与版面验收

日期：2026-10-01；状态：`ASCII_PATH_SYNTHETIC_OCR_PASS / NON_ASCII_PATH_FAIL / RELEASE_OPEN`。

## 前置与范围

Phase 2 / `PLT-PKG-01-A09-P03`；输入为 [A09-P02 统一非发行候选](plt-pkg-01-a09-p02-unified-windows-candidate.md)，其 ZIP SHA-256 `da285e1c88d45f195d141f5eb6cba5f887f019063f4547a0a54ecae78c251bff`。仅用仓库现有 POC-01 合成 OCR 验证器对包内 Python、Tesseract、Ghostscript、tessdata 做端到端验证；无正式程序/API/ORM/Migration/权限或客户数据变更。验收为 `--deskew --output-type pdfa-2 --tesseract-pagesegmode 3` 的真实进程退出0、PDF/A-2b真、五个预期中文/英数字术语均出现；路径失败必须单列。回滚仅弃用本机 Git 忽略的测试解包/输出，不影响原候选。

## 实测

先从仓库含中文的路径下清洁解包并完成19,449项逐件Hash，再直接指向该解包目录运行表格版面：OCRmyPDF 退出3；Tesseract `--list-langs` 报 `filesystem error: Cannot convert character sequence: Illegal byte sequence`，无输出 PDF。因此“任意 Windows 安装路径可用”不成立，不能把这轮记为成功。失败输出在本机临时目录，未提交客户数据。

再将**同一 ZIP** 全新解包到 ASCII 路径 `C:/Users/17231/AppData/Local/Temp/plm-unified-candidate-ascii-20261001`，运行前逐件Hash与文件集再次 `CLEAN_EXTRACT_HASH_PASS`（19,449项）。仅把 `TESSERACT_EXE`、`GHOSTSCRIPT_EXE`、`TESSDATA_PREFIX` 指向该包内资产，不借用系统已安装 OCR；调用包内 Python3.13.15 与OCRmyPDF17.12.1。四种合成版面如下：

| 版面 | OCRmyPDF | PDF/A-2b | 五术语 |
|---|---|---|---|
| 标准 | exit0 | 真 | 5/5 |
| 密集 | exit0 | 真 | 5/5 |
| 表格 | exit0 | 真 | 5/5 |
| 轻微倾斜 | exit0 | 真 | 5/5 |

本项仅证明 Windows11 + ASCII 路径 + 四份**合成** PDF 的包内 OCR 闭环；不证明真实中文客户扫描质量、复杂表格/低质图、正式部署账户或 Server2025/Debian13。非 ASCII 路径的失败属于当前 Tesseract 原生资产的已知限制。下一任务应在安装/升级入口显式拒绝不支持的非 ASCII 安装根路径，或用同等严格的新原生版本修复并复验；现行建议安装根 `C:\PLMTool` 符合此限制，但其正式安装器尚未完成。NOTICE/AGPL、签名/License、质量、完整离线安装及 Gate 仍开放；`release_eligible=false`。
