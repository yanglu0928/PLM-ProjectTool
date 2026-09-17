# Phase 0 三平台环境矩阵

## 目标环境

|项目|Windows 11|Windows Server 2025|Debian 13|验收要求|
|---|---|---|---|---|
|CPU 架构|x86-64|x86-64|x86-64|三端均须实际执行|
|Python|3.13.x|3.13.x|3.13.x|安装、创建 venv、核心依赖 import 和最小功能通过|
|数据库|PostgreSQL 18 + pgvector|PostgreSQL 18 + pgvector|PostgreSQL 18 + pgvector|离线安装、Alembic、HNSW、备份恢复|
|OCR|PaddleOCR + Tesseract + OCRmyPDF|PaddleOCR + Tesseract + OCRmyPDF|PaddleOCR + Tesseract + OCRmyPDF|扫描 PDF 可处理|
|Office 输出|python-docx + python-pptx|python-docx + python-pptx|python-docx + python-pptx|生成文件可由 Microsoft Office 正常打开|
|安装方式|完全离线|完全离线|完全离线|从本地制品完成 clean install|

## 当前可用环境

|环境|操作系统|CPU 架构|资源|Python 3.13|资格|状态|
|---|---|---|---|---|---|---|
|本地开发机 / Windows 11 验收环境|Windows 11 Home 10.0.26200|x86-64|32 逻辑处理器 / 31.63 GB RAM / D盘约 435.29 GB 可用|3.13.15|POC-01 已收口；POC-02 PostgreSQL/pgvector 功能链已验证|POC01_PASS / POC02_FUNCTIONAL_PASS|
|VMware / Windows Server 2025 验收环境|Windows Server 2025 Datacenter 10.0.26100（Desktop Experience）|x86-64|16 逻辑处理器 / 16 GB RAM / 系统盘约 54.71 GB 可用|3.13.15（官方嵌入式包）|POC-01 已收口；POC-02 完全断网功能链已验证|POC01_PASS / POC02_PASS|
|Linux 验收环境|Debian 13|x86-64|最低 4C / 8 GB / 100 GB|未确认|正式目标；本轮验证暂缓|DEFERRED_BY_USER|

## 当前工具发现

|工具|本机状态|说明|
|---|---|---|
|Git|AVAILABLE|仓库与远端正常|
|Python 3.14|AVAILABLE|不属于 POC-01 目标版本|
|Python 3.12|AVAILABLE|仅可作为失败后的候选替代，未经批准不得替换基线|
|Python 3.13|AVAILABLE|已安装 3.13.15；在线和 wheelhouse 离线预检通过|
|Docker|NOT_AVAILABLE|不能用本机容器替代 Debian 13 验收|
|WSL Debian 13|NOT_AVAILABLE|WSL 未安装发行版|
|Tesseract|AVAILABLE|5.4.0.20240606；`chi_sim/chi_sim_vert/eng/osd` 可用|
|OCRmyPDF Python 包/CLI|PASS|17.12.1；deskew + PDF/A-2b 中文 OCR 主链通过|
|tessdata_best|PASS|`chi_sim/chi_sim_vert/eng/osd` 已准备并保存 SHA-256|
|Ghostscript|PASS|10.08.0 项目内 portable 安装；安装包 Hash、版本及 PDF/A-2b 验证通过|
|OCRmyPDF deskew|PASS|补齐 `chi_sim_vert` 并增加 Windows 本地编码回退兼容层|
|PostgreSQL 18|PASS_PORTABLE|18.6 Windows x64 二进制 ZIP；纯 ASCII 隔离目录完成 init/start/stop、Migration、备份恢复|
|pgvector|PASS|0.8.6 已以 MSVC x64 构建；基础 CRUD、HNSW 与 10 万向量验证通过|
|Visual Studio C++ Build Tools|AVAILABLE|2022 17.14.41，MSVC 14.44 x64 与 `nmake` 已验证|

## 环境缺口

1. Debian 13 本轮验证依据 `EXC-P0-001` 暂缓；恢复验证时仍需可重复使用的 x86-64 环境。
2. POC-02 三个平台均需具备断网验收窗口；Windows 11 已使用本地制品，但未在物理断网状态执行。
3. Windows 11 与 Windows Server 2025 的 PostgreSQL 18.6 + pgvector 0.8.6 功能链已通过；Server 已完全断网验证，Windows 11 断网重放仍为 NOT_RUN。
4. Windows Server 2025 当前账号无管理员令牌，系统策略拒绝 Python EXE 安装器；POC-01 已使用官方嵌入式包验证无管理员部署路径。
5. Windows 11 的 PostgreSQL `initdb` 在中文运行路径失败；当前部署约束为程序、数据和临时 SQL 使用纯 ASCII 路径。

## 本机预检摘要

|检查|结果|
|---|---|
|Python 3.13.15 隔离环境|PASS|
|完整依赖在线安装|PASS|
|15 项 import / 最小功能检查|15/15 PASS|
|Windows wheelhouse|109 个文件，256.74 MB，109 个 SHA-256|
|使用 `--no-index` 的全新环境离线安装|PASS|
|离线环境 15 项检查|15/15 PASS|
|Tesseract 中文/英文语言|PASS|
|中文扫描 PDF → searchable PDF|PASS|
|预期术语召回率|5/5，100%|
|Ghostscript / PDF-A|PASS|
|deskew / 中文路径编码|PASS|
|PostgreSQL 18.6 init / start / stop|PASS（纯 ASCII 运行路径）|
|pgvector 0.8.6 构建 / CREATE EXTENSION|PASS|
|Alembic 空库及有数据 up/down|PASS|
|100,000 条 32 维向量 / HNSW|PASS；20 组 Top-5 Recall 100%|
|pg_dump / pg_restore / 重启健康检查|PASS|

## Windows Server 2025 实机验证摘要

|检查|结果|
|---|---|
|操作系统|Windows Server 2025 Datacenter 10.0.26100，x86-64|
|Python|3.13.15 官方嵌入式包；SHA-256 已按 Python.org 发布值校验|
|完整离线依赖安装|PASS（`--no-index`）|
|15 项 import / 最小功能检查|15/15 PASS|
|Tesseract 中文/英文语言|PASS|
|Ghostscript 10.08.0 / PDF-A-2b|PASS|
|OCRmyPDF deskew / 中文输出编码|PASS|
|预期术语召回率|5/5，100%|
|PostgreSQL 18.6 完全断网 init / start / stop|PASS|
|pgvector 0.8.6 / SQLAlchemy / Alembic|PASS|
|100,000 条 32 维向量 / HNSW|PASS；20 组 Top-5 Recall 100%|
|pg_dump / pg_restore / 重启健康检查|PASS|
