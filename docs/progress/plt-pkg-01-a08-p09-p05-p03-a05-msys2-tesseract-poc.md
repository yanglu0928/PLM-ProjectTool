# PLT-PKG-01-A08-P09-P05-P03-A05：MSYS2 Tesseract 同版本隔离 PoC

## 编码前检查

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A05`；按 [CR-PKG-003](../changes/CR-PKG-003-tesseract-fully-traceable-windows-candidate.md)对完整包来源未证的官方安装资产建立独立候选，不切换正式产品路径。
- 输入基线/前置：A04 的 33 DLL 精确来源矩阵（32/33）；MSYS2 官方固定 `tesseract-ocr 5.5.3-1` 包及其历史依赖包；A03 固定四份 `tessdata_best`、OCRmyPDF17.12.1 嵌入式 Python 与 Ghostscript10.08.0 非发行 PoC。Gate 2 已批准，Gate 3 未通过。
- 模块/实体/API/权限：仅 `tools/build_tesseract_msys2_poc.py`、定向测试及非发行验证；无产品 Parser 配置、实体、API、Migration、权限、安装程序变更。
- 验收：包归档 Hash/版本拒错；递归 AMD64 PE 静态导入闭包；隔离拷贝逐文件 Hash、训练数据固定 Hash；CLI 版本/语言与标准、密集、表格、轻微倾斜四版面 PDF/A-2b/`--deskew` 术语回归。
- 风险/回滚：静态导入不覆盖延迟导入、动态插件和未测输入；相同 5.5.3 并非原安装资产的相同构建。PoC 路径可弃用，原官方安装资产、A03 候选和冻结基线不变。

## Windows 11 实测（2026-10-01）

从 [MSYS2 官方固定包](https://packages.msys2.org/packages/mingw-w64-x86_64-tesseract-ocr)及本机 A04 已固定的历史依赖归档装配新 ASCII 目录 `C:\Users\17231\AppData\Local\Temp\plm-tesseract-msys2-poc-20261001`，未覆盖旧目录或系统安装。Tesseract 包 SHA-256 `67c0a857e9f028f88d1463c0293885d806334346a81d70be5e38f08bad11e1e3` 与官方包页面一致；GCC `gcc-libs 16.1.0-5` 候选包与本机固定 `aa560f5438c35b71c3e7b24fd5becbca028f70c5b4d1f1697a86ff80fec947da` 一致。其余包逐项对 A04 矩阵。包内 `.PKGINFO` 名称/版本、档案 Hash 及每个复制文件 Hash 写入 Git 忽略的本机 `manifest.json`，并固定四份训练数据及 `pdf.ttf` 的 Hash。

递归静态图为 35 个本地 PE（二进制 1 exe + 34 DLL），保留目录无多余根 DLL、无子目录 DLL；11 个外部系统 DLL 只按导入名归类，目标环境的实际装载仍待。`tesseract.exe --version` 返回 5.5.3，`--list-langs` 列出 `chi_sim`、`chi_sim_vert`、`eng`、`osd`。图与清单是 Git 忽略证据 `artifacts/package-prep/windows11/tesseract-msys2-poc-static-graph.json` 和 PoC 根目录 `manifest.json`。包/训练数据不进入 Git。

以现有106-wheel 嵌入式 Python3.13.15、OCRmyPDF17.12.1、Ghostscript10.08.0，在 Windows 11 合成扫描 PDF 上运行 `--tesseract-pagesegmode 3 --deskew --output-type pdfa-2`：标准、密集、表格、轻微倾斜四版面均 exit0、PDF/A-2b 验证为真，预期中文/合同术语 20/20。报告留在 Git 忽略的 `artifacts/package-prep/windows11/tesseract-msys2-poc-{standard,dense,table,skewed}-20261001/result.json`。定向测试2项 PASS：固定档案被篡改即拒绝、已存在输出目录拒绝覆盖；调整后脚本语法校验通过。

## 结论与下一步

仅 `STATIC_IMPORT_CLOSURE_ONLY + FOUR_SYNTHETIC_LAYOUTS_PASS`，`release_eligible=false`。不等于动态依赖、包签名、传递许可/NOTICE、真实质量或目标账户/Server2025 发行验证。官方安装资产的 `libtesseract-5.dll` 缺口仍作为原候选事实保留；新候选 `libtesseract-5.5.dll` 来源可逐包归属，但不可继承旧构建的签名/许可/质量结论。下一项应单独完成新候选 35 个本地二进制的许可证与源码提供义务矩阵，并检查潜在延迟/动态装载；未闭合前不得把此 PoC 纳入正式安装包。
