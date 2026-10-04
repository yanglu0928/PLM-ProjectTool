# Windows Server 2025 验证证据

## Result

`PASS`

Windows Server 2025 Datacenter 10.0.26100 x86-64、Python 3.13.15 在 VMware 虚拟网卡断开状态完成全新目录复跑。验证时发现 1 个物理网卡、0 个连接；JSON Schema wheel 使用 `--no-index` 安装；PaddleOCR 使用包内显式本地模型目录。

六类输入统一解析和三条 OCR 链共 8/8 PASS，扫描术语召回均为 5/5，OCRmyPDF 输出 PDF/A-2b 且 `--deskew` 未出现中文 Windows 编码异常。验证完成后虚拟网卡已恢复。

## Evidence

- `offline-result.json`：操作系统、硬件、网卡隔离、包 Hash 和离线执行标志。
- `environment.json`：Python、包和外部工具版本。
- `input-manifest.json`：输入 SHA-256，与 Windows 11 一致。
- `model-manifest.json`：离线模型文件清单及 SHA-256。
- `validation-result.json`：最终 8/8 PASS 结果。

首次执行的六类解析和 OCR 实际已 PASS，但 PowerShell 5.1 用本地代码页读取无 BOM UTF-8 JSON，导致最终证据汇总失败。驱动改为显式 `-Encoding UTF8` 后重新生成离线包，并在全新工作目录重跑通过；最终证据引用修复后包的 SHA-256。
