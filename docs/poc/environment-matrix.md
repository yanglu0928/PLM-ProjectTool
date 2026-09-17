# Phase 0 双平台环境矩阵

## 目标环境

|项目|Windows 目标|Debian 目标|验收要求|
|---|---|---|---|
|操作系统|Windows Server 2025 x86-64|Debian 13 x86-64|两端均须实际执行|
|Python|3.13.x|3.13.x|安装、创建 venv、核心依赖 import 和最小功能通过|
|数据库|PostgreSQL 18 + pgvector|PostgreSQL 18 + pgvector|离线安装、Alembic、HNSW、备份恢复|
|OCR|PaddleOCR + Tesseract + OCRmyPDF|PaddleOCR + Tesseract + OCRmyPDF|扫描 PDF 可处理|
|Office 输出|python-docx + python-pptx|python-docx + python-pptx|生成文件可由 Microsoft Office 正常打开|
|安装方式|完全离线|完全离线|从本地制品完成 clean install|

## 当前可用环境

|环境|操作系统|CPU 架构|资源|Python 3.13|资格|状态|
|---|---|---|---|---|---|---|
|本地开发机|Windows 11 Home 10.0.26200|x86-64|32 逻辑处理器 / 31.63 GB RAM / D盘约 441.76 GB 可用|3.13.15|仅本机预检，不替代正式环境|LOCAL_PRECHECK_PASS|
|Windows 验收环境|Windows Server 2025|x86-64|最低 4C / 8 GB / 100 GB|未确认|正式验收|BLOCKED_ENVIRONMENT|
|Linux 验收环境|Debian 13|x86-64|最低 4C / 8 GB / 100 GB|未确认|正式验收|BLOCKED_ENVIRONMENT|

## 当前工具发现

|工具|本机状态|说明|
|---|---|---|
|Git|AVAILABLE|仓库与远端正常|
|Python 3.14|AVAILABLE|不属于 POC-01 目标版本|
|Python 3.12|AVAILABLE|仅可作为失败后的候选替代，未经批准不得替换基线|
|Python 3.13|AVAILABLE|已安装 3.13.15；在线和 wheelhouse 离线预检通过|
|Docker|NOT_AVAILABLE|不能用本机容器替代 Debian 13 验收|
|WSL Debian 13|NOT_AVAILABLE|WSL 未安装发行版|
|Tesseract|NOT_AVAILABLE|后续安装并验证|
|OCRmyPDF Python 包/CLI|AVAILABLE_IN_POC_VENV|17.12.1 可安装并导入；完整执行仍缺 Tesseract/Ghostscript|
|PostgreSQL client|NOT_AVAILABLE|属于 POC-02 准备项|

## 环境缺口

1. 需要可重复使用的 Windows Server 2025 x86-64 环境。
2. 需要可重复使用的 Debian 13 x86-64 环境。
3. 两端需具备断网验收窗口，以验证 wheel/deb/安装介质完整性。
4. 本机预检通过只降低脚本和依赖组合风险，不改变上述正式环境缺口状态。

## 本机预检摘要

|检查|结果|
|---|---|
|Python 3.13.15 隔离环境|PASS|
|完整依赖在线安装|PASS|
|15 项 import / 最小功能检查|15/15 PASS|
|Windows wheelhouse|109 个文件，256.74 MB，109 个 SHA-256|
|使用 `--no-index` 的全新环境离线安装|PASS|
|离线环境 15 项检查|15/15 PASS|
