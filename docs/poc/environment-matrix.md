# Phase 0 三平台环境矩阵

## 目标环境

|项目|Windows 11|Windows Server 2025|Debian 13|验收要求|
|---|---|---|---|---|
|CPU 架构|x86-64|x86-64|x86-64|三端均须实际执行|
|Python|3.13.x|3.13.x|3.13.x|安装、创建 venv、核心依赖 import 和最小功能通过|
|数据库|PostgreSQL 18 + pgvector|PostgreSQL 18 + pgvector|PostgreSQL 18 + pgvector|离线安装、Alembic、HNSW、备份恢复|
|OCR|PaddleOCR + Tesseract + OCRmyPDF|PaddleOCR + Tesseract + OCRmyPDF|PaddleOCR + Tesseract + OCRmyPDF|扫描 PDF 可处理|
|Office 输出|python-docx + python-pptx|python-docx + python-pptx|python-docx + python-pptx|生成文件可由 Microsoft Office 正常打开；本轮 POC-06 PPTX 制件因工作区规范使用 Artifact Tool，不变更正式基线|
|安装方式|完全离线|完全离线|完全离线|从本地制品完成 clean install|

## 当前可用环境

|环境|操作系统|CPU 架构|资源|Python 3.13|资格|状态|
|---|---|---|---|---|---|---|
|本地开发机 / Windows 11 验收环境|Windows 11 Home 10.0.26200|x86-64|32 逻辑处理器 / 31.63 GB RAM / D盘约 435.29 GB 可用|3.13.15|POC-01 已收口；POC-02 功能链已验证；POC-03 候选数据准备已验证；POC-04 统一网关与真实 DeepSeek 已验证；POC-05 功能链与真实扫描分层语义审计已验证；POC-06 Office 实开已验证；POC-08 Plugin Host 与 POC-09 License 已验证|POC01_PASS / POC02_FUNCTIONAL_PASS / POC03_DATASET_CANDIDATES_PASS / POC04_FUNCTIONAL_PASS / POC05_PASS_WITH_EXCEPTION / POC06_PASS / POC08_PASS / POC09_PASS|
|VMware / Windows Server 2025 验收环境|Windows Server 2025 Datacenter 10.0.26100（Desktop Experience）|x86-64|16 逻辑处理器 / 16 GB RAM / 系统盘约 54.71 GB 可用|3.13.15（官方嵌入式包）|POC-01 已收口；POC-02、POC-05 完全断网功能链已验证；POC-04 统一网关与真实 DeepSeek 已验证；POC-06 包结构/Hash 已验证但 Office 未安装；POC-08 Plugin Host 与 POC-09 License 离线链已验证|POC01_PASS / POC02_PASS / POC04_FUNCTIONAL_PASS / POC05_PASS / POC06_PARTIAL_OFFICE_BLOCKED / POC08_PASS / POC09_PASS|
|Linux 验收环境|Debian 13|x86-64|最低 4C / 8 GB / 100 GB|未确认|正式目标；POC-01/POC-02/POC-04/POC-05 验证经用户批准暂缓；POC-08/POC-09 尚未取得独立例外|DEFERRED_BY_USER / POC04_DEFERRED_BY_USER / POC05_DEFERRED_BY_USER / POC08_NOT_RUN / POC09_NOT_RUN|

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
|PaddleOCR 3.7 / PaddlePaddle 3.3.1|PASS_WITH_CONSTRAINT|PP-OCRv5 mobile det/rec；Windows CPU 必须设置 `enable_mkldnn=False` 规避 oneDNN 未实现错误|
|PostgreSQL 18|PASS_PORTABLE|18.6 Windows x64 二进制 ZIP；纯 ASCII 隔离目录完成 init/start/stop、Migration、备份恢复|
|pgvector|PASS|0.8.6 已以 MSVC x64 构建；基础 CRUD、HNSW 与 10 万向量验证通过|
|Visual Studio C++ Build Tools|AVAILABLE|2022 17.14.41，MSVC 14.44 x64 与 `nmake` 已验证|
|httpx / jsonschema|PASS|0.28.1 / 4.26.0；POC-04 确定性协议和异常场景 11/11 PASS|
|DeepSeek 官方端点|PASS_WINDOWS11_SERVER2025|Windows 11、Windows Server 2025 的 401 连通性、真实文本、SSE 流式和结构化 JSON 已通过；不记录密钥或响应正文|
|POC-03 候选数据准备|PASS_WINDOWS11|26 个可解析真实资料、60,430 个块、655 个 PROJECT Chunk、120 条待人工评审候选；不记录原文件名或正文|

## 环境缺口

1. Debian 13 的 POC-01/POC-02/POC-04/POC-05 分别依据 `EXC-P0-001`、`EXC-P0-002`、`EXC-P0-003`、`EXC-P0-004` 暂缓。恢复验证时仍需可重复使用的 x86-64 环境。
2. POC-02 Windows 11 已使用本地制品完成全部功能验证，但物理断网重放依据 `EXC-P0-002` 暂缓。
3. Windows 11 与 Windows Server 2025 的 PostgreSQL 18.6 + pgvector 0.8.6 功能链已通过；Server 已完全断网验证，Windows 11 断网重放为 `DEFERRED_BY_USER`。
4. Windows Server 2025 当前账号无管理员令牌，系统策略拒绝 Python EXE 安装器；POC-01 已使用官方嵌入式包验证无管理员部署路径。
5. Windows 11 的 PostgreSQL `initdb` 在中文运行路径失败；当前部署约束为程序、数据和临时 SQL 使用纯 ASCII 路径。
6. POC-05 Windows 11 已从显式本地 PaddleOCR 模型目录重放，但物理断网依据 `EXC-P0-004` 暂缓；Windows Server 2025 已完全断网通过。
7. POC-05 已对 5 个真实扫描 PDF 的 15 个分层抽样页建立 75 个视觉真值检查点；PaddleOCR 75/75，Tesseract 70/75。该抽样结论不等同于 105 页逐字符全量标注。
8. POC-04 Windows 11 与 Windows Server 2025 功能链已通过；Debian 13 依据 `EXC-P0-003` 暂缓且保持未验证。
9. POC-03 已形成 120 条候选记录，但 0 条完成 APPROVED 人工确认；Top-5 Recall、分类准确率和来源引用准确率保持 `NOT_RUN`。
10. POC-06 Windows 11 完成 100 页 Word / 50 页 PowerPoint 实开、PDF 导出和全量视觉检查；Windows Server 2025 未安装 Microsoft Office，只完成 OOXML 包与 Hash 复验，不得外推 Office 兼容性。
11. POC-08 Windows 11 与 Windows Server 2025 已通过；Debian 13 仍缺少可执行环境，不得以 Windows 结果替代 Linux 进程/信号/stdio 兼容性证据。
12. POC-09 Windows 11 与 Windows Server 2025 已通过；Debian 13 的 `/sys/class/net` 网卡枚举与 cryptography/Ed25519 离线链仍须实际执行。

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
|POC-05 六类输入统一解析|PASS；Schema 错误 0|
|POC-05 扫描 PDF PaddleOCR / Tesseract / OCRmyPDF|三条链术语召回均为 5/5|
|POC-05 真实扫描分层语义审计|PaddleOCR 75/75、关键错误 0；Tesseract 70/75，仅作辅助链|
|POC-06 Word / PowerPoint|Word 100 页、PowerPoint 50 页；Office 实开/PDF 导出 PASS；150 页全量视觉检查 PASS|
|POC-08 Plugin Host|13/13 测试、10/10 场景、20/20 并发 PASS；crash/timeout 后 FastAPI 健康|
|POC-09 License|26/26 测试、10/10 场景 PASS；核心覆盖率 91%～94%，8/8 非法授权拒绝|
|POC-03 候选评审记录|120 条；覆盖 26/26 个可解析真实资料；全部为 `PENDING_HUMAN_REVIEW`|

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
|POC-05 完全断网六类输入统一解析|PASS；8/8|
|POC-05 PaddleOCR 本地模型 / Tesseract / OCRmyPDF|PASS；三条链术语召回均为 5/5|
|POC-04 AI Gateway 单元测试 / 确定性场景|PASS；11/11 / 11/11|
|POC-04 DeepSeek 401 / 文本 / SSE / 结构化 JSON|PASS；真实在线调用，证据不含 Secret 或响应正文|
|POC-06 OOXML 包 / Hash|PASS；DOCX 99 个显式分页、PPTX 50 页，与 Windows 11 Hash 一致|
|POC-06 Microsoft Office 实开|BLOCKED；未安装 Word/PowerPoint|
|POC-08 Plugin Host 离线验证|PASS；13/13 测试、10/10 场景、20/20 并发，敏感环境变量可见数 0|
|POC-09 License 离线验证|PASS；26/26 测试、10/10 场景、8/8 非法授权拒绝，私钥/原始 MAC 不落盘|
