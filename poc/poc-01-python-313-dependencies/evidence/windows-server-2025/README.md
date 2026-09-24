# Windows Server 2025 验证证据

- 执行日期：2026-09-17
- 环境：Windows Server 2025 Datacenter 10.0.26100（Desktop Experience），x86-64
- 资源：16 逻辑处理器、16 GB RAM、系统盘约 54.71 GB 可用
- Python：3.13.15 官方 Windows embeddable package (64-bit)
- Python 包 SHA-256：`d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf`
- 执行模式：通过 VMware Tools 向虚拟机传入完全离线制品；验证期间不从包索引下载依赖
- 结论：PASS

## 结果

- 系统策略拒绝非管理员 Python EXE 安装器，返回 1625；随后使用 Python.org 官方嵌入式包完成无管理员部署。
- 109-wheel Windows 离线制品集安装成功。
- Python 3.13 与 15 项 import / 最小功能检查全部通过。
- Tesseract `chi_sim+eng`、Ghostscript 10.08.0、OCRmyPDF 17.12.1、PDF/A-2b 和 `--deskew` 全链路通过。
- 中文 OCR 预期术语 5/5 命中，召回率 100%。
- Windows 中文输出编码兼容层未发生解码异常。

## 文件

- `environment.json`：脱敏后的环境与包版本。
- `verification.json`：15 项依赖检查结果。
- `ocr-result.json`：OCR、PDF/A 与 deskew 结果。
- `validation-status.json`：来宾端最终状态。
- `artifact-sha256sums.txt`：输入、输出 PDF 与完整回收证据包的哈希。

原始日志与 PDF 存于本地忽略目录 `artifacts/poc-01/windows-server-2025/`，未提交账号、密码、主机名或用户目录。
