# CR-PKG-001：Windows Tesseract 离线发行来源调整

状态：OPEN / VALIDATION_IN_PROGRESS；日期：2026-10-01；Phase 2 / PLT-PKG-01-A08-P09-P03。Gate 2 技术栈 Tesseract 不变；本 CR 仅调整 Windows 离线发行二进制的来源/版本，不追写 POC-01 或 ADR-001 的 5.4 历史验证。

## 来源、冲突与方案

POC-01 使用 UB Mannheim Tesseract 5.4.0.20240606；其 [发布者 Release](https://github.com/UB-Mannheim/tesseract/releases/tag/v5.4.0.20240606) 下载件 50,175,248 字节/SHA-256 与 [Microsoft winget 固定清单](https://github.com/microsoft/winget-pkgs/blob/master/manifests/u/UB-Mannheim/TesseractOCR/5.4.0.20240606/UB-Mannheim.TesseractOCR.installer.yaml) 一致，但本机 Authenticode 报证书超期，链验证 `NotTimeValid`。来源 Hash 匹配不等于有效签名；该文件未执行或并入候选。

- A（选定）：评估 [Tesseract 上游官方 5.5.3 Release](https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.3) 的 Windows x64 安装资产。先核来源、固定 Hash、签名、许可和传递 DLL；若安全门禁通过，再在隔离 Windows11 路径重新验证 OCRmyPDF/deskew/中文训练数据与 Parser；最后做目标账户/Server2025。版本升级不能继承 5.4 的 PoC PASS。
- B：继续使用 5.4 历史安装资产，基于发布者 Release 与独立固定 Hash 作为替代控制接受过期签名。风险是代码签名身份不能有效验签，须另行记录安全例外和隔离测试；当前不选。
- C：自行从官方源码构建 Windows 二进制。来源可控，但编译环境/依赖与再现性成本更高；作为 A 失败时的后备方案，不预先实施。

## 差异、影响、迁移/回滚、验证

原历史 5.4 PoC、已安装开发机程序和非发行候选保持不动。若 A 通过，发行包固定 5.5.3 x64 及其 Hash/许可证，并在目标部署中作为新系统依赖；不自动升级或覆盖用户机器已有 Tesseract。若验证失败，拒绝并包，保留 5.4 PoC 与现有安装，回滚仅撤新候选与测试目录，不回滚业务数据库。

验证顺序：上游资产清单 → 下载字节/Hash/Authenticode → 许可/原生依赖清单 → 隔离安装及版本、tessdata_best 中英/OCRmyPDF `--deskew` 中文 Windows 输出编码 → 与 Ghostscript/Paddle 的合成 OCR 链 → Windows11/Server2025 清洁目标目录与账户 ACL/离线复装 → 发行安全与许可审查。未经过对应阶段不得宣称兼容或 Release PASS。无 DB/API/产品权限变化；可能改变 OCR 结果，需记录质量回归。旧候选始终 `release_eligible=false`。
