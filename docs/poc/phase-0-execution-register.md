# Phase 0 执行登记表

## 阶段状态

|字段|值|
|---|---|
|Phase|Phase 0 技术验证|
|状态|IN_PROGRESS|
|启动日期|2026-09-17|
|正式开发 Gate|BLOCKED|
|完成条件|全部 P0 PoC PASS，或失败项具有用户确认的替代方案|

## PoC 登记

|PoC|对应 WBS|验证主题|状态|开始日期|完成日期|结论|证据|
|---|---|---|---|---|---|---|---|
|POC-01|P0.01/P0.01S/P0.02/P0.03/P0.04|Python 3.13 三平台依赖及离线安装|IN_PROGRESS|2026-09-17|-|Windows 11、Windows Server 2025 子项 PASS；Debian 13 待验证|`poc/poc-01-python-313-dependencies/`|
|POC-02|P0.05/P0.06/P0.07/P0.08|PostgreSQL 18 + pgvector|NOT_STARTED|-|-|-|-|
|POC-03|P0.09/P0.10/P0.12|PLM RAG|NOT_STARTED|-|-|-|-|
|POC-04|P0.11|AI Gateway / DeepSeek|NOT_STARTED|-|-|-|-|
|POC-05|P0.04/P0.12|Document + OCR|NOT_STARTED|-|-|-|-|
|POC-06|P0.16/P0.17|Word / PPT|NOT_STARTED|-|-|-|-|
|POC-07|P1|VSDX|DEFERRED_P1|-|-|不阻塞 Phase 0|-|
|POC-08|P0.13|Plugin Host|NOT_STARTED|-|-|-|-|
|POC-09|P0.14/P0.15|License|NOT_STARTED|-|-|-|-|

## 状态定义

- `NOT_STARTED`：尚未开始。
- `IN_PROGRESS`：已有执行活动，但未满足完整验收条件。
- `BLOCKED`：当前缺少必要环境、输入或决策。
- `PASS`：全部必需产物和验收项通过。
- `FAIL`：已形成完整失败分析，尚无获批替代方案。
- `DEFERRED_P1`：正式降级为 P1，不阻塞 Phase 0。

## 变更记录

|日期|变更|
|---|---|
|2026-09-17|建立 Phase 0 登记表并启动 POC-01。|
|2026-09-17|完成 Windows 11 / Python 3.13.15 在线与 wheelhouse 离线预检；POC-01 保持 IN_PROGRESS。|
|2026-09-17|基线升版：新增 Windows 11，与 Windows Server 2025、Debian 13 并列为正式目标环境。|
|2026-09-17|Windows 11 完成 Tesseract/OCRmyPDF 中文扫描 PDF 主链验证，POC-01 平台覆盖达到 1/3。|
|2026-09-17|Windows 11 完成 Ghostscript 10.08.0 portable 安装、deskew 编码修复及 PDF/A-2b 回归验证。|
|2026-09-17|Windows Server 2025 Datacenter 实机完成 Python 3.13.15 官方嵌入式运行时、109-wheel 完全离线安装、15/15 项检查及中文 OCR/PDF-A-2b/deskew 验证；POC-01 平台覆盖达到 2/3。|
