# PLT-PKG-01-A08-P08：Windows 候选原生文件来源与外部 OCR 缺项

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；非发行来源核查。
- 当前 WBS：PLT-PKG-01-A08-P08。
- 输入基线：A08-P07 非发行候选、A05 官方 Python3.13.15 AMD64 embed ZIP、A01 固定 Hash 的 93 个 wheel、ADR-002 Ghostscript AGPL 发行前置。
- 前置任务：候选、官方 Python/93 wheel 的原始 Hash 已核实；法律与 Release Gate 未通过。
- 涉及模块：本地原生文件来源审计工具；无业务代码、实体、API、权限、Schema 或 Migration。
- 验收标准：对候选 `.exe/.dll/.pyd/.so` 逐文件 SHA-256 匹配官方 embed 或固定 wheel；记录多个同字节来源的安装路径映射；外部 OCR 可执行文件缺项和合规风险明确。
- 风险：字节来源核查不检查 Windows DLL 传递依赖、签名、目标 OS 运行或许可证义务。审计 JSON 存 Git 忽略目录，可撤；不改变候选。

## Windows 11 执行结果

- 对 A08-P07 ZIP 完整性先验哈；官方 `python-3.13.15-embed-amd64.zip` SHA-256 固定 `d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf`；93 个原 wheel 按 A01 清单全部重新核哈。候选原生文件共 250 项，其中 30 项与官方 Python embed 对应成员同字节、220 项与 35 个原 wheel 中的成员同字节，未匹配 0。细目及来源 Hash 在本地忽略的 `artifacts/package-prep/windows11/embedded-full-notice-candidate-ad21bbbee647/native-source-evidence.json`。
- 首轮 249/250：顶层 `msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll` 与 NumPy、pandas、ujson 三个 wheel 内同字节，不能仅凭 Hash 唯一归属。按 wheel `.data/platlib` 标准旁装位置核查后，对应 ujson 成员路径唯一，250/250。该映射和合成同字节双来源/篡改/未知二进制测试 3/3 PASS；没有把歧义静默忽略。
- 候选无 `gswin*.exe` 或 `tesseract.exe`；A01 wheelhouse 无 `ocrmypdf` wheel。故旧 PoC 在开发机验证过的 Ghostscript/Tesseract/OCRmyPDF 链路并未进入当前候选，无法据此宣称离线完整 OCR/PDF-A。OCRmyPDF [官方 Windows 安装说明](https://ocrmypdf.readthedocs.io/en/stable/installation.html)亦将 Tesseract/Ghostscript 视为外部安装组件。
- [Ghostscript 官方许可说明](https://ghostscript.com/faq/)列出 AGPL/商业双路径；本项目 ADR-002 选 AGPL 路线但公开仓库/兼容许可/对应源码和分发通知尚未完成。候选还含 `PyMuPDF 1.28.2` wheel；其 [官方文档](https://pymupdf.readthedocs.io/en/latest/about.html)说明 AGPL/商业双路径，需与 Ghostscript 一并纳入产品公开源码/许可审查，不能只审核 Ghostscript。

## 结论与后续

`NATIVE_BYTE_SOURCE_MATCH_PASS / EXTERNAL_OCR_AND_LICENSE_RELEASE_BLOCKED`。本项不等于 DLL 依赖图、目标机重装或法律合规 PASS。下一项 `PLT-PKG-01-A08-P09` 建立 Ghostscript/Tesseract/OCRmyPDF 及模型的固定来源、版本、许可/安装矩阵，并核实本项目公开源码及产品许可前置；只有再经三平台离线安装/业务验收才可考虑发行。`release_eligible=false` 不变。
