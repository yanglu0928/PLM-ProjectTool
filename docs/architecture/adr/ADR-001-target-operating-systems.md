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

Windows 11 Home 10.0.26200 / Python 3.13.15 已完成 Python 包在线安装、109 个 wheel 的离线安装以及 15/15 项 import/最小功能检查。Tesseract、Ghostscript、真实 OCR 和完整安装流程尚未验证，因此 Windows 11 当前为部分通过，不代表平台 Gate 已通过。

Windows Server 2025 与 Debian 13 尚缺正式执行环境和验证证据。

## 后续要求

- 补齐 Windows 11 系统级依赖和断网完整流程。
- 在 Windows Server 2025 与 Debian 13 执行相同 POC-01 验证。
- 后续 PoC、安装测试和 Release Gate 均按三平台登记结果。
