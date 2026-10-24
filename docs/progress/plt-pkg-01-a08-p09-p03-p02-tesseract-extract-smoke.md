# PLT-PKG-01-A08-P09-P03-P02：官方安装资产静态解包与 OCR 冒烟

## 编码前检查

- Phase/WBS：Phase 2 / PLT-PKG-01-A08-P09-P03-P02；只做非安装式解包与合成输入测试。
- 基线/前置：CR-PKG-001 已登记版本及签名替代来源控制，P03-P01 官方资产 digest/大小固定、Defender 本机扫描无检出。
- 模块/实体/API/权限：发行输入验证，无产品源码、实体、API、权限、Schema 或 Migration 改动。
- 验收：只读解析 NSIS，检查文件清单、PE 架构、包内版本、许可证文件与合成中英 OCR；不将短样本推为完整质量/deskew/安装通过。
- 风险/回滚：运行包内 tesseract CLI，但未运行安装器；签名仍无效。隔离解包目录在 Git 忽略区，原系统安装不变。

## Windows 11 结果

对官方 5.5.3 SHA-256 `bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4` 安装资产，使用本机隔离 7-Zip 只读解包至 `artifacts/package-prep/windows11/tesseract-official-5.5.3-extract`：NSIS-3 Unicode，139 个文件，7-Zip 完整提取 PASS；目录包含 `doc/LICENSE`（Apache License 2.0）、`tesseract.exe`、`libtesseract-5.dll` 及多种第三方 DLL，尚未完成每个 DLL/JAR 的单独许可/来源审计。

包内 `tesseract.exe` SHA-256 `c66f0f12ed76f6aa455dac97684bbc86756d6a732380bee09122454cfda3f420`，PE Machine `0x8664`（AMD64）。在该目录直接执行 `--version` 得 `tesseract v5.5.3.20260724`、exit 0；未运行 NSIS 安装器、未触碰现有系统 Tesseract。使用 POC-01 已锁定的 `tessdata_best`，本地合成 PNG：英文 `PROJECT SCOPE APPROVED` 逐字识别；中文 `项目实施`（空格规范化后）识别一致，exit 0。首次较长中文“项目范围确认”样本未完全准确，不以本冒烟样本证明中文实际文档质量。

结果 `EXTRACTED_AMD64_CLI_SYNTHETIC_OCR_PASS / INSTALL_AND_DESKEW_NOT_RUN`。后续须审计 139 文件中第三方许可、隔离安装/服务账户、OCRmyPDF17.12.1 `--deskew` 中文 Windows 输出编码、PDF/A 与 Ghostscript 组合及 Windows Server 2025，且 CR-PKG-001 的无效签名仍需专项安全收口。`release_eligible=false`。
