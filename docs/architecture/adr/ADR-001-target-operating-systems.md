# ADR-001：目标操作系统扩展为三平台

- 状态：Accepted
- 日期：2026-09-17
- 决策人：用户/项目负责人
- 关联基线：实施方案 V2.1、总控规范 V1.1

## 背景

原 V2.0 基线仅将 Windows Server 2025 和 Debian 13 列为正式目标环境。项目负责人明确要求新增 Windows 11，与原有两个环境并列支持。

## 决策

正式目标操作系统调整为：

1. Windows 11 x86-64/AMD64。
2. Windows Server 2025 x86-64/AMD64。
3. Debian 13 x86-64/AMD64。

Windows 11 是新增目标，不替换或降低 Windows Server 2025、Debian 13 的兼容要求。

## 影响

- Phase 0 的依赖、PostgreSQL/pgvector、OCR、插件、License、Word/PPT 验证矩阵扩展为三个平台。
- 安装、升级、回归和发行验收必须分别覆盖三个平台。
- Windows 11 与 Windows Server 2025 可共享 Windows 发行介质时，仍需分别保留安装和运行证据。
- POC-01 的正式平台覆盖率目标由 2/2 调整为 3/3。

## 当前证据

Windows 11 Home 10.0.26200 / Python 3.13.15 已完成 Python 包在线安装、109 个 wheel 的离线安装以及 15/15 项 import/最小功能检查。Tesseract 5.4、OCRmyPDF 17.12.1、Ghostscript 10.08.0 和 `tessdata_best` 的 PDF/A-2b 中文扫描 PDF 主链已通过，deskew 正常，5/5 个预期术语命中。完整离线发行安装仍未执行，因此不代表 Windows 11 Release Gate 已通过。

Windows Server 2025 Datacenter 10.0.26100 已完成实机验证：Python 3.13.15 官方嵌入式运行时、109-wheel 完全离线安装、15/15 项 import/最小功能检查、Tesseract/OCRmyPDF/Ghostscript PDF/A-2b 与 deskew 中文主链均通过。该环境的系统策略拒绝非管理员 Python EXE 安装器，因此正式发行需保留免安装路径，并在 Release Gate 另行验证管理员安装路径。Debian 13 尚缺正式执行环境和验证证据；用户已通过 `EXC-P0-001` 批准本轮暂缓，未改变其正式目标平台地位。

## 后续要求

- 补齐 Windows 11 断网完整发行流程和 AGPL 发行 Gate。
- `EXC-P0-001` 解除本轮 POC-01 的 Debian 执行要求；恢复验证或进入 Debian 发行验收时，仍需执行相同验证。
- 后续 PoC、安装测试和 Release Gate 均按三平台登记结果。
